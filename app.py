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
SQL_SCRIPT_CONTENT = """
-- CRIAÇÃO DAS TABELAS (Ajustado para SQLite: INTEGER PRIMARY KEY AUTOINCREMENT)
CREATE TABLE IF NOT EXISTS Alunos (
    id_aluno INTEGER PRIMARY KEY AUTOINCREMENT,
    RA VARCHAR(10) NOT NULL UNIQUE,
    Nome_Completo VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS Disciplinas (
    id_disciplina INTEGER PRIMARY KEY AUTOINCREMENT,
    Nome_Disciplina VARCHAR(100) NOT NULL,
    Semestre INT NOT NULL,
    UNIQUE (Nome_Disciplina, Semestre)
);

CREATE TABLE IF NOT EXISTS Historico_Academico (
    id_registro INTEGER PRIMARY KEY AUTOINCREMENT,
    fk_id_aluno INT NOT NULL,
    fk_id_disciplina INT NOT NULL,
    Nota DECIMAL(4, 2) DEFAULT 0.00,
    Faltas INT DEFAULT 0,
    Estudos_Disciplinares_Concluido BOOLEAN DEFAULT 0,
    AVAS_Concluido BOOLEAN DEFAULT 0,
    FOREIGN KEY (fk_id_aluno) REFERENCES Alunos(id_aluno),
    FOREIGN KEY (fk_id_disciplina) REFERENCES Disciplinas(id_disciplina),
    UNIQUE (fk_id_aluno, fk_id_disciplina)
);

-- POPULANDO A TABELA DISCIPLINAS
INSERT OR IGNORE INTO Disciplinas (Nome_Disciplina, Semestre) VALUES
('Introdução à Programação', 1), ('Lógica de Computação', 1), ('Fundamentos de Sistemas', 1), ('Português e Redação', 1),
('Estruturas de Dados', 2), ('Banco de Dados I', 2), ('Arquitetura de Computadores', 2), ('Ética e Cidadania', 2);

-- POPULANDO A TABELA ALUNOS
INSERT OR IGNORE INTO Alunos (RA, Nome_Completo) VALUES
('R3487E5', 'Matheus de Assis Alves'), ('R6738H5', 'Matheus Balzi da Silva'), ('R818888', 'Lucas Gabriel da Silva Gardezan'),
('H755247', 'Matheus Henrique Castro de Oliveira'), ('R848140', 'Thainanda Alves Monteiro'), ('820793', 'Lucas da Silva Andrade');

-- REGISTRO DO HISTÓRICO ACADÊMICO
INSERT OR IGNORE INTO Historico_Academico (fk_id_aluno, fk_id_disciplina, Nota, Faltas, Estudos_Disciplinares_Concluido, AVAS_Concluido) VALUES
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Introdução à Programação' AND Semestre = 1), 8.5, 2, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Lógica de Computação' AND Semestre = 1), 7.0, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Fundamentos de Sistemas' AND Semestre = 1), 9.2, 1, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Português e Redação' AND Semestre = 1), 6.5, 4, 0, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Estruturas de Dados' AND Semestre = 2), 7.5, 3, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Banco de Dados I' AND Semestre = 2), 8.8, 1, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Arquitetura de Computadores' AND Semestre = 2), 6.9, 5, 1, 0),
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Ética e Cidadania' AND Semestre = 2), 9.5, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Introdução à Programação' AND Semestre = 1), 5.5, 8, 1, 0),
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Lógica de Computação' AND Semestre = 1), 7.8, 1, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Fundamentos de Sistemas' AND Semestre = 1), 8.0, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Português e Redação' AND Semestre = 1), 9.0, 3, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Estruturas de Dados' AND Semestre = 2), 6.0, 7, 0, 0),
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Banco de Dados I' AND Semestre = 2), 7.2, 4, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Arquitetura de Computadores' AND Semestre = 2), 8.5, 2, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Ética e Cidadania' AND Semestre = 2), 5.0, 9, 0, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Introdução à Programação' AND Semestre = 1), 9.5, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Lógica de Computação' AND Semestre = 1), 8.9, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Fundamentos de Sistemas' AND Semestre = 1), 9.8, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Português e Redação' AND Semestre = 1), 9.1, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Estruturas de Dados' AND Semestre = 2), 10.0, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE Alunos.RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Banco de Dados I' AND Semestre = 2), 9.5, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Arquitetura de Computadores' AND Semestre = 2), 9.9, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Ética e Cidadania' AND Semestre = 2), 9.0, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Introdução à Programação' AND Semestre = 1), 6.0, 5, 0, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Lógica de Computação' AND Semestre = 1), 5.5, 7, 0, 0),
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Fundamentos de Sistemas' AND Semestre = 1), 7.2, 2, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Português e Redação' AND Semestre = 1), 8.5, 1, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Estruturas de Dados' AND Semestre = 2), 5.5, 8, 0, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Banco de Dados I' AND Semestre = 2), 6.5, 5, 1, 0),
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Arquitetura de Computadores' AND Semestre = 2), 7.8, 3, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Ética e Cidadania' AND Semestre = 2), 8.0, 1, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Introdução à Programação' AND Semestre = 1), 9.8, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Lógica de Computação' AND Semestre = 1), 9.5, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Fundamentos de Sistemas' AND Semestre = 1), 8.0, 1, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Português e Redação' AND Semestre = 1), 7.9, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Estruturas de Dados' AND Semestre = 2), 9.0, 1, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Banco de Dados I' AND Semestre = 2), 8.5, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Arquitetura de Computadores' AND Semestre = 2), 7.5, 2, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Ética e Cidadania' AND Semestre = 2), 9.3, 0, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Introdução à Programação' AND Semestre = 1), 7.7, 3, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Lógica de Computação' AND Semestre = 1), 6.9, 4, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Fundamentos de Sistemas' AND Semestre = 1), 8.8, 1, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Português e Redação' AND Semestre = 1), 7.5, 2, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Estruturas de Dados' AND Semestre = 2), 6.8, 5, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Banco de Dados I' AND Semestre = 2), 7.0, 3, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Arquitetura de Computadores' AND Semestre = 2), 8.2, 1, 1, 1),
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Ética e Cidadania' AND Semestre = 2), 7.9, 2, 1, 1);
"""

