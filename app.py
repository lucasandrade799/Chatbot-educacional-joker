import sqlite3
import os
import json
from google import genai
from google.genai.errors import APIError
from google.genai.types import GenerateContentConfig
from flask import Flask, request, jsonify, send_file
from twilio.twiml.messaging_response import MessagingResponse
from flask_cors import CORS

# --- VARIÁVEIS DE CONFIGURAÇÃO E CHAVE API ---
API_KEY_GEMINI = os.environ.get('GEMINI_API_KEY')
DATABASE_NAME = 'BDchatbot.db'

# --- 1. SCRIPT SQL COMPLETO ---
# ATENÇÃO: Apenas 8 matérias com NP1/NP2/PIM e 1 PIM por semestre.
SQL_SCRIPT_CONTENT = """
-- CRIAÇÃO DAS TABELAS
CREATE TABLE IF NOT EXISTS Alunos (
    id_aluno INTEGER PRIMARY KEY AUTOINCREMENT,
    RA VARCHAR(10) NOT NULL UNIQUE,
    Nome_Completo VARCHAR(100) NOT NULL,
    Tipo_Usuario VARCHAR(10) NOT NULL DEFAULT 'Aluno',
    Codigo_Seguranca VARCHAR(6) NULL,
    Senha VARCHAR(100) NOT NULL 
);

CREATE TABLE IF NOT EXISTS Disciplinas (
    id_disciplina INTEGER PRIMARY KEY AUTOINCREMENT,
    Nome_Disciplina VARCHAR(100) NOT NULL,
    Semestre INT NOT NULL,
    Tipo_Avaliacao VARCHAR(10) NOT NULL, -- NORMAL (NP1/NP2/PIM), ED (Status), PIM (Nota Única)
    UNIQUE (Nome_Disciplina, Semestre)
);

CREATE TABLE IF NOT EXISTS Historico_Academico (
    id_registro INTEGER PRIMARY KEY AUTOINCREMENT,
    fk_id_aluno INT NOT NULL,
    fk_id_disciplina INT NOT NULL,
    NP1 DECIMAL(4, 2) NULL, 
    NP2 DECIMAL(4, 2) NULL, 
    Media_Final DECIMAL(4, 2) NULL, 
    Faltas INT NULL, 
    FOREIGN KEY (fk_id_aluno) REFERENCES Alunos(id_aluno),
    FOREIGN KEY (fk_id_disciplina) REFERENCES Disciplinas(id_disciplina),
    UNIQUE (fk_id_aluno, fk_id_disciplina)
);

-- POPULANDO A TABELA DISCIPLINAS (8 NORMAL + 1 PIM por semestre)
INSERT OR IGNORE INTO Disciplinas (Nome_Disciplina, Semestre, Tipo_Avaliacao) VALUES
-- Semestre 1: 8 matérias com NP1/NP2/PIM
('Introdução à Programação', 1, 'NORMAL'), 
('Lógica de Programação', 1, 'NORMAL'), 
('Arquitetura de Computadores', 1, 'NORMAL'),
('Redes de Computadores', 1, 'NORMAL'), 
('Sistemas de Informação', 1, 'NORMAL'),
('Estrutura de Dados I', 1, 'NORMAL'),
('Matemática Aplicada', 1, 'NORMAL'),
('Comunicação Empresarial', 1, 'NORMAL'), 
('PIM I', 1, 'PIM'), 

-- Semestre 2: 8 matérias com NP1/NP2/PIM
('Estruturas de Dados II', 2, 'NORMAL'),
('Banco de Dados I', 2, 'NORMAL'), 
('Sistemas Operacionais', 2, 'NORMAL'), 
('Álgebra Linear', 2, 'NORMAL'),
('Engenharia de Software I', 2, 'NORMAL'),
('Análise de Sistemas', 2, 'NORMAL'),
('Tópicos Avançados', 2, 'NORMAL'),
('Gestão de Projetos', 2, 'NORMAL'),
('PIM II', 2, 'PIM');

-- POPULANDO A TABELA ALUNOS (Senhas e Códigos de Segurança inclusos)
INSERT OR IGNORE INTO Alunos (RA, Nome_Completo, Tipo_Usuario, Codigo_Seguranca, Senha) VALUES
('R6738H5', 'Matheus Balzi da Silva', 'Aluno', NULL, '123456'), 
('R818888', 'Lucas Gabriel da Silva Gardezan', 'Aluno', NULL, '123456'),
('H755247', 'Matheus Henrique Castro de Oliveira', 'Aluno', NULL, '123456'), 
('R848140', 'Thainanda Alves Monteiro', 'Aluno', NULL, '123456'), 
('820793', 'LUCAS ANDRADE', 'Aluno', NULL, '123456'), -- RA do Lucas Andrade (820793)
-- Professor com Código de Segurança e Senha do Professor
('P12345', 'Prof. SAE NIIJIMA', 'Professor', '010101', 'professorsenha'); 

-- REGISTRO DO HISTÓRICO ACADÊMICO (Todos os alunos com todas as disciplinas inicialmente NULL)
INSERT OR IGNORE INTO Historico_Academico (fk_id_aluno, fk_id_disciplina, NP1, NP2, Media_Final, Faltas)
SELECT 
    A.id_aluno, 
    D.id_disciplina,
    NULL AS NP1, 
    NULL AS NP2, 
    NULL AS Media_Final, 
    NULL AS Faltas 
FROM Alunos A
JOIN Disciplinas D;
"""

