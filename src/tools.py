import sqlite3
import os
import uuid
from langchain_core.tools import tool

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/chatbot.db")

# Árvore de diagnóstico simplificada: mapeia palavras-chave do sintoma ao próximo passo
DIAGNOSTIC_MAP = {
    "los":          "Luz LOS vermelha indica perda de sinal na fibra externa — problema na rede externa. Não tem solução remota. Escalar imediatamente para visita técnica.",
    "sem internet": "Pedir ao cliente que verifique as luzes do modem e informe o estado de cada uma (Power, PON, LOS, LAN).",
    "lento":        "Solicitar que o cliente teste com cabo direto no computador e verifique quantos dispositivos estão conectados.",
    "caindo":       "Verificar se a queda ocorre com cabo direto também. Consultar histórico para checar recorrência.",
    "wifi":         "Orientar o cliente a esquecer a rede Wi-Fi e reconectar. Testar em outro dispositivo para isolar se o problema é o aparelho ou a rede.",
    "reinicio":     "Desligar o modem da tomada, aguardar 1-2 minutos, ligar novamente e aguardar 2 minutos para as luzes estabilizarem.",
    "equipamento":  "Verificar se o modem está com todas as luzes apagadas. Testar outra tomada e cabo de energia antes de concluir defeito.",
}


@tool
def verify_client_by_cpf(cpf: str) -> dict:
    """
    Verifica se o CPF informado corresponde a um cliente ativo do provedor.
    Retorna found=true e os dados do cliente, ou found=false caso não localizado.
    Aceita CPF com ou sem pontuação.
    """
    cpf_clean = cpf.replace(".", "").replace("-", "").strip()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT nome, local, cpf, pacote FROM customers WHERE cpf = ?",
        (cpf_clean,),
    ).fetchone()
    conn.close()

    if row:
        return {
            "found": True,
            "client": {"nome": row[0], "local": row[1], "cpf": row[2], "pacote": row[3]},
        }
    return {"found": False}


@tool
def get_client_history(cpf: str) -> dict:
    """
    Retorna os tickets de suporte anteriores do cliente pelo CPF.
    Útil para identificar problemas recorrentes antes de iniciar o diagnóstico.
    """
    cpf_clean = cpf.replace(".", "").replace("-", "").strip()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT ticket_id, summary, queue_id, created_at
           FROM tickets WHERE cpf = ?
           ORDER BY created_at DESC LIMIT 10""",
        (cpf_clean,),
    ).fetchall()
    conn.close()

    if not rows:
        return {"count": 0, "tickets": []}

    tickets = [
        {"id": r[0], "summary": r[1], "queue": r[2], "date": r[3]} for r in rows
    ]
    return {"count": len(tickets), "tickets": tickets}


@tool
def run_diagnostic_step(symptom: str) -> dict:
    """
    Recebe uma descrição do sintoma atual e retorna o próximo passo de diagnóstico.
    Consulta a árvore de decisão interna do provedor.
    """
    symptom_lower = symptom.lower()

    for keyword, step in DIAGNOSTIC_MAP.items():
        if keyword in symptom_lower:
            return {"symptom": symptom, "next_step": step}

    # Passo genérico quando o sintoma não se encaixa em nenhuma categoria conhecida
    return {
        "symptom": symptom,
        "next_step": (
            "Solicitar mais detalhes: perguntar sobre o estado das luzes do modem "
            "e se o problema afeta todos os dispositivos ou apenas um."
        ),
    }


@tool
def open_support_ticket(summary: str, queue_id: str, cpf: str = "") -> dict:
    """
    Abre um chamado de suporte e direciona para a fila correta.
    Use queue_id='suporte' para problemas técnicos ou queue_id='vendas' para novos clientes.
    O summary deve conter: sintoma, estado das luzes, passos já tentados e motivo da escalada.
    """
    ticket_id = str(uuid.uuid4())[:8].upper()
    cpf_clean = cpf.replace(".", "").replace("-", "").strip()

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO tickets (ticket_id, cpf, summary, queue_id) VALUES (?, ?, ?, ?)",
        (ticket_id, cpf_clean, summary, queue_id),
    )
    conn.commit()
    conn.close()

    return {"ticket_id": ticket_id, "queue": queue_id, "status": "aberto"}