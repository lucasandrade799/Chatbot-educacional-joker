import os
import json
# --- NOVOS IMPORTS PARA POSTGRESQL ---
import psycopg2
import psycopg2.extras 
from psycopg2 import Error as Psycopg2Error
# ------------------------------------
from google import genai
from google.genai.errors import APIError
from google.genai.types import GenerateContentConfig
from flask import Flask, request, jsonify, send_file
from twilio.twiml.messaging_response import MessagingResponse
from flask_cors import CORS

# --- VARIÁVEIS DE CONFIGURAÇÃO E CHAVE API ---
API_KEY_GEMINI = os.environ.get('GEMINI_API_KEY')
# Variável de ambiente fornecida pelo serviço de DBaaS (Railway, ElephantSQL, etc.)
DATABASE_URL = os.environ.get('DATABASE_URL') 

# --- 1. SCRIPT SQL COMPLETO (ADAPTADO PARA POSTGRESQL) ---
SQL_SCRIPT_CONTENT = """
-- CRIAÇÃO DAS TABELAS
CREATE TABLE IF NOT EXISTS Alunos (
    id_aluno SERIAL PRIMARY KEY, -- SERIAL para autoincremento no PostgreSQL
    RA VARCHAR(10) NOT NULL UNIQUE,
    Nome_Completo VARCHAR(100) NOT NULL,
    Tipo_Usuario VARCHAR(10) NOT NULL DEFAULT 'Aluno',
    Codigo_Seguranca VARCHAR(6) NULL,
    Senha VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS Disciplinas (
    id_disciplina SERIAL PRIMARY KEY,
    Nome_Disciplina VARCHAR(100) NOT NULL,
    Semestre INT NOT NULL,
    Tipo_Avaliacao VARCHAR(10) NOT NULL,
    UNIQUE (Nome_Disciplina, Semestre)
);

CREATE TABLE IF NOT EXISTS Historico_Academico (
    id_registro SERIAL PRIMARY KEY,
    fk_id_aluno INT NOT NULL,
    fk_id_disciplina INT NOT NULL,
    NP1 NUMERIC(4, 2) NULL, -- NUMERIC no lugar de DECIMAL/FLOAT
    NP2 NUMERIC(4, 2) NULL,
    Media_Final NUMERIC(4, 2) NULL,
    Faltas INT NULL,
    FOREIGN KEY (fk_id_aluno) REFERENCES Alunos(id_aluno),
    FOREIGN KEY (fk_id_disciplina) REFERENCES Disciplinas(id_disciplina),
    UNIQUE (fk_id_aluno, fk_id_disciplina)
);

-- POPULANDO A TABELA DISCIPLINAS (USANDO ON CONFLICT DO NOTHING para ignorar duplicatas)
INSERT INTO Disciplinas (Nome_Disciplina, Semestre, Tipo_Avaliacao) VALUES
('Introdução à Programação', 1, 'AVAS'), 
('Lógica de Programação', 1, 'AVAS'), 
('Fundamentos de Sistemas', 1, 'AVAS'), 
('Matemática Discreta', 1, 'AVAS'), 
('Arquitetura de Computadores', 1, 'ED'), 
('Redes de Computadores', 1, 'ED'),       
('Comunicação Empresarial', 1, 'ED'),     
('Ética e Cidadania', 1, 'ED'),           
('PIM I', 1, 'PIM'), 
('Estruturas de Dados', 2, 'AVAS'),
('Banco de Dados I', 2, 'AVAS'), 
('Sistemas Operacionais', 2, 'AVAS'), 
('Álgebra Linear', 2, 'AVAS'), 
('Engenharia de Software', 2, 'ED'), 
('Gestão de Projetos', 2, 'ED'), 
('Análise de Sistemas', 2, 'ED'), 
('Tópicos Avançados', 2, 'ED'),
('PIM II', 2, 'PIM')
ON CONFLICT (Nome_Disciplina, Semestre) DO NOTHING;

-- POPULANDO A TABELA ALUNOS
INSERT INTO Alunos (RA, Nome_Completo, Tipo_Usuario, Codigo_Seguranca, Senha) VALUES
('R3487E5', 'Matheus de Assis Alves', 'Aluno', NULL, '123456'), 
('R6738H5', 'Matheus Balzi da Silva', 'Aluno', NULL, '123456'), 
('R818888', 'Lucas Gabriel da Silva Gardezan', 'Aluno', NULL, '123456'),
('H755247', 'Matheus Henrique Castro de Oliveira', 'Aluno', NULL, '123456'), 
('R848140', 'Thainanda Alves Monteiro', 'Aluno', NULL, '123456'), 
('820793', 'Lucas da Silva Andrade', 'Aluno', NULL, '123456'),
('P12345', 'Prof. Eliana', 'Professor', '010101', 'professorsenha')
ON CONFLICT (RA) DO NOTHING;

-- REGISTRO DO HISTÓRICO ACADÊMICO
INSERT INTO Historico_Academico (fk_id_aluno, fk_id_disciplina, NP1, NP2, Media_Final, Faltas)
SELECT 
    A.id_aluno, 
    D.id_disciplina,
    CASE WHEN D.Tipo_Avaliacao IN ('PIM', 'ED') THEN NULL ELSE NULL END AS NP1, 
    CASE WHEN D.Tipo_Avaliacao IN ('PIM', 'ED') THEN NULL ELSE NULL END AS NP2, 
    NULL AS Media_Final, 
    NULL AS Faltas       
FROM Alunos A
CROSS JOIN Disciplinas D
ON CONFLICT (fk_id_aluno, fk_id_disciplina) DO NOTHING;
"""