# --- INICIALIZAÇÃO DO FLASK E GEMINI ---
app = Flask(__name__)
CORS(app)
client = None

if API_KEY_GEMINI:
    try: # CORRIGIDO: Recuo com espaços normais
        client = genai.Client(api_key=API_KEY_GEMINI)
        print("✅ Cliente Gemini inicializado com sucesso.")
    except Exception as e:
        print(f"❌ Erro fatal ao inicializar o cliente Gemini. Detalhe: {e}")
else:
    print("⚠️ Chave API do Gemini ausente. A Op. 2 e o roteador não funcionarão.")


# --- 2. FUNÇÕES DE SUPORTE AO BANCO DE DADOS E CÁLCULOS ---

def _get_aluno_id(conn, ra_aluno):
    """Busca o ID do aluno pelo RA."""
    cursor = conn.cursor()
    cursor.execute("SELECT id_aluno FROM Alunos WHERE RA = ?", (ra_aluno,))
    result = cursor.fetchone()
    return result['id_aluno'] if result else None
    
def _set_test_data(conn, ra_aluno, nome_disciplina, np1=None, np2=None, media_final=None):
    """Função auxiliar para popular dados de teste de forma segura."""
    update_parts = []
    values = []

    if np1 is not None:
        update_parts.append("NP1 = ?")
        values.append(np1)
    if np2 is not None:
        update_parts.append("NP2 = ?")
        values.append(np2)
    if media_final is not None:
        update_parts.append("Media_Final = ?")
        values.append(media_final)

    if not update_parts:
        return

    sql_update = f"""
    UPDATE Historico_Academico
    SET {', '.join(update_parts)}
    WHERE fk_id_aluno = (SELECT id_aluno FROM Alunos WHERE RA = ?)
    AND fk_id_disciplina = (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = ?);
    """
    values.extend([ra_aluno, nome_disciplina])
    conn.execute(sql_update, values)
    conn.commit()
    
def init_db():
    """Cria e popula o banco de dados. Chamado apenas no início do servidor."""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.executescript(SQL_SCRIPT_CONTENT)
        conn.commit()
        
        # --- PREENCHIMENTO DE DADOS DE TESTE PARA LUCAS ANDRADE (820793) ---
        RA_LUCAS = '820793'
        
        _set_test_data(conn, RA_LUCAS, 'Introdução à Programação', 7.0, 6.0)
        _set_test_data(conn, RA_LUCAS, 'Lógica de Programação', 8.5, 7.5)
        _set_test_data(conn, RA_LUCAS, 'Arquitetura de Computadores', 5.0, 9.0)
        _set_test_data(conn, RA_LUCAS, 'Redes de Computadores', 9.0, 9.0)
        _set_test_data(conn, RA_LUCAS, 'Sistemas de Informação', 6.0, 6.0)
        _set_test_data(conn, RA_LUCAS, 'Estrutura de Dados I', 7.0, 7.0)
        _set_test_data(conn, RA_LUCAS, 'Matemática Aplicada', 5.5, 6.5)
        _set_test_data(conn, RA_LUCAS, 'Comunicação Empresarial', 8.0, 8.0)

        _set_test_data(conn, RA_LUCAS, 'PIM I', media_final=8.0) # PIM nota 8.0
        
        # Recalcula todas as disciplinas NORMAIS após definir o PIM
        aluno_id = _get_aluno_id(conn, RA_LUCAS)
        if aluno_id:
            _recalcular_todas_medias_notas_np_do_semestre(conn, aluno_id, 1)
        
        # --- FIM PREENCHIMENTO DE DADOS ---
        
        conn.close()
        print(f"✅ Banco de dados '{DATABASE_NAME}' verificado, populado e pronto para uso.")
    except sqlite3.Error as e:
        print(f"❌ Erro na inicialização do banco de dados: {e}")
        exit()

