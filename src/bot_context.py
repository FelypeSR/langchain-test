import os
from dotenv import load_dotenv
from tools import (
    verify_client_by_cpf,
    get_client_history,
    run_diagnostic_step,
    open_support_ticket,
)

# Carrega OPENAI_API_KEY do arquivo .env
load_dotenv(os.path.join(os.path.dirname(__file__), "../config/.env"))

# Lê o support.md como system prompt — ele define identidade, fluxo de triagem,
# regras de uso das ferramentas e exemplos de diálogo
SUPPORT_MD_PATH = os.path.join(os.path.dirname(__file__), "../support.md")
with open(SUPPORT_MD_PATH, encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

# Ferramentas disponíveis para o agente, conforme definido no support.md
TOOLS = [
    verify_client_by_cpf,   # Fase 1 — triagem: valida CPF do cliente
    get_client_history,      # Fase 2 — diagnóstico: histórico de chamados
    run_diagnostic_step,     # Fase 2 — diagnóstico: próximo passo da árvore de decisão
    open_support_ticket,     # Escalada: abre chamado para suporte ou vendas
]