# --- INICIALIZAÇÃO DO FLASK E GEMINI ---
app = Flask(__name__)
CORS(app)
client = None

if API_KEY_GEMINI:
    try:
        client = genai.Client(api_key=API_KEY_GEMINI)
        print("✅ Cliente Gemini inicializado com sucesso.")
    except Exception as e:
        print(f"❌ Erro fatal ao inicializar o cliente Gemini. Detalhe: {e}")
else:
    print("⚠️ Chave API do Gemini ausente. A Op. 2 e o roteador não funcionarão.")


# --- 2. FUNÇÕES DE SUPORTE AO BANCO DE DADOS E CÁLCULOS (ADAPTAÇÃO PARA POSTGRESQL) ---

def init_db():
    """Cria e popula o banco de dados. Chamado apenas no início do servidor."""
    if not DATABASE_URL:
        print("❌ VARIÁVEL DATABASE_URL AUSENTE. O banco de dados PostgreSQL não pode ser inicializado.")
        exit()
        
    conn = None
    try:
        # Usa a URL de conexão
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Executa o script SQL completo
        cursor.execute(SQL_SCRIPT_CONTENT)
        
        conn.commit()
        print("✅ Banco de dados PostgreSQL verificado e pronto para uso.")
    except Psycopg2Error as e:
        print(f"❌ Erro na inicialização do banco de dados (PostgreSQL): {e}")
        # Se falhar na inicialização, o servidor não deve subir.
        exit()
    finally:
        if conn:
            conn.close()

def get_db_connection():
    """
    Retorna uma nova conexão ao banco de dados, configurada para
    retornar resultados como dicionário (RealDictCursor).
    """
    if not DATABASE_URL:
        raise Exception("DATABASE_URL não configurada.")
        
    conn = psycopg2.connect(DATABASE_URL)
    # Usa RealDictCursor para simular o comportamento de linha como dicionário
    return conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def formatar_valor(valor):
    """Auxiliar para formatar números ou retornar None."""
    if valor is None:
        return None
    try:
        # Garante que o valor seja tratado como float antes de formatar
        return f"{float(valor):.2f}"
    except (ValueError, TypeError):
        return None

def calcular_media_final(np1, np2, pim_nota):
    """
    Calcula a média final usando a fórmula: (NP1*4 + NP2*4 + PIM*2) / 10
    Retorna float se cálculo possível, senão None.
    """
    if np1 is None or np2 is None or pim_nota is None:
        return None  # Não é possível calcular
    try:
        np1 = float(np1)
        np2 = float(np2)
        pim_nota = float(pim_nota)
        media = (np1 * 4 + np2 * 4 + pim_nota * 2) / 10
        return round(media, 2)
    except (ValueError, TypeError):
        return None
    