def get_db_connection():
    """Retorna uma nova conexão ao banco de dados para uma requisição."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def formatar_valor(valor):
    """Auxiliar para formatar números ou retornar None."""
    if valor is None:
        return None
    try:
        return f"{float(valor):.2f}"
    except (ValueError, TypeError):
        return None

def calcular_media_final(np1, np2, pim_nota):
    """
    Calcula a média final usando a fórmula: (NP1*40% + NP2*40% + PIM*20%)
    Válido para TODAS as matérias que usam NP1 e NP2.
    Retorna float se cálculo possível, senão None.
    """
    if np1 is None or np2 is None or pim_nota is None:
        return None  # Não é possível calcular
    try:
        np1 = float(np1)
        np2 = float(np2)
        pim_nota = float(pim_nota)
        # A regra é: (NP1*4 + NP2*4 + PIM*2) / 10
        media = (np1 * 0.4) + (np2 * 0.4) + (pim_nota * 0.2)
        return round(media, 2)
    except (ValueError, TypeError):
        return None
    
def _get_pim_nota(conn, id_aluno, semestre):
    """Busca a nota PIM (Media_Final) de um aluno para um semestre específico."""
    pim_sql = """
    SELECT H.Media_Final 
    FROM Historico_Academico H
    JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
    WHERE H.fk_id_aluno = ? AND D.Semestre = ? AND D.Tipo_Avaliacao = 'PIM'
    """
    cursor = conn.cursor()
    cursor.execute(pim_sql, (id_aluno, semestre))
    pim_result = cursor.fetchone()
    # A nota PIM é armazenada no campo Media_Final da disciplina PIM
    return pim_result['Media_Final'] if pim_result and pim_result['Media_Final'] is not None else None

def _recalcular_e_salvar_media_notas_np(conn, id_aluno, nome_disciplina):
    """
    Busca NP1, NP2 e PIM (do semestre) e recalcula/salva a Media_Final
    para uma disciplina que usa a regra NP1/NP2/PIM (Tipo_Avaliacao != PIM).
    """
    sql_dados = """
    SELECT 
        H.id_registro, H.NP1, H.NP2, D.Semestre, D.Tipo_Avaliacao
    FROM Historico_Academico H
    JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
    WHERE H.fk_id_aluno = ? AND D.Nome_Disciplina = ? AND D.Tipo_Avaliacao NOT IN ('PIM');
    """
    cursor = conn.cursor()
    cursor.execute(sql_dados, (id_aluno, nome_disciplina))
    reg = cursor.fetchone()

    if not reg:
        return False, "Disciplina não encontrada ou é PIM (não usa cálculo NP1/NP2/PIM)."
    
    # Se a disciplina for PIM, ela não deve chegar aqui (checado na query)
    if reg['Tipo_Avaliacao'] in ['PIM']:
        return False, "Disciplina é PIM. Não há cálculo de média NP1/NP2/PIM."

    pim_nota = _get_pim_nota(conn, id_aluno, reg['Semestre'])
    
    media = calcular_media_final(reg['NP1'], reg['NP2'], pim_nota)
    
    # Salva a nova média, ou NULL se não puder ser calculada
    sql_update = """
    UPDATE Historico_Academico SET Media_Final = ? WHERE id_registro = ?
    """
    cursor.execute(sql_update, (media, reg['id_registro']))
    conn.commit()
    
    return True, media


def _recalcular_todas_medias_notas_np_do_semestre(conn, id_aluno, semestre):
    """
    Recalcula a média de TODAS as disciplinas (exceto PIM) de um semestre,
    usando a nova nota PIM.
    """
    pim_nota = _get_pim_nota(conn, id_aluno, semestre)
    
    sql_disciplinas_np = """
    SELECT 
        H.id_registro, H.NP1, H.NP2, D.Nome_Disciplina
    FROM Historico_Academico H
    JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
    WHERE H.fk_id_aluno = ? AND D.Semestre = ? AND D.Tipo_Avaliacao NOT IN ('PIM');
    """
    cursor = conn.cursor()
    cursor.execute(sql_disciplinas_np, (id_aluno, semestre))
    registros_np = cursor.fetchall()
    
    if not registros_np:
        return 0
        
    for reg in registros_np:
        media = calcular_media_final(reg['NP1'], reg['NP2'], pim_nota)
        
        sql_update = """
        UPDATE Historico_Academico SET Media_Final = ? WHERE id_registro = ?
        """
        cursor.execute(sql_update, (media, reg['id_registro']))
        
    conn.commit()
    return len(registros_np)


# --- 3. FUNÇÕES DE OPERAÇÃO (LÓGICA CORE: Leitura e Escrita) ---

# --- OPERAÇÕES DE ESCRITA (Professor Tools) ---

def lancar_nota_np_api(ra_aluno: str, nome_disciplina: str, np_qual: str, nota: float) -> dict:
    """Lança a nota NP1 ou NP2 e recalcula a Média Final se possível."""
    ra_aluno = ra_aluno.strip().upper()
    nome_disciplina = nome_disciplina.strip()
    np_qual = np_qual.strip().upper()

    if np_qual not in ['NP1', 'NP2'] or not (0.0 <= nota <= 10.0):
        return {"status": "error", "message": "Parâmetros inválidos. Use NP1 ou NP2 com nota entre 0.0 e 10.0."}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Obter IDs e checar se é NOT IN ('PIM')
        sql_info = """
        SELECT A.id_aluno, D.Tipo_Avaliacao 
        FROM Alunos A
        JOIN Historico_Academico H ON A.id_aluno = H.fk_id_aluno
        JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
        WHERE A.RA = ? AND D.Nome_Disciplina = ?;
        """
        cursor.execute(sql_info, (ra_aluno, nome_disciplina))
        info = cursor.fetchone()

        if not info:
            conn.close()
            return {"status": "error", "message": f"Aluno/Disciplina '{ra_aluno}'/'{nome_disciplina}' não encontrados."}
        
        if info['Tipo_Avaliacao'] in ['PIM']:
            conn.close()
            return {"status": "error", "message": f"Lançamento de NP1/NP2 não é permitido para PIM. '{nome_disciplina}' é {info['Tipo_Avaliacao']}."}

        # 2. Atualizar nota NP
        sql_update_np = f"""
        UPDATE Historico_Academico 
        SET {np_qual} = ?
        WHERE fk_id_aluno = ? 
        AND fk_id_disciplina = (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = ?);
        """
        cursor.execute(sql_update_np, (nota, info['id_aluno'], nome_disciplina))

        # 3. Recalcular e salvar Media_Final (se possível)
        sucesso, media = _recalcular_e_salvar_media_notas_np(conn, info['id_aluno'], nome_disciplina)
        
        conn.close()

        status_media = f"Média Final calculada e salva: {media:.2f}" if media is not None else "Média Final pendente (PIM ou outra NP faltando)."
        return {"status": "success", "message": f"Nota {np_qual} ({nota:.2f}) lançada para {nome_disciplina} ({ra_aluno}). {status_media}"}

    except sqlite3.Error as e:
        conn.close()
        return {"status": "error", "message": f"Erro no lançamento da nota NP: {e}"}

def lancar_nota_pim_api(ra_aluno: str, nome_disciplina_pim: str, nota: float) -> dict:
    """Lança a nota PIM e recalcula a Média Final de todas as disciplinas com NP1/NP2 do semestre."""
    ra_aluno = ra_aluno.strip().upper()
    nome_disciplina_pim = nome_disciplina_pim.strip()

    if not (0.0 <= nota <= 10.0):
        return {"status": "error", "message": "Nota PIM inválida. Deve estar entre 0.0 e 10.0."}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Obter IDs e checar se é PIM
        sql_info = """
        SELECT A.id_aluno, D.Tipo_Avaliacao, D.Semestre
        FROM Alunos A
        JOIN Historico_Academico H ON A.id_aluno = H.fk_id_aluno
        JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
        WHERE A.RA = ? AND D.Nome_Disciplina = ?;
        """
        cursor.execute(sql_info, (ra_aluno, nome_disciplina_pim))
        info = cursor.fetchone()

        if not info:
            conn.close()
            return {"status": "error", "message": f"Aluno/Disciplina PIM '{ra_aluno}'/'{nome_disciplina_pim}' não encontrados."}
        
        if info['Tipo_Avaliacao'] != 'PIM':
            conn.close()
            return {"status": "error", "message": f"'{nome_disciplina_pim}' não é uma disciplina PIM."}

        # 2. Atualizar nota PIM (que fica no campo Media_Final)
        sql_update_pim = """
        UPDATE Historico_Academico 
        SET Media_Final = ?
        WHERE fk_id_aluno = ? 
        AND fk_id_disciplina = (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = ?);
        """
        cursor.execute(sql_update_pim, (nota, info['id_aluno'], nome_disciplina_pim))

        # 3. Recalcular e salvar Media_Final para todas as disciplinas com NP1/NP2 do semestre
        count_recalculada = _recalcular_todas_medias_notas_np_do_semestre(conn, info['id_aluno'], info['Semestre'])
        
        conn.close()

        return {"status": "success", "message": f"Nota PIM ({nota:.2f}) lançada para o semestre {info['Semestre']} ({ra_aluno}). {count_recalculada} Média(s) Final(is) recalculada(s) (40% NP1 + 40% NP2 + 20% PIM)."}

    except sqlite3.Error as e:
        conn.close()
        return {"status": "error", "message": f"Erro no lançamento da nota PIM: {e}"}

def marcar_ed_concluido_api(ra_aluno: str, nome_disciplina_ed: str) -> dict:
    """
    Função mantida por flexibilidade, mas as EDs foram removidas do DB para seguir
    a regra de 8 matérias NP/PIM e 1 PIM. 
    Se a regra mudar novamente, esta função seria ativada para 'Tipo_Avaliacao' = 'ED'.
    No momento, ela retornará erro, pois 'ED' não existe mais como disciplina separada.
    """
    return {"status": "error", "message": f"A disciplina '{nome_disciplina_ed}' não é mais reconhecida como Estudo Dirigido (ED) separado para notas. Favor usar a ferramenta de lançamento de notas para disciplinas com NP1/NP2/PIM."}
    
def lancar_faltas_api(ra_aluno: str, nome_disciplina: str, faltas: int) -> dict:
    """Lança o número de faltas para uma disciplina."""
    ra_aluno = ra_aluno.strip().upper()
    nome_disciplina = nome_disciplina.strip()

    if faltas < 0:
        return {"status": "error", "message": "Número de faltas inválido."}
    
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. Obter IDs 
        sql_info = """
        SELECT A.id_aluno, D.Tipo_Avaliacao 
        FROM Alunos A
        JOIN Historico_Academico H ON A.id_aluno = H.fk_id_aluno
        JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
        WHERE A.RA = ? AND D.Nome_Disciplina = ?;
        """
        cursor.execute(sql_info, (ra_aluno, nome_disciplina))
        info = cursor.fetchone()

        if not info:
            conn.close()
            return {"status": "error", "message": f"Aluno/Disciplina '{ra_aluno}'/'{nome_disciplina}' não encontrados."}
        
        # 2. Atualizar faltas
        sql_update_faltas = """
        UPDATE Historico_Academico 
        SET Faltas = ?
        WHERE fk_id_aluno = ? 
        AND fk_id_disciplina = (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = ?);
        """
        cursor.execute(sql_update_faltas, (faltas, info['id_aluno'], nome_disciplina))
        conn.commit()
        conn.close()
        
        aviso = ""
        if info['Tipo_Avaliacao'] in ['PIM']:
             aviso = f" (AVISO: '{nome_disciplina}' é PIM e não costuma ter controle de faltas, mas o registro foi salvo.)"

        return {"status": "success", "message": f"Lançadas {faltas} faltas para '{nome_disciplina}' ({ra_aluno}).{aviso}"}

    except sqlite3.Error as e:
        conn.close()
        return {"status": "error", "message": f"Erro no lançamento de faltas: {e}"}


# --- OPERAÇÃO DE LEITURA (Consulta) ---

def verificar_dados_curso_api(ra_aluno: str) -> dict:
    """OPERAÇÃO 1: Busca o histórico ajustado para as regras de PIM/NP1/NP2."""
    ra_aluno = ra_aluno.strip().upper()

    comando_sql_join = """
    SELECT
    A.Nome_Completo, A.id_aluno, D.Nome_Disciplina, D.Semestre, D.Tipo_Avaliacao,
    H.NP1, H.NP2, H.Media_Final, H.Faltas
    FROM Historico_Academico H
    JOIN Alunos A ON H.fk_id_aluno = A.id_aluno
    JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
    WHERE A.RA = ?
    ORDER BY D.Semestre, D.Tipo_Avaliacao DESC, D.Nome_Disciplina;
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(comando_sql_join, (ra_aluno,))
        registros = cursor.fetchall()

        if not registros:
            conn.close()
            cursor.execute("SELECT Nome_Completo, Tipo_Usuario FROM Alunos WHERE RA = ?", (ra_aluno,))
            info_user = cursor.fetchone()
            
            if info_user:
                 return {"status": "error", "message": f"O usuário '{info_user['Nome_Completo']}' ({ra_aluno}) não possui histórico acadêmico registrado."}
            
            return {"status": "error", "message": f"A credencial '{ra_aluno}' não foi encontrada."}

        historico = []
        id_aluno = registros[0]['id_aluno']
        
        # Pré-busca de todas as notas PIM para evitar múltiplas queries
        pim_notas = {}
        semestres = sorted(list(set(reg['Semestre'] for reg in registros)))
        for sem in semestres:
            pim_notas[sem] = _get_pim_nota(conn, id_aluno, sem)


        for reg in registros:
            tipo = reg['Tipo_Avaliacao'].upper()
            semestre = reg['Semestre']
            
            np1_val = formatar_valor(reg['NP1'])
            np2_val = formatar_valor(reg['NP2'])
            media_val = formatar_valor(reg['Media_Final'])
            faltas_val = reg['Faltas'] if reg['Faltas'] is not None else None

            disciplina_info = {
                "disciplina": reg['Nome_Disciplina'],
                "semestre": semestre,
                "tipo_avaliacao": "Matéria com NP1/NP2/PIM" if tipo == 'NORMAL' else tipo,
            }

            if tipo == 'PIM':
                # PIM: Somente uma nota (Media_Final).
                pim_nota = pim_notas.get(semestre)
                disciplina_info.update({
                    "nota_pim": formatar_valor(pim_nota) if pim_nota is not None else "Indefinida",
                    "np1": "N/A",
                    "np2": "N/A",
                    "media_final": "N/A", 
                    "faltas": "N/A",
                    "observacao": "Nota de trabalho (20% do cálculo da Média Final de outras matérias)."
                })
            
            elif tipo == 'NORMAL': # Matérias com NP1/NP2/PIM
                
                pim_nota_semestre = pim_notas.get(semestre)
                media_display = media_val
                
                # Se a Media_Final não estiver salva, tenta calcular dinamicamente
                if reg['Media_Final'] is None:
                    calculated_media = calcular_media_final(reg['NP1'], reg['NP2'], pim_nota_semestre)
                    media_display = formatar_valor(calculated_media) if calculated_media is not None else "Indefinida"
                
                # Trata faltas: se for NULL, exibe 'N/A'
                faltas_exibicao = faltas_val if faltas_val is not None else "N/A"
                
                disciplina_info.update({
                    "np1": np1_val if np1_val is not None else "Indefinida",
                    "np2": np2_val if np2_val is not None else "Indefinida",
                    "nota_pim_usada": formatar_valor(pim_nota_semestre) if pim_nota_semestre is not None else "Indefinida",
                    "media_final": media_display,
                    "faltas": faltas_exibicao,
                    "observacao": "Média calculada: 40% NP1, 40% NP2, 20% PIM."
                })
            else: # Para qualquer outro tipo que possa ser adicionado (ex. ED, que foi excluído)
                # Mantido para robustez, mas deve ser inalcançável com o DB atual
                disciplina_info.update({
                    "np1": "N/A", "np2": "N/A", "media_final": media_val if media_val is not None else "N/A",
                    "faltas": faltas_val if faltas_val is not None else "N/A",
                    "observacao": f"Tipo de avaliação: {tipo}"
                })
                
            historico.append(disciplina_info)

        conn.close()
        return {
            "status": "success",
            "aluno": registros[0]['Nome_Completo'],
            "ra": ra_aluno,
            "historico": historico,
            "nota_pim_info": "Disciplinas com NP1/NP2: Média Final = (NP1*40% + NP2*40% + PIM*20%)."
        }

    except sqlite3.Error as e:
        conn.close()
        return {"status": "error", "message": f"Erro na consulta ao banco de dados: {e}"}

