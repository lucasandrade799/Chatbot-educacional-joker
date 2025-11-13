import os
import json
# --- IMPORTS PARA POSTGRESQL ---
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
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_PUBLIC_URL')

# --- FLAG GLOBAL DE ESTABILIDADE (NOVO) ---
DB_INITIALIZED = False
# --- VARIÁVEL GLOBAL DE NOTA DE CORTE ---
NOTA_CORTE_APROVACAO = 7.0 # Nota de corte final: 7.0

# --- 1. SCRIPT SQL COMPLETO ---
# CRUCIAL: Mantém a inicialização das EDs com uma nota (Media_Final = 6.0), mas o status de "Completa"
# será fixo na função de leitura.
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
    -- Tipo_Avaliacao: 'TEORICA' (Padrão), 'PIM' ou 'ED'
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

-- POPULANDO A TABELA DISCIPLINAS
INSERT INTO Disciplinas (Nome_Disciplina, Semestre, Tipo_Avaliacao) VALUES
('Introdução à Programação', 1, 'TEORICA'), 
('Lógica de Programação', 1, 'TEORICA'), 
('Fundamentos de Sistemas', 1, 'TEORICA'), 
('Matemática Discreta', 1, 'TEORICA'), 
('Arquitetura de Computadores', 1, 'ED'), 
('Redes de Computadores', 1, 'ED'), 
('Comunicação Empresarial', 1, 'ED'), 
('Ética e Cidadania', 1, 'ED'), 
('PIM Semestre 1', 1, 'PIM'), 
('Estruturas de Dados', 2, 'TEORICA'),
('Banco de Dados I', 2, 'TEORICA'), 
('Sistemas Operacionais', 2, 'TEORICA'), 
('Álgebra Linear', 2, 'TEORICA'), 
('Engenharia de Software', 2, 'ED'), 
('Gestão de Projetos', 2, 'ED'), 
('Análise de Sistemas', 2, 'ED'), 
('Tópicos Avançados', 2, 'ED'),
('PIM Semestre 2', 2, 'PIM')
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
    NULL::NUMERIC AS NP1, 
    NULL::NUMERIC AS NP2, 
    CASE
        -- Mantém a nota para EDs na inicialização, mas o status será determinado de forma fixa
        WHEN D.Tipo_Avaliacao = 'ED' THEN 6.0 
        ELSE NULL::NUMERIC
    END AS Media_Final, 
    NULL::INT AS Faltas       
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


# --- 2. FUNÇÕES DE SUPORTE AO BANCO DE DADOS E CÁLCULOS ---