def _get_pim_nota(conn, cursor, id_aluno, semestre):
    """Busca a nota PIM de um aluno para um semestre específico."""
    pim_sql = """
    SELECT H.Media_Final 
    FROM Historico_Academico H
    JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
    WHERE H.fk_id_aluno = %s AND D.Semestre = %s AND D.Tipo_Avaliacao = 'PIM'
    """
    # %s é o placeholder para psycopg2
    cursor.execute(pim_sql, (id_aluno, semestre))
    pim_result = cursor.fetchone()
    # A nota PIM é armazenada no campo Media_Final da disciplina PIM
    return pim_result['media_final'] if pim_result and pim_result['media_final'] is not None else None

def _recalcular_e_salvar_media_avas(conn, cursor, id_aluno, nome_disciplina):
    """
    Busca NP1, NP2 e PIM (do semestre) e recalcula/salva a Media_Final
    para uma disciplina AVAS.
    """
    sql_dados = """
    SELECT 
        H.id_registro, H.NP1, H.NP2, D.Semestre
    FROM Historico_Academico H
    JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
    WHERE H.fk_id_aluno = %s AND D.Nome_Disciplina = %s AND D.Tipo_Avaliacao = 'AVAS';
    """
    cursor.execute(sql_dados, (id_aluno, nome_disciplina))
    reg = cursor.fetchone()

    if not reg:
        return False, "Disciplina não encontrada ou não é AVAS."

    # Busca a nota PIM com o cursor atual
    pim_nota = _get_pim_nota(conn, cursor, id_aluno, reg['semestre'])
    
    media = calcular_media_final(reg['np1'], reg['np2'], pim_nota)
    
    # Salva a nova média, ou NULL se não puder ser calculada
    sql_update = """
    UPDATE Historico_Academico SET Media_Final = %s WHERE id_registro = %s
    """
    cursor.execute(sql_update, (media, reg['id_registro']))
    conn.commit()
    
    return True, media


def _recalcular_todas_medias_avas_do_semestre(conn, cursor, id_aluno, semestre):
    """
    Recalcula a média de TODAS as disciplinas AVAS de um semestre,
    usando a nova nota PIM.
    """
    # Busca a nota PIM com o cursor atual
    pim_nota = _get_pim_nota(conn, cursor, id_aluno, semestre)
    
    sql_disciplinas_avas = """
    SELECT 
        H.id_registro, H.NP1, H.NP2, D.Nome_Disciplina
    FROM Historico_Academico H
    JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
    WHERE H.fk_id_aluno = %s AND D.Semestre = %s AND D.Tipo_Avaliacao = 'AVAS';
    """
    cursor.execute(sql_disciplinas_avas, (id_aluno, semestre))
    registros_avas = cursor.fetchall()
    
    if not registros_avas:
        return 0
        
    for reg in registros_avas:
        media = calcular_media_final(reg['np1'], reg['np2'], pim_nota)
        
        sql_update = """
        UPDATE Historico_Academico SET Media_Final = %s WHERE id_registro = %s
        """
        cursor.execute(sql_update, (media, reg['id_registro']))
        
    conn.commit()
    return len(registros_avas)


# --- 3. FUNÇÕES DE OPERAÇÃO (LÓGICA CORE: Leitura e Escrita - Adaptação de Queries) ---

# --- OPERAÇÕES DE ESCRITA (Professor Tools) ---