def buscar_material_estudo_api(topico: str) -> dict:
    """OPERAÇÃO 2: Gera material usando o Gemini e retorna a resposta. (Com Google Search ativado)"""
    if not client:
        return {"status": "error", "message": "A API do Gemini não está configurada corretamente."}

    prompt = (
        f"Gere um material de estudo conciso e focado para o tópico '{topico}'. "
        "Inclua:\n"
        "1. Breve resumo.\n"
        "2. Três pontos chave.\n"
        "3. Um exercício prático (com resposta).\n"
        "4. **Busque na web** e adicione **2 sugestões de links relevantes (vídeo-aulas ou artigos) sobre o tópico, formatados como links Markdown [Título](URL)**. "
        "Responda em português. Mantenha o tom acadêmico-informal."
        "Encaminhe todo o material gerado sob as especificações acima para o usuário para que ele possa visualizar tudo e estudar."
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=GenerateContentConfig(tools=[{"google_search": {}}])
        )

        return {
            "status": "success",
            "topico": topico,
            "material": response.text
        }

    except APIError as e:
        return {"status": "error", "message": f"Erro na API do Gemini: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Ocorreu um erro inesperado ao gerar o conteúdo: {e}"}

# --- 4. CONFIGURAÇÃO DE FUNÇÕES (TOOLS) E ROUTER DE CONTEÚDO ---