def init_db():
    """Cria e popula o banco de dados. Chamado apenas uma vez, na primeira requisição."""
    if not DATABASE_URL:
        print("❌ ERRO CRÍTICO: VARIÁVEL DATABASE_URL AUSENTE. O banco de dados PostgreSQL não pode ser inicializado.")
        return False
        
    conn = None
    try:
        print("⏳ Tentando conectar e inicializar o banco de dados PostgreSQL...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(SQL_SCRIPT_CONTENT)
        conn.commit()
        print("✅ Banco de dados PostgreSQL verificado e pronto para uso.")
        return True
    except Psycopg2Error as e:
        print(f"❌ ERRO GRAVE na inicialização do banco de dados (PostgreSQL): {e}")
        return False 
    finally:
        if conn:
            conn.close()

def get_db_connection():
    """Retorna uma nova conexão ao banco de dados."""
    if not DATABASE_URL:
        raise Exception("ERRO: DATABASE_URL não configurada. Conexão ao DB falhou.")
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    except Psycopg2Error as e:
        raise Exception(f"ERRO DE CONEXÃO AO POSTGRESQL: Não foi possível conectar ao DB. Detalhe: {e}")
    except Exception as e:
        raise Exception(f"ERRO DESCONHECIDO NA CONEXÃO AO DB: {e}")


def formatar_valor(valor):
    """Auxiliar para formatar números ou retornar None."""
    if valor is None:
        return None
    try:
        return f"{float(valor):.2f}"
    except (ValueError, TypeError):
        return None

def calcular_media_final(np1, np2, pim_nota):
    """Calcula a média final usando a fórmula: (NP1*4 + NP2*4 + PIM*2) / 10"""
    if np1 is None or np2 is None or pim_nota is None:
        return None 
    try:
        np1 = float(np1)
        np2 = float(np2)
        pim_nota = float(pim_nota)
        # Nota: O cálculo usa a fórmula unificada para EDs e TEÓRICAS
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
    cursor.execute(pim_sql, (id_aluno, semestre))
    pim_result = cursor.fetchone()
    return pim_result['media_final'] if pim_result and pim_result['media_final'] is not None else None

def _recalcular_e_salvar_media_geral(conn, cursor, id_aluno, nome_disciplina):
    """Recalcula e salva a Media_Final para QUALQUER disciplina que não seja PIM."""
    sql_dados = """
    SELECT 
        H.id_registro, H.NP1, H.NP2, D.Semestre, D.Tipo_Avaliacao
    FROM Historico_Academico H
    JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
    WHERE H.fk_id_aluno = %s AND D.Nome_Disciplina = %s AND D.Tipo_Avaliacao != 'PIM';
    """
    cursor.execute(sql_dados, (id_aluno, nome_disciplina))
    reg = cursor.fetchone()

    if not reg:
        return False, "Disciplina não encontrada ou é PIM."

    pim_nota = _get_pim_nota(conn, cursor, id_aluno, reg['semestre'])
    media = calcular_media_final(reg['np1'], reg['np2'], pim_nota)
    
    sql_update = """
    UPDATE Historico_Academico SET Media_Final = %s WHERE id_registro = %s
    """
    cursor.execute(sql_update, (media, reg['id_registro']))
    conn.commit()
    
    return True, media


def _recalcular_todas_medias_do_semestre(conn, cursor, id_aluno, semestre):
    """Recalcula a média de TODAS as disciplinas (que não são PIM) de um semestre, usando a nova nota PIM."""
    pim_nota = _get_pim_nota(conn, cursor, id_aluno, semestre)
    
    sql_disciplinas_calculo = """
    SELECT 
        H.id_registro, H.NP1, H.NP2, D.Nome_Disciplina
    FROM Historico_Academico H
    JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
    WHERE H.fk_id_aluno = %s AND D.Semestre = %s AND D.Tipo_Avaliacao != 'PIM';
    """
    cursor.execute(sql_disciplinas_calculo, (id_aluno, semestre))
    registros_calculo = cursor.fetchall()
    
    if not registros_calculo:
        return 0
        
    for reg in registros_calculo:
        media = calcular_media_final(reg['np1'], reg['np2'], pim_nota)
        
        sql_update = """
        UPDATE Historico_Academico SET Media_Final = %s WHERE id_registro = %s
        """
        cursor.execute(sql_update, (media, reg['id_registro']))
        
    conn.commit()
    return len(registros_calculo)


# --- 3. FUNÇÕES DE OPERAÇÃO (LÓGICA CORE: Leitura e Escrita) ---

# --- OPERAÇÕES DE ESCRITA (Professor Tools) ---

def lancar_nota_np_api(ra_aluno: str, nome_disciplina: str, np_qual: str, nota: float) -> dict:
    """Lança a nota NP1 ou NP2 e recalcula a Média Final se possível."""
    ra_aluno = ra_aluno.upper().strip()
    nome_disciplina = nome_disciplina.strip()
    np_qual = np_qual.upper().strip()

    if np_qual not in ['NP1', 'NP2'] or not (0.0 <= nota <= 10.0):
        return {"status": "error", "message": "Parâmetros inválidos. Use NP1 ou NP2 com nota entre 0.0 e 10.0."}
    
    conn, cursor = get_db_connection()
    
    try:
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
        
        if info['tipo_avaliacao'] == 'PIM':
            conn.close()
            return {"status": "error", "message": f"Lançamento de NP1/NP2 não permitido para disciplinas do tipo PIM. Use a função de lançamento PIM."}

        sql_update_np = f"""
        UPDATE Historico_Academico 
        SET {np_qual} = %s
        WHERE fk_id_aluno = %s 
        AND fk_id_disciplina = (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = %s);
        """
        cursor.execute(sql_update_np, (nota, info['id_aluno'], nome_disciplina))

        sucesso, media = _recalcular_e_salvar_media_geral(conn, cursor, info['id_aluno'], nome_disciplina)
        
        conn.close()

        status_media = f"Média Final calculada e salva: {media:.2f}" if media is not None else "Média Final pendente (PIM ou outra NP faltando)."
        return {"status": "success", "message": f"Nota {np_qual} ({nota:.2f}) lançada para {nome_disciplina} ({ra_aluno}). {status_media}"}

    except Psycopg2Error as e:
        conn.close()
        return {"status": "error", "message": f"Erro no lançamento da nota NP: {e}"}

def lancar_nota_pim_api(ra_aluno: str, nome_disciplina_pim: str, nota: float) -> dict:
    """Lança a nota PIM e recalcula a Média Final de todas as disciplinas do semestre."""
    ra_aluno = ra_aluno.upper().strip()
    nome_disciplina_pim = nome_disciplina_pim.strip()

    if not (0.0 <= nota <= 10.0):
        return {"status": "error", "message": "Nota PIM inválida. Deve estar entre 0.0 e 10.0."}
    
    conn, cursor = get_db_connection()
    
    try:
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
            return {"status": "error", "message": f"'{nome_disciplina_pim}' não é uma disciplina PIM. - Joker."}

        sql_update_pim = """
        UPDATE Historico_Academico 
        SET Media_Final = %s
        WHERE fk_id_aluno = %s
        AND fk_id_disciplina = (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = %s);
        """
        cursor.execute(sql_update_pim, (nota, info['id_aluno'], nome_disciplina_pim))

        count_calculadas = _recalcular_todas_medias_do_semestre(conn, cursor, info['id_aluno'], info['semestre'])
        
        conn.close()

        return {"status": "success", "message": f"Nota PIM ({nota:.2f}) lançada para o semestre {info['semestre']} ({ra_aluno}). {count_calculadas} Média(s) Final(is) recalculada(s). (Incluindo EDs)."}

    except Psycopg2Error as e:
        conn.close()
        return {"status": "error", "message": f"Erro no lançamento da nota PIM: {e}"}

def lancar_faltas_api(ra_aluno: str, nome_disciplina: str, faltas: int) -> dict:
    """Lança o número de faltas para uma disciplina."""
    ra_aluno = ra_aluno.upper().strip()
    nome_disciplina = nome_disciplina.strip()

    if faltas < 0:
        return {"status": "error", "message": "Número de faltas inválido."}
    
    conn, cursor = get_db_connection()

    try:
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
        if info['tipo_avaliacao'] == 'PIM':
              aviso = f" (AVISO: '{nome_disciplina}' é PIM e pode não ter controle de faltas.)"

        return {"status": "success", "message": f"Lançadas {faltas} faltas para '{nome_disciplina}' ({ra_aluno}).{aviso}"}

    except Psycopg2Error as e:
        conn.close()
        return {"status": "error", "message": f"Erro no lançamento de faltas: {e}"}


# --- OPERAÇÃO DE LEITURA (Consulta) ---

def verificar_dados_curso_api(ra_aluno: str) -> dict:
    """Busca o histórico ajustado com a nova regra de corte (7.0)."""
    global NOTA_CORTE_APROVACAO
    ra_aluno = ra_aluno.upper().strip()

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
            cursor.execute("SELECT Nome_Completo, Tipo_Usuario FROM Alunos WHERE RA = %s", (ra_aluno,))
            info_user = cursor.fetchone()
            
            conn.close()
            
            if info_user:
                return {"status": "error", "message": f"O usuário '{info_user['nome_completo']}' ({ra_aluno}) não possui histórico acadêmico registrado."}
            
            return {"status": "error", "message": f"A credencial '{ra_aluno}' não foi encontrada."}

        historico = []
        id_aluno = registros[0]['id_aluno']

        for reg in registros:
            tipo = reg['tipo_avaliacao'].upper()
            
            np1_val = formatar_valor(reg['np1'])
            np2_val = formatar_valor(reg['np2'])
            media_val = formatar_valor(reg['media_final'])
            faltas_val = reg['faltas'] if reg['faltas'] is not None else None
            pim_nota_semestre = _get_pim_nota(conn, cursor, id_aluno, reg['semestre'])

            disciplina_info = {
                "disciplina": reg['nome_disciplina'],
                "semestre": reg['semestre'],
                "tipo_avaliacao": tipo,
            }

            if tipo == 'PIM':
                # PIM: Não tem NP1/NP2 e a nota fica em Media_Final.
                disciplina_info.update({
                    "nota_pim": media_val if media_val is not None else "Indefinida",
                    "np1": "N/A",
                    "np2": "N/A",
                    "media_final": "N/A", 
                    "faltas": "N/A",
                    "observacao": "Nota de trabalho que compõe a média de todas as matérias do semestre."
                })
            else: # TEORICA e ED
                
                media_display = media_val
                
                # Recalcula a média se não estiver salva (depende de NP1, NP2 e PIM)
                if reg['media_final'] is None:
                    calculated_media = calcular_media_final(reg['np1'], reg['np2'], pim_nota_semestre)
                    media_display = formatar_valor(calculated_media) if calculated_media is not None else "Indefinida"
                
                faltas_exibicao = faltas_val if faltas_val is not None else "N/A"
                
                disciplina_info.update({
                    "np1": np1_val if np1_val is not None else "Indefinida",
                    "np2": np2_val if np2_val is not None else "Indefinida",
                    "nota_pim_usada": formatar_valor(pim_nota_semestre) if pim_nota_semestre is not None else "Indefinida",
                    "media_final": media_display,
                    "faltas": faltas_exibicao,
                    "observacao": "Média calculada: (NP1*4 + NP2*4 + PIM*2) / 10."
                })
                
                # Lógica de Status:
                media_float = float(media_display) if media_display and media_display != "Indefinida" else None
                status_aprovacao = "Indefinido"

                if media_float is not None:
                    if media_float >= NOTA_CORTE_APROVACAO:
                        status_aprovacao = "Aprovado"
                    else:
                        status_aprovacao = "Reprovado"


                if tipo == 'ED':
                    # Para ED, o status de conclusão é fixo: "ED CONCLUIDO"
                    disciplina_info['status_conclusao'] = "ED CONCLUIDO"
                    disciplina_info['observacao'] = (
                        f"Estudo Disciplinar (Atividade Complementar). "
                        f"Status: **{disciplina_info['status_conclusao']}** (Status fixo). "
                        f"Média calculada para registro: {media_display} (Corte de aprovação: {NOTA_CORTE_APROVACAO:.1f})."
                    )
                else: # TEORICA
                    # Para TEÓRICAS (AVAs), o status depende da média calculada
                    disciplina_info['status_aprovacao'] = status_aprovacao
                    disciplina_info['observacao'] = (
                        f"Média calculada: (NP1*4 + NP2*4 + PIM*2) / 10. "
                        f"Status de Aprovação: **{status_aprovacao}** (Corte: {NOTA_CORTE_APROVACAO:.1f})."
                    )


            historico.append(disciplina_info)

        conn.close()
        return {
            "status": "success",
            "aluno": registros[0]['nome_completo'],
            "ra": ra_aluno,
            "historico": historico,
            "nota_pim_info": f"REGRAS: Todas as matérias (TEORICA e ED) usam PIM na média. Nota de corte para aprovação é **{NOTA_CORTE_APROVACAO:.1f}**."
        }

    except Psycopg2Error as e:
        conn.close()
        return {"status": "error", "message": f"Erro na consulta ao banco de dados (PostgreSQL): {e}"}


def buscar_material_estudo_api(topico: str) -> dict:
    """Gera material usando o Gemini e retorna a resposta."""
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
    'lancar_faltas': lancar_faltas_api 
}