# --- INICIALIZAÇÃO DO FLASK E GEMINI ---
app = Flask(__name__)
CORS(app) 
client = None

# Inicializa o cliente Gemini
if API_KEY_GEMINI:
    try:
        client = genai.Client(api_key=API_KEY_GEMINI)
        print("✅ Cliente Gemini inicializado com sucesso.")
    except Exception as e:
        print(f"❌ Erro fatal ao inicializar o cliente Gemini. Detalhe: {e}")
else:
    print("⚠️ Chave API do Gemini ausente. A Op. 2 e o roteador não funcionarão.")


# --- 2. FUNÇÕES DE SUPORTE AO BANCO DE DADOS ---

def init_db():
    """Cria e popula o banco de dados. Chamado apenas no início do servidor."""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.executescript(SQL_SCRIPT_CONTENT) 
        conn.commit()
        conn.close()
        print(f"✅ Banco de dados '{DATABASE_NAME}' verificado e pronto para uso.")
    except sqlite3.Error as e:
        print(f"❌ Erro na inicialização do banco de dados: {e}")
        exit() 

def get_db_connection():
    """Retorna uma nova conexão ao banco de dados para uma requisição."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row 
    return conn

# --- 3. FUNÇÕES DE OPERAÇÃO (LÓGICA CORE) ---

def verificar_dados_curso_api(ra_aluno: str) -> dict:
    """OPERAÇÃO 1: Busca o histórico e retorna um dicionário de dados."""
    ra_aluno = ra_aluno.strip().upper()

    comando_sql_join = """
    SELECT
        A.Nome_Completo, D.Nome_Disciplina, D.Semestre,
        H.Nota, H.Faltas, H.Estudos_Disciplinares_Concluido, H.AVAS_Concluido
    FROM Historico_Academico H
    JOIN Alunos A ON H.fk_id_aluno = A.id_aluno
    JOIN Disciplinas D ON H.fk_id_disciplina = D.id_disciplina
    WHERE A.RA = ?
    ORDER BY D.Semestre, D.Nome_Disciplina;
    """

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(comando_sql_join, (ra_aluno,))
        registros = cursor.fetchall()

        if not registros:
            conn.close()
            return {"status": "error", "message": f"O RA '{ra_aluno}' não foi encontrado ou não possui histórico registrado."}

        historico = []
        for reg in registros:
            historico.append({
                "disciplina": reg['Nome_Disciplina'],
                "semestre": reg['Semestre'],
                "nota": float(f"{reg['Nota']:.2f}"),
                "faltas": reg['Faltas'],
                "ed_concluido": bool(reg['Estudos_Disciplinares_Concluido']),
                "avas_concluido": bool(reg['AVAS_Concluido']),
            })

        conn.close()
        return {
            "status": "success",
            "aluno": registros[0]['Nome_Completo'],
            "ra": ra_aluno,
            "historico": historico
        }

    except sqlite3.Error as e:
        conn.close()
        return {"status": "error", "message": f"Erro na consulta ao banco de dados: {e}"}

def buscar_material_estudo_api(topico: str) -> dict:
    """OPERAÇÃO 2: Gera material usando o Gemini e retorna a resposta."""
    if not client:
        return {"status": "error", "message": "A API do Gemini não está configurada corretamente."}

    prompt = (
        f"Gere um material de estudo conciso e focado para o tópico '{topico}'. "
        "Inclua: 1. Breve resumo. 2. Três pontos chave. 3. Um exercício prático (com resposta). Responda em português."
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
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

# --- 4. CONFIGURAÇÃO DE FUNÇÕES (TOOLS) E ROUTER ---

# Funções que o Gemini pode chamar
def verificar_historico_academico(ra: str) -> dict:
    """Busca o histórico acadêmico completo de um aluno pelo seu RA."""
    return verificar_dados_curso_api(ra)

def gerar_material_estudo(topico: str) -> dict:
    """Gera material de estudo conciso e focado sobre um tópico específico."""
    return buscar_material_estudo_api(topico)

# Mapeamento das ferramentas
TOOLS = {
    'verificar_historico_academico': verificar_historico_academico,
    'gerar_material_estudo': gerar_material_estudo
}

def rotear_e_executar_mensagem(mensagem_usuario: str) -> str:
    """
    Usa o Gemini para interpretar a intenção do usuário (Function Calling), 
    executa a função apropriada (SQL ou Gemini) e gera a resposta final em texto.
    """
    
    if not client:
        return "❌ Desculpe, a conexão com a inteligência artificial está temporariamente indisponível."
    
    prompt_ferramenta = (
        "O usuário enviou a seguinte mensagem: '{}'. Analise a intenção. Se a intenção for 'buscar "
        "material de estudo', use 'gerar_material_estudo'. Se a intenção for 'consultar "
        "dados acadêmicos' (notas, faltas, RA), use 'verificar_historico_academico'. "
        "Em caso de dados faltantes (ex: RA), peça-os. Se nenhuma ferramenta for apropriada, responda diretamente."
    ).format(mensagem_usuario)
    
    # 1. Envia a mensagem com as ferramentas para o Gemini
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt_ferramenta],
            # 💡 CORREÇÃO APLICADA: Uso de 'config' para resolver o erro 'tools' no Render
            config=GenerateContentConfig(tools=list(TOOLS.values()))  
        )
    except Exception as e:
        # Erro de 'tools' não deve ocorrer na hospedagem, mas é bom ter uma mensagem genérica de erro aqui.
        print(f"Erro na chamada do Gemini: {e}")
        return "❌ Erro ao processar a requisição com o Gemini. Tente novamente."


    # 2. Verifica se o Gemini decidiu chamar uma função
    if response.function_calls:
        call = response.function_calls[0]
        func_name = call.name
        func_args = dict(call.args)
        
        if func_name in TOOLS:
            print(f"🤖 Chamando função {func_name} com args: {func_args}")

            # 3. Executa a função localmente
            function_response_data = TOOLS[func_name](**func_args)
            
            # Se a busca SQL falhar (ex: RA não encontrado), retorna o erro diretamente.
            if func_name == 'verificar_historico_academico' and function_response_data.get('status') == 'error':
                 return f"Joker: {function_response_data['message']}"

            # 4. Envia o resultado da execução de volta ao Gemini
            segundo_prompt = [
                response, 
                genai.types.Part.from_function_response(
                    name=func_name,
                    response=function_response_data
                )
            ]

            # 5. Gera a resposta final formatada para o usuário
            final_response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=segundo_prompt
            )

            return final_response.text

    # 6. Se nenhuma função foi chamada, o Gemini respondeu diretamente
    return response.text

# --- ROTA PARA SERVIR O FRONT-END ---
@app.route('/')
def serve_index():
    """Serva o arquivo index.html principal, que está na raiz."""
    # ⬅️ Faz o Flask enviar o arquivo index.html da pasta raiz
    return send_file('joker_bot.html') 

# --- 5. ROTA PRINCIPAL PARA O FRONT-END WEB ---
@app.route('/web_router', methods=['POST'])
def handle_web_message():
    """
    Endpoint que recebe a mensagem do usuário do Front-end Web (index.html).
    """
    try:
        data = request.get_json()
        message_text = data.get('message')

        if not message_text:
            return jsonify({"status": "error", "message": "Mensagem de texto não fornecida."}), 400

        print(f"🌐 Mensagem recebida do Web UI: {message_text}")

        resposta_final_texto = rotear_e_executar_mensagem(message_text)

        return jsonify({
            "status": "success",
            "message": resposta_final_texto
        }), 200

    except Exception as e:
        print(f"❌ Erro no Web Router: {e}")
        return jsonify({"status": "error", "message": f"Erro interno do servidor: {e}"}), 500


# --- ROTA PARA TWILIO (WhatsApp) ---

@app.route('/whatsapp_webhook', methods=['POST'])
def handle_whatsapp_message():
    """Endpoint que recebe a mensagem do usuário do WhatsApp via Webhook da Twilio."""
    
    message_text = request.form.get('Body')
    
    if not message_text:
        return str(MessagingResponse()), 200 

    print(f"💬 Mensagem recebida da Twilio: {message_text}")

    resposta_final_texto = rotear_e_executar_mensagem(message_text)
    
    resp = MessagingResponse()
    resp.message(resposta_final_texto)
    return str(resp)


# --- EXECUÇÃO PRINCIPAL ---

# Inicializa o banco de dados antes de iniciar o servidor (Correção para o Render)
init_db() 

if __name__ == '__main__':
    app.run(debug=True)