# Mapeamento das ferramentas
TOOLS = {
    'verificar_historico_academico': verificar_dados_curso_api,
    'gerar_material_estudo': buscar_material_estudo_api,
    'lancar_nota_np': lancar_nota_np_api, 
    'lancar_nota_pim': lancar_nota_pim_api, 
    'marcar_ed_concluido': marcar_ed_concluido_api, 
    'lancar_faltas': lancar_faltas_api 
}

def rotear_e_executar_mensagem(mensagem_usuario: str, tipo_usuario: str) -> str:
    """
    Usa o Gemini para interpretar a intenção do usuário (Function Calling),
    executa a função apropriada, com base no tipo de usuário logado (permissão).
    """

    if not client:
        return "❌ Desculpe, a conexão com a inteligência artificial está temporariamente indisponível."

    # 1. CONTROLE DE PERMISSÃO: Define quais ferramentas o Gemini pode acessar
    if tipo_usuario.upper() == 'PROFESSOR':
        # PROFESSOR: Acesso total (Leitura e Escrita)
        ferramentas_permitidas = list(TOOLS.values()) 
        instrucoes_perfil = (
            "Você é um assistente acadêmico para um **Professor**. Sua persona é o **Joker** (Persona 5). Responda com um tom sarcástico, mas sempre respeitoso e informativo. Use emojis e linguagem que remetam ao estilo dele. "
            "Suas principais tarefas são: 1. Ajudar o professor a visualizar dados acadêmicos. 2. Gerar material de estudo. 3. **Lançar notas (NP1, NP2, PIM) e faltas.** "
            "O sistema calcula a média de todas as matérias automaticamente após ter NP1, NP2 e PIM (Fórmula: 40% NP1 + 40% NP2 + 20% PIM). Ao lançar notas, garanta que todos os 4 parâmetros (RA, Disciplina, NP/PIM e Nota) estejam claros e use a função apropriada. Informe a ele que o lançamento do PIM recalcula automaticamente todas as notas do semestre."
            "O sistema foi configurado com 8 disciplinas que usam NP1/NP2/PIM, e a disciplina PIM que dá a nota para as outras 8. Não existe mais disciplina 'ED' separada no histórico. Se for pedido para lançar ED, use a resposta padrão para a ferramenta 'marcar_ed_concluido'."
            "Ao exibir dados do histórico, formate a resposta em Markdown (listas ou tabelas) para que a visualização seja clara e fácil de ler. Não use aspas ou blocos de código para formatar a resposta."
        )
    else: # Aluno
        # ALUNO: Acesso restrito (Somente Leitura de Histórico e Geração de Material)
        ferramentas_permitidas = [
            TOOLS['verificar_historico_academico'], 
            TOOLS['gerar_material_estudo']
        ]
        instrucoes_perfil = (
            "Você é um assistente acadêmico para um **Aluno**. Sua persona é o **Joker** (Persona 5). Responda com um tom sarcástico, mas sempre informativo, usando emojis e linguagem que remetam ao estilo dele. "
            "Suas principais tarefas são: 1. Ajudar o aluno a verificar o próprio histórico. 2. Gerar material de estudo. **(Você NÃO pode lançar ou alterar notas ou faltas.)**"
            "Ao exibir dados do histórico, formate a resposta em Markdown (listas ou tabelas) para que a visualização seja clara e fácil de ler. Não use aspas ou blocos de código para formatar a resposta."
        )
        
    prompt_ferramenta = (
        f"{instrucoes_perfil}\n\n"
        "O usuário enviou a seguinte mensagem: '{}'. \n\n"
        "**Instruções para Ferramentas:**\n"
        "1. Se o usuário pedir especificamente por um RA, notas ou histórico, use 'verificar_historico_academico'.\n"
        "2. Se o usuário pedir um material de estudo/resumo/explicação sobre um tópico, use 'gerar_material_estudo'.\n"
        "3. Se o professor pedir para lançar NP1/NP2, use 'lancar_nota_np'.\n"
        "4. Se o professor pedir para lançar PIM, use 'lancar_nota_pim'.\n"
        "5. Se o professor pedir para marcar ED como concluído, use 'marcar_ed_concluido' (recebe a resposta padrão da função).\n"
        "6. Se o professor pedir para lançar faltas, use 'lancar_faltas'.\n"
        "7. Para **qualquer outra pergunta abrangente** ou se a função for desnecessária/impossível, **RESPONDA DIRETAMENTE**.\n"
        "Em caso de dados faltantes (ex: RA, nota), peça-os. \n\n"
    ).format(mensagem_usuario)

    # 2. Envia a mensagem com as ferramentas FILTRADAS para o Gemini
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt_ferramenta],
            config=GenerateContentConfig(tools=ferramentas_permitidas)
        )
    except Exception as e:
        print(f"Erro na chamada do Gemini: {e}")
        return "❌ Erro ao processar a requisição com o Gemini. Tente novamente."


    # 3. Verifica se o Gemini decidiu chamar uma função
    if response.function_calls:
        call = response.function_calls[0]
        func_name = call.name
        func_args = dict(call.args)

        if func_name in TOOLS:
            print(f"🤖 Chamando função {func_name} com args: {func_args}")

            # 4. Executa a função localmente
            try:
                function_response_data = TOOLS[func_name](**func_args)
            except TypeError as e:
                return f"Joker: Parece que você esqueceu alguns detalhes, Mestre. Verifique se passou todos os parâmetros corretos para {func_name}. Detalhe técnico: {e}"

            # Se a busca/lançamento SQL falhar, retorna o erro diretamente.
            if function_response_data.get('status') == 'error':
                # Permite que a resposta padrão da 'marcar_ed_concluido' seja enviada sem processamento extra
                if func_name == 'marcar_ed_concluido':
                    return f"Joker: Ops! 🃏 {function_response_data['message']}"

            # 5. Envia o resultado da execução de volta ao Gemini
            segundo_prompt = [
                response,
                genai.types.Part.from_function_response(
                    name=func_name,
                    response=function_response_data
                )
            ]

            # 6. Gera a resposta final formatada para o usuário
            final_response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=segundo_prompt
            )

            return final_response.text

    # 7. Se nenhuma função foi chamada, o Gemini respondeu diretamente
    return response.text


