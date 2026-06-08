import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "chatbot.db")


def create_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id),
            role            TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
            content         TEXT NOT NULL,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS knowledge_base (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            topic    TEXT NOT NULL,
            question TEXT NOT NULL,
            answer   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id  TEXT NOT NULL UNIQUE,
            cpf        TEXT DEFAULT "",
            summary    TEXT NOT NULL,
            queue_id   TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)


def seed_data(conn: sqlite3.Connection):
    knowledge = [
        ("langchain", "O que é LangChain?",
         "LangChain é um framework para desenvolver aplicações com LLMs, "
         "facilitando encadeamento de prompts, memória e integração com ferramentas externas."),
        ("langchain", "O que são chains no LangChain?",
         "Chains são sequências de chamadas — a LLMs, ferramentas ou outros componentes — "
         "que permitem construir pipelines complexos de processamento de linguagem natural."),
        ("langchain", "O que é um agent no LangChain?",
         "Um agent usa um LLM para decidir dinamicamente quais ferramentas chamar e em qual ordem, "
         "com base na entrada do usuário."),
        ("langchain", "O que é memória no LangChain?",
         "Memória permite que o chatbot mantenha contexto entre turnos de conversa, "
         "armazenando e recuperando o histórico de mensagens."),
        ("geral", "Qual a capital do Brasil?",
         "A capital do Brasil é Brasília."),
        ("geral", "Quem criou o Python?",
         "Python foi criado por Guido van Rossum e lançado em 1991."),
    ]

    conn.executemany(
        "INSERT INTO knowledge_base (topic, question, answer) VALUES (?, ?, ?)",
        knowledge,
    )

    conn.execute(
        "INSERT INTO conversations (session_id) VALUES (?)", ("session-teste-001",)
    )
    conv_id = conn.execute(
        "SELECT id FROM conversations WHERE session_id = 'session-teste-001'"
    ).fetchone()[0]

    messages = [
        (conv_id, "user",      "Olá! O que é LangChain?"),
        (conv_id, "assistant", "LangChain é um framework para construir aplicações com LLMs."),
        (conv_id, "user",      "E o que são agents?"),
        (conv_id, "assistant", "Agents usam LLMs para decidir dinamicamente quais ferramentas usar."),
    ]
    conn.executemany(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
        messages,
    )


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)
    seed_data(conn)
    conn.commit()
    conn.close()
    print(f"Banco criado em: {DB_PATH}")


if __name__ == "__main__":
    main()