def lancar_nota_np_api(ra_aluno: str, nome_disciplina: str, np_qual: str, nota: float) -> dict:
    """Lança a nota NP1 ou NP2 e recalcula a Média Final se possível."""
    ra_aluno = ra_aluno.strip().upper()
    nome_disciplina = nome_disciplina.strip()
    np_qual = np_qual.strip().upper()

    if np_qual not in ['NP1', 'NP2'] or not (0.0 <= nota <= 10.0):
        return {"status": "error", "message": "Parâmetros inválidos. Use NP1 ou NP2 com nota entre 0.0 e 10.0."}
    
    conn, cursor = get_db_connection()
    
    try:
        # 1. Obter IDs e checar se é AVAS
        sql_info = """
        SELECT A.id_aluno, D.Tipo_Avaliacao 
        FROM Alunos A
        JOIN Historico_Academico H ON A.id_aluno = H.fk_id_aluno
        JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
        WHERE A.RA = %s AND D.Nome_Disciplina = %s;
        """
        cursor.execute(sql_info, (ra_aluno, nome_disciplina))
        info = cursor.fetchone()

        if not info:
            conn.close()
            return {"status": "error", "message": f"Aluno/Disciplina '{ra_aluno}'/'{nome_disciplina}' não encontrados."}
        
        if info['tipo_avaliacao'] != 'AVAS':
            conn.close()
            return {"status": "error", "message": f"Lançamento de NP1/NP2 só é permitido para matérias AVAS. '{nome_disciplina}' é {info['tipo_avaliacao']}."}

        # 2. Atualizar nota NP
        # IMPORTANTE: No PostgreSQL, a substituição de %s só funciona para valores, não para nomes de colunas.
        # Por isso, o nome da coluna é injetado diretamente (cuidado com SQL Injection, mas neste caso o valor é controlado)
        sql_update_np = f"""
        UPDATE Historico_Academico 
        SET {np_qual} = %s
        WHERE fk_id_aluno = %s 
        AND fk_id_disciplina = (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = %s);
        """
        cursor.execute(sql_update_np, (nota, info['id_aluno'], nome_disciplina))

        # 3. Recalcular e salvar Media_Final (se possível)
        sucesso, media = _recalcular_e_salvar_media_avas(conn, cursor, info['id_aluno'], nome_disciplina)
        
        conn.close()

        status_media = f"Média Final calculada e salva: {media:.2f}" if media is not None else "Média Final pendente (PIM ou outra NP faltando)."
        return {"status": "success", "message": f"Nota {np_qual} ({nota:.2f}) lançada para {nome_disciplina} ({ra_aluno}). {status_media}"}

    except Psycopg2Error as e:
        conn.close()
        return {"status": "error", "message": f"Erro no lançamento da nota NP: {e}"}

def lancar_nota_pim_api(ra_aluno: str, nome_disciplina_pim: str, nota: float) -> dict:
    """Lança a nota PIM e recalcula a Média Final de todas as AVAS do semestre."""
    ra_aluno = ra_aluno.strip().upper()
    nome_disciplina_pim = nome_disciplina_pim.strip()

    if not (0.0 <= nota <= 10.0):
        return {"status": "error", "message": "Nota PIM inválida. Deve estar entre 0.0 e 10.0."}
    
    conn, cursor = get_db_connection()
    
    try:
        # 1. Obter IDs e checar se é PIM
        sql_info = """
        SELECT A.id_aluno, D.Tipo_Avaliacao, D.Semestre
        FROM Alunos A
        JOIN Historico_Academico H ON A.id_aluno = H.fk_id_aluno
        JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
        WHERE A.RA = %s AND D.Nome_Disciplina = %s;
        """
        cursor.execute(sql_info, (ra_aluno, nome_disciplina_pim))
        info = cursor.fetchone()

        if not info:
            conn.close()
            return {"status": "error", "message": f"Aluno/Disciplina PIM '{ra_aluno}'/'{nome_disciplina_pim}' não encontrados."}
        
        if info['tipo_avaliacao'] != 'PIM':
            conn.close()
            return {"status": "error", "message": f"'{nome_disciplina_pim}' não é uma disciplina PIM."}

        # 2. Atualizar nota PIM (que fica no campo Media_Final)
        sql_update_pim = """
        UPDATE Historico_Academico 
        SET Media_Final = %s
        WHERE fk_id_aluno = %s
        AND fk_id_disciplina = (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = %s);
        """
        cursor.execute(sql_update_pim, (nota, info['id_aluno'], nome_disciplina_pim))

        # 3. Recalcular e salvar Media_Final para todas as AVAS do semestre
        count_avas = _recalcular_todas_medias_avas_do_semestre(conn, cursor, info['id_aluno'], info['semestre'])
        
        conn.close()

        return {"status": "success", "message": f"Nota PIM ({nota:.2f}) lançada para o semestre {info['semestre']} ({ra_aluno}). {count_avas} Média(s) Final(is) AVAS recalculada(s)."}

    except Psycopg2Error as e:
        conn.close()
        return {"status": "error", "message": f"Erro no lançamento da nota PIM: {e}"}

