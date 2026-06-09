import sqlite3
import os

# Caminho para o banco de dados, seguindo a mesma estrutura do seu tools.py
DB_PATH = os.path.join(os.path.dirname(__file__), "../data/chatbot.db")

def init_db():
    # Garante que a pasta 'data' existe
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Cria a tabela de clientes (customers)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            local TEXT,
            cpf TEXT UNIQUE NOT NULL,
            pacote TEXT
        )
    """)

    # Cria a tabela de chamados (tickets) que a ferramenta 'get_client_history' precisa
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            cpf TEXT NOT NULL,
            summary TEXT NOT NULL,
            queue_id TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insere dados de teste (limpa antes para não duplicar se rodar mais de uma vez)
    cursor.execute("DELETE FROM customers")
    
    clientes_teste = [
        ("João Silva", "São Paulo", "12345678900", "Plano 500 Mega"),
        ("Maria Oliveira", "Rio de Janeiro", "09876543211", "Plano 1 Giga"),
        ("Carlos Coutinho", "Belo Horizonte", "11122233344", "Plano 300 Mega")
    ]
    
    cursor.executemany(
        "INSERT INTO customers (nome, local, cpf, pacote) VALUES (?, ?, ?, ?)",
        clientes_teste
    )

    conn.commit()
    conn.close()
    print("Banco de dados criado com sucesso! Dados de teste inseridos.")

if __name__ == "__main__":
    init_db()