def rotear_e_executar_mensagem(mensagem_usuario: str, tipo_usuario: str) -> str:
    """Usa o Gemini para interpretar a intenção do usuário (Function Calling) e executa a função apropriada."""

    if not client:
        return "❌ Desculpe, a conexão com a inteligência artificial está temporariamente indisponível."

    # 1. CONTROLE DE PERMISSÃO
    if tipo_usuario.upper() == 'PROFESSOR':
        ferramentas_permitidas = list(TOOLS.values()) 
        instrucoes_perfil = (
            "Você é um assistente acadêmico para um **Professor**. Responda com um tom sarcástico, mas sempre respeitoso e informativo, usando a personalidade do 'Joker' (Persona 5). "
            "Suas principais tarefas são: 1. Ajudar o professor a visualizar dados acadêmicos. 2. Gerar material de estudo. 3. **Lançar notas (NP1, NP2, PIM) e faltas no sistema.** OBS: O status de conclusão da ED é fixo como 'ED CONCLUIDO' e não é determinado pela média. A nota de corte para aprovação é 7.0."
        )
    else: # Aluno
        ferramentas_permitidas = [
            TOOLS['verificar_historico_academico'], 
            TOOLS['gerar_material_estudo']
        ]
        instrucoes_perfil = (
            "Você é um assistente acadêmico para um **Aluno**. Responda com um tom sarcástico, mas sempre informativo, usando a personalidade do 'Joker'(Persona 5). "
            "Suas principais tarefas são: 1. Ajudar o aluno a verificar o próprio histórico. 2. Gerar material de estudo. **(Você NÃO pode lançar ou alterar notas.)** A nota de corte para aprovação é 7.0."
        )
        
    prompt_ferramenta = (
        f"{instrucoes_perfil}\n\n"
        "O usuário enviou a seguinte mensagem: '{}'. \n\n"
        "**Instruções para Ferramentas:**\n"
        "1. Se o usuário pedir especificamente por um RA, notas ou histórico, use 'verificar_dados_curso_api'.\n"
        "2. Se o usuário pedir um material de estudo/resumo/explicação sobre um tópico, use 'buscar_material_estudo_api'.\n"
        "3. Se o professor pedir para lançar NP1/NP2, use 'lancar_nota_np'.\n"
        "4. Se o professor pedir para lançar PIM, use 'lancar_nota_pim'.\n"
        "5. Se o professor pedir para lançar faltas, use 'lancar_faltas'.\n"
        "6. Para **qualquer outra pergunta abrangente** ou se a função for desnecessária/impossível, **RESPONDA DIRETAMENTE**.\n"
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
    """Simulação de autenticação e inicialização do DB."""
    global DB_INITIALIZED 
    
    conn = None
    try:
        if not DB_INITIALIZED:
            if init_db():
                DB_INITIALIZED = True
            else:
                return jsonify({"status": "error", "message": "Falha crítica ao inicializar o banco de dados. Verifique a variável DATABASE_URL nos logs."}), 503

        data = request.get_json()
        tipo_usuario = data.get('tipo_usuario', '').upper().strip()
        senha = data.get('senha') 
        credencial = data.get('ra') if tipo_usuario == 'ALUNO' else data.get('funcional')
        credencial = credencial.upper().strip() if credencial else None
        codigo_seguranca = data.get('codigo_seguranca', '').strip()

        if not credencial or not senha:
            return jsonify({"status": "error", "message": "Credencial (RA/Funcional) e Senha são obrigatórias."}), 400

        conn, cursor = get_db_connection()
        
        if tipo_usuario == 'ALUNO':
            sql = "SELECT Nome_Completo FROM Alunos WHERE RA = %s AND Senha = %s AND Tipo_Usuario = 'Aluno'"
            cursor.execute(sql, (credencial, senha))
        elif tipo_usuario == 'PROFESSOR':
            sql = "SELECT Nome_Completo FROM Alunos WHERE RA = %s AND Senha = %s AND Codigo_Seguranca = %s AND Tipo_Usuario = 'Professor'"
            cursor.execute(sql, (credencial, senha, codigo_seguranca))
        else:
            conn.close()
            return jsonify({"status": "error", "message": "Tipo de usuário inválido."}), 400

        user_info = cursor.fetchone()

        if user_info:
            conn.close()
            return jsonify({
                "status": "success",
                "message": "Login bem-sucedido!",
                "user": {
                    "nome": user_info['nome_completo'],
                    "ra": credencial,
                    "tipo_usuario": tipo_usuario.lower()
                }
            }), 200
        else:
            conn.close()
            return jsonify({"status": "error", "message": "Credenciais inválidas. Verifique RA/Funcional, Senha e Código de Segurança (Professor)."}), 401

    except Exception as e:
        if conn:
            conn.close()
        return jsonify({"status": "error", "message": f"Erro de servidor: {e}"}), 500

@app.route('/web_router', methods=['POST'])
def web_router():
    """Rota unificada para receber mensagens do chat e rotear para o Gemini/DB."""
    global DB_INITIALIZED
    if not DB_INITIALIZED:
        if init_db():
            DB_INITIALIZED = True
        else:
            return jsonify({"error": "Serviço indisponível. Falha na inicialização do banco de dados."}), 503

    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        tipo_usuario = data.get('tipo_usuario', '').strip()

        if not message:
            return jsonify({"error": "Mensagem vazia."}), 400
        
        if not tipo_usuario:
            return jsonify({"error": "Tipo de usuário ausente na requisição."}), 400

        response_text = rotear_e_executar_mensagem(message, tipo_usuario)

        return jsonify({"message": response_text}), 200

    except Exception as e:
        return jsonify({"error": f"Erro interno no roteador: {e}"}), 500


@app.route('/<path:filename>')
def serve_static(filename):
    """Serve arquivos estáticos (CSS, JS, imagens) localizados na pasta 'static'."""
    if filename == 'joker_bot.html':
        return send_file(filename)
    return send_file(filename)


@app.route('/')
def index():
    """Rota da página inicial."""
    return send_file('joker_bot.html')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