def marcar_ed_concluido_api(ra_aluno: str, nome_disciplina_ed: str) -> dict:
    """Marca uma disciplina ED como 'Feito' (usando Media_Final = 1.0 como flag)."""
    ra_aluno = ra_aluno.strip().upper()
    nome_disciplina_ed = nome_disciplina_ed.strip()

    conn, cursor = get_db_connection()

    try:
        # 1. Obter IDs e checar se é ED
        sql_info = """
        SELECT A.id_aluno, D.Tipo_Avaliacao 
        FROM Alunos A
        JOIN Historico_Academico H ON A.id_aluno = H.fk_id_aluno
        JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
        WHERE A.RA = %s AND D.Nome_Disciplina = %s;
        """
        cursor.execute(sql_info, (ra_aluno, nome_disciplina_ed))
        info = cursor.fetchone()

        if not info:
            conn.close()
            return {"status": "error", "message": f"Aluno/Disciplina '{ra_aluno}'/'{nome_disciplina_ed}' não encontrados."}
        
        if info['tipo_avaliacao'] != 'ED':
            conn.close()
            return {"status": "error", "message": f"'{nome_disciplina_ed}' não é uma disciplina ED. Só é possível marcar status de conclusão para ED."}

        # 2. Atualizar status (Media_Final = 1.0 como flag de conclusão)
        sql_update_ed = """
        UPDATE Historico_Academico 
        SET Media_Final = 1.0
        WHERE fk_id_aluno = %s
        AND fk_id_disciplina = (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = %s);
        """
        cursor.execute(sql_update_ed, (info['id_aluno'], nome_disciplina_ed))
        conn.commit()
        conn.close()

        return {"status": "success", "message": f"Estudo Disciplinar '{nome_disciplina_ed}' marcado como concluído para o aluno {ra_aluno}."}

    except Psycopg2Error as e:
        conn.close()
        return {"status": "error", "message": f"Erro ao marcar ED como concluído: {e}"}

def lancar_faltas_api(ra_aluno: str, nome_disciplina: str, faltas: int) -> dict:
    """Lança o número de faltas para uma disciplina."""
    ra_aluno = ra_aluno.strip().upper()
    nome_disciplina = nome_disciplina.strip()

    if faltas < 0:
        return {"status": "error", "message": "Número de faltas inválido."}
    
    conn, cursor = get_db_connection()

    try:
        # 1. Obter IDs e checar se pode ter falta
        sql_info = """
        SELECT A.id_aluno, D.Tipo_Avaliacao 
        FROM Alunos A
        JOIN Historico_Academico H ON A.id_aluno = H.fk_id_aluno
        JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
        WHERE A.RA = %s AND D.Nome_Disciplina = %s;
        """
        cursor.execute(sql_info, (ra_aluno, nome_disciplina))
        info = cursor.fetchone()

        if not info:
            conn.close()
            return {"status": "error", "message": f"Aluno/Disciplina '{ra_aluno}'/'{nome_disciplina}' não encontrados."}
        
        # 2. Atualizar faltas
        sql_update_faltas = """
        UPDATE Historico_Academico 
        SET Faltas = %s
        WHERE fk_id_aluno = %s
        AND fk_id_disciplina = (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = %s);
        """
        cursor.execute(sql_update_faltas, (faltas, info['id_aluno'], nome_disciplina))
        conn.commit()
        conn.close()
        
        aviso = ""
        if info['tipo_avaliacao'] in ['AVAS', 'PIM', 'ED']:
             aviso = f" (AVISO: '{nome_disciplina}' é {info['tipo_avaliacao']} e não costuma ter controle de faltas, mas o registro foi salvo.)"

        return {"status": "success", "message": f"Lançadas {faltas} faltas para '{nome_disciplina}' ({ra_aluno}).{aviso}"}

    except Psycopg2Error as e:
        conn.close()
        return {"status": "error", "message": f"Erro no lançamento de faltas: {e}"}


