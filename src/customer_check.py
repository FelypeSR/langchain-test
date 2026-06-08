import sqlite3
import os
from dataclasses import dataclass

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/chatbot.db")


@dataclass
class Customer:
    id: int
    nome: str
    local: str
    cpf: str
    pacote: str


def find_customer_by_cpf(cpf: str) -> Customer | None:
    cpf_clean = cpf.replace(".", "").replace("-", "").strip()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, nome, local, cpf, pacote FROM customers WHERE cpf = ?",
        (cpf_clean,),
    ).fetchone()
    conn.close()
    if row:
        return Customer(*row)
    return None


def find_customer_by_name(nome: str) -> Customer | None:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, nome, local, cpf, pacote FROM customers WHERE LOWER(nome) = LOWER(?)",
        (nome.strip(),),
    ).fetchone()
    conn.close()
    if row:
        return Customer(*row)
    return None