# --- ROTAS DE FLASK (Login e Router) ---

@app.route('/login', methods=['POST'])
def handle_login():
    """
    Simulação de autenticação com senhas fixas (Aluno: 123456)
    e três campos obrigatórios para Professor.
    """
    try:
        data = request.get_json()
        tipo_usuario = data.get('tipo_usuario', '').strip().upper()
        
        # A senha é o campo 'senha' para ambos
        senha = data.get('senha') 
        
        # Credencial Principal
        credencial = data.get('ra') if tipo_usuario == 'ALUNO' else data.get('funcional')
        credencial = credencial.strip().upper() if credencial else None
        
        # Campo exclusivo do Professor
        codigo_seguranca = data.get('codigo_seguranca', '').strip()

        if not credencial or not senha:
            return jsonify({"status": "error", "message": "Credencial e Senha são obrigatórios."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Lógica de autenticação
        if tipo_usuario == 'ALUNO':
            sql = "SELECT RA, Nome_Completo, Tipo_Usuario, Senha FROM Alunos WHERE RA = ? AND Tipo_Usuario = 'Aluno'"
            params = (credencial,)
        elif tipo_usuario == 'PROFESSOR':
            if not codigo_seguranca:
                 conn.close()
                 return jsonify({"status": "error", "message": "Para Professores, o Código de Segurança é obrigatório."}), 400
                 
            sql = "SELECT RA, Nome_Completo, Tipo_Usuario, Senha, Codigo_Seguranca FROM Alunos WHERE RA = ? AND Tipo_Usuario = 'Professor'"
            params = (credencial,)
        else:
            conn.close()
            return jsonify({"status": "error", "message": "Tipo de usuário inválido. Use 'Aluno' ou 'Professor'."}), 400
            
        cursor.execute(sql, params)
        user_data = cursor.fetchone()
        conn.close()
        
        if not user_data:
            return jsonify({"status": "error", "message": f"Login falhou. Credencial '{credencial}' não encontrada como {tipo_usuario.title()}."}), 401
            
        # 1. Checa a Senha
        if user_data['Senha'] != senha:
            return jsonify({"status": "error", "message": "Login falhou. Senha incorreta."}), 401
            
        # 2. Checa o Código de Segurança (apenas para Professor)
        if tipo_usuario == 'PROFESSOR' and user_data['Codigo_Seguranca'] != codigo_seguranca:
             return jsonify({"status": "error", "message": "Login falhou. Código de Segurança incorreto."}), 401

        # Sucesso!
        return jsonify({
            "status": "success", 
            "message": f"Login bem-sucedido. Bem-vindo(a), {user_data['Nome_Completo']}!",
            "ra": user_data['RA'],
            "nome": user_data['Nome_Completo'],
            "tipo_usuario": user_data['Tipo_Usuario']
        }), 200

    except Exception as e:
        # Erro geral (pode ser problema de JSON, etc.)
        return jsonify({"status": "error", "message": f"Erro inesperado no servidor: {e}"}), 500

@app.route('/chat', methods=['POST'])
def handle_chat():
    """Rota principal para o chat que usa o router do Gemini."""
    try:
        data = request.get_json()
        mensagem = data.get('message')
        tipo_usuario = data.get('tipo_usuario')
        
        if not mensagem or not tipo_usuario:
            return jsonify({"status": "error", "message": "Campos 'message' e 'tipo_usuario' são obrigatórios."}), 400
            
        # Roteia e executa a lógica principal com o Gemini
        response_text = rotear_e_executar_mensagem(mensagem, tipo_usuario)
        
        return jsonify({
            "status": "success",
            "resposta": response_text
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": f"Erro na comunicação do chat: {e}"}), 500


if __name__ == '__main__':
    init_db()
    # Em ambientes de produção (Render, etc.), o Gunicorn deve chamar o app,
    # mas para teste local:
    # app.run(debug=True) # Use com debug se estiver em ambiente de dev.