# --- OPERAÇÃO DE LEITURA (Consulta) ---

def verificar_dados_curso_api(ra_aluno: str) -> dict:
    """OPERAÇÃO 1: Busca o histórico ajustado para as regras de PIM/ED/AVAS."""
    ra_aluno = ra_aluno.strip().upper()

    comando_sql_join = """
    SELECT
    A.Nome_Completo, A.id_aluno, D.Nome_Disciplina, D.Semestre, D.Tipo_Avaliacao,
    H.NP1, H.NP2, H.Media_Final, H.Faltas
    FROM Historico_Academico H
    JOIN Alunos A ON H.fk_id_aluno = A.id_aluno
    JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
    WHERE A.RA = %s
    ORDER BY D.Semestre, D.Tipo_Avaliacao DESC, D.Nome_Disciplina;
    """

    conn, cursor = get_db_connection()

    try:
        cursor.execute(comando_sql_join, (ra_aluno,))
        registros = cursor.fetchall()

        if not registros:
            # Tenta buscar se o RA existe, mesmo sem histórico
            cursor.execute("SELECT Nome_Completo, Tipo_Usuario FROM Alunos WHERE RA = %s", (ra_aluno,))
            info_user = cursor.fetchone()
            
            conn.close()
            
            if info_user:
                 return {"status": "error", "message": f"O usuário '{info_user['nome_completo']}' ({ra_aluno}) não possui histórico acadêmico registrado."}
            
            return {"status": "error", "message": f"A credencial '{ra_aluno}' não foi encontrada."}

        historico = []
        id_aluno = registros[0]['id_aluno']

        for reg in registros:
            # Atenção: as chaves são minúsculas no RealDictCursor!
            tipo = reg['tipo_avaliacao'].upper()
            
            np1_val = formatar_valor(reg['np1'])
            np2_val = formatar_valor(reg['np2'])
            media_val = formatar_valor(reg['media_final'])
            faltas_val = reg['faltas'] if reg['faltas'] is not None else None

            disciplina_info = {
                "disciplina": reg['nome_disciplina'],
                "semestre": reg['semestre'],
                "tipo_avaliacao": tipo,
            }

            if tipo == 'PIM':
                # PIM: Somente uma nota (Media_Final).
                disciplina_info.update({
                    "nota_pim": media_val if media_val is not None else "Indefinida",
                    "np1": "N/A",
                    "np2": "N/A",
                    "media_final": "N/A", 
                    "faltas": "N/A",
                    "observacao": "Nota de trabalho que compõe a média de todas as matérias AVAS do semestre."
                })
            elif tipo == 'ED':
                # ED: Apenas status de conclusão (Media_Final != NULL -> Feito).
                status_ed = "Feito" if reg['media_final'] is not None else "Não Feito"
                
                disciplina_info.update({
                    "status_conclusao": status_ed,
                    "np1": "N/A",
                    "np2": "N/A",
                    "media_final": "N/A",
                    "faltas": "N/A",
                    "observacao": "Obrigatória, sem nota. Status: Feito/Não Feito."
                })
            elif tipo == 'AVAS':
                
                # O cursor aqui é do tipo RealDictCursor. Preciso passá-lo para a função interna.
                pim_nota_semestre = _get_pim_nota(conn, cursor, id_aluno, reg['semestre'])
                media_display = media_val
                
                # Se a Media_Final não estiver salva, tenta calcular dinamicamente
                if reg['media_final'] is None:
                    # Atenção: np1 e np2 vêm como objetos Decimal do PostgreSQL, precisam ser convertidos para float antes do cálculo
                    calculated_media = calcular_media_final(reg['np1'], reg['np2'], pim_nota_semestre)
                    media_display = formatar_valor(calculated_media) if calculated_media is not None else "Indefinida"
                
                # Trata faltas: se for NULL, exibe 'N/A'
                faltas_exibicao = faltas_val if faltas_val is not None else "N/A"
                
                disciplina_info.update({
                    "np1": np1_val if np1_val is not None else "Indefinida",
                    "np2": np2_val if np2_val is not None else "Indefinida",
                    "nota_pim_usada": formatar_valor(pim_nota_semestre) if pim_nota_semestre is not None else "Indefinida",
                    "media_final": media_display,
                    "faltas": faltas_exibicao,
                    "observacao": "Média calculada com PIM. Matéria Online (sem controle de faltas obrigatório)."
                })
            else: # Outros tipos
                disciplina_info.update({
                    "np1": np1_val if np1_val is not None else "Indefinida",
                    "np2": np2_val if np2_val is not None else "Indefinida",
                    "media_final": media_val if media_val is not None else "Indefinida",
                    "faltas": faltas_val if faltas_val is not None else "Indefinidas"
                })
                
            historico.append(disciplina_info)

        conn.close()
        return {
            "status": "success",
            "aluno": registros[0]['nome_completo'],
            "ra": ra_aluno,
            "historico": historico,
            "nota_pim_info": "AVAS: Média Final = (NP1*4 + NP2*4 + PIM*2) / 10."
        }

    except Psycopg2Error as e:
        conn.close()
        return {"status": "error", "message": f"Erro na consulta ao banco de dados (PostgreSQL): {e}"}


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
        "Encaminhe todo o material gerado sob as especificações acima para o usuário para que ele possa vizualizar tudo e estudar."
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
            "Você é um assistente acadêmico para um **Professor**. Responda com um tom sarcástico, mas sempre respeitoso e informativo, usando a personalidade do 'Joker' (Persona 5). "
            "Suas principais tarefas são: 1. Ajudar o professor a visualizar dados acadêmicos. 2. Gerar material de estudo. 3. **Lançar notas (NP1, NP2, PIM) e faltas e marcar ED como concluído no sistema.** "
            "Ao lançar notas, garanta que todos os 4 parâmetros (RA, Disciplina, NP/PIM e Nota) estejam claros e use a função apropriada. Informe a ele que o sistema calcula a média AVAS automaticamente após ter NP1, NP2 e PIM."
        )
    else: # Aluno
        # ALUNO: Acesso restrito (Somente Leitura de Histórico e Geração de Material)
        ferramentas_permitidas = [
            TOOLS['verificar_historico_academico'], 
            TOOLS['gerar_material_estudo']
        ]
        instrucoes_perfil = (
            "Você é um assistente acadêmico para um **Aluno**. Responda com um tom sarcástico, mas sempre informativo, usando a personalidade do 'Joker'(Persona 5). "
            "Suas principais tarefas são: 1. Ajudar o aluno a verificar o próprio histórico. 2. Gerar material de estudo. **(Você NÃO pode lançar ou alterar notas.)**"
        )
        
    prompt_ferramenta = (
        f"{instrucoes_perfil}\n\n"
        "O usuário enviou a seguinte mensagem: '{}'. \n\n"
        "**Instruções para Ferramentas:**\n"
        "1. Se o usuário pedir especificamente por um RA, notas ou histórico, use 'verificar_dados_curso_api'.\n"
        "2. Se o usuário pedir um material de estudo/resumo/explicação sobre um tópico, use 'buscar_material_estudo_api'.\n"
        "3. Se o professor pedir para lançar NP1/NP2, use 'lancar_nota_np'.\n"
        "4. Se o professor pedir para lançar PIM, use 'lancar_nota_pim'.\n"
        "5. Se o professor pedir para marcar ED como concluído, use 'marcar_ed_concluido'.\n"
        "6. Se o professor pedir para lançar faltas, use 'lancar_faltas'.\n"
        "7. Para **qualquer outra pergunta abrangente** ou se a função for desnecessária/impossível, **RESPONDA DIRETAMENTE**.\n"
        "Em caso de dados faltantes (ex: RA), peça-os. \n\n"
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
            function_response_data = TOOLS[func_name](**func_args)

            # Se a busca/lançamento SQL falhar, retorna o erro diretamente.
            if function_response_data.get('status') == 'error':
                return f"Joker: Oops! {function_response_data['message']}"

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
    conn = None
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

        conn, cursor = get_db_connection()
        aluno_info = None
        senha_valida = False # Define como falso por padrão

        if tipo_usuario == 'ALUNO':
            # 1. Lógica para Aluno: verifica RA, Tipo e Senha
            comando_sql_aluno = "SELECT Nome_Completo, Tipo_Usuario, Senha FROM Alunos WHERE RA = %s AND Tipo_Usuario = 'Aluno'"
            cursor.execute(comando_sql_aluno, (credencial,))
            aluno_info = cursor.fetchone()
            
            # Verifica se encontrou o aluno E se a senha confere
            if aluno_info and aluno_info['senha'] == senha:
                senha_valida = True
            
        elif tipo_usuario == 'PROFESSOR':
            # 2. Lógica para Professor: verifica 3 campos
            if not codigo_seguranca or len(codigo_seguranca) != 6:
                 conn.close()
                 return jsonify({"status": "error", "message": "Código de Segurança inválido. Deve ter 6 dígitos."}), 401

            comando_sql_prof = """
            SELECT Nome_Completo, Tipo_Usuario, Codigo_Seguranca, Senha 
            FROM Alunos 
            WHERE RA = %s AND Tipo_Usuario = 'Professor'
            """
            cursor.execute(comando_sql_prof, (credencial,))
            prof_data = cursor.fetchone()
            
            if prof_data:
                # 3. Verifica o Código de Segurança E a Senha do Professor
                if prof_data['codigo_seguranca'] == codigo_seguranca and prof_data['senha'] == senha:
                    aluno_info = prof_data
                    senha_valida = True

        else:
             conn.close()
             return jsonify({"status": "error", "message": "Tipo de usuário inválido."}), 400

        conn.close()

        if aluno_info and senha_valida:
            # Login bem-sucedido (simulação)
            return jsonify({
                "status": "success", 
                "message": "Login bem-sucedido.", 
                "user": {
                    "ra": credencial, 
                    "nome": aluno_info['nome_completo'],
                    "tipo_usuario": aluno_info['tipo_usuario'].lower() 
                }
            }), 200
        else:
            # Falha na autenticação
            return jsonify({"status": "error", "message": "Credenciais (RA/Funcional, Senha ou Código) inválidas."}), 401

    except Psycopg2Error as e:
        print(f"❌ Erro na rota /login (PostgreSQL): {e}")
        return jsonify({"status": "error", "message": "Erro de conexão/consulta ao banco de dados."}), 500
    except Exception as e:
        print(f"❌ Erro na rota /login: {e}")
        return jsonify({"status": "error", "message": "Erro interno do servidor."}), 500
    finally:
        if conn:
            conn.close()


@app.route('/')
def serve_index():
    """Serva o arquivo joker_bot.html principal, que está na raiz."""
    return send_file('joker_bot.html')

@app.route('/web_router', methods=['POST'])
def handle_web_message():
    """Endpoint que recebe a mensagem do usuário do Front-end Web."""
    try:
        data = request.get_json()
        message_text = data.get('message')
        tipo_usuario = data.get('tipo_usuario', 'aluno') 

        if not message_text:
            return jsonify({"status": "error", "message": "Mensagem de texto não fornecida."}), 400

        print(f"🌐 Mensagem recebida de {tipo_usuario.upper()}: {message_text}")

        resposta_final_texto = rotear_e_executar_mensagem(message_text, tipo_usuario)

        return jsonify({
            "status": "success",
            "message": resposta_final_texto
        }), 200

    except Exception as e:
        print(f"❌ Erro no Web Router: {e}")
        return jsonify({"status": "error", "message": f"Erro interno do servidor: {e}"}), 500


@app.route('/whatsapp_webhook', methods=['POST'])
def handle_whatsapp_message():
    """Endpoint que recebe a mensagem do usuário do WhatsApp via Webhook da Twilio."""

    message_text = request.form.get('Body')
    TIPO_USUARIO_WHATSAPP = 'aluno' 

    if not message_text:
        return str(MessagingResponse()), 200

    print(f"💬 Mensagem recebida da Twilio: {message_text}")

    resposta_final_texto = rotear_e_executar_mensagem(message_text, TIPO_USUARIO_WHATSAPP)

    resp = MessagingResponse()
    resp.message(resposta_final_texto)
    return str(resp)


# --- EXECUÇÃO PRINCIPAL ---
init_db()

if __name__ == '__main__':
    app.run(debug=True)


