import os
import time
from dotenv import load_dotenv
from groq import (
    APIConnectionError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from tools import verify_client_by_cpf, get_client_history, run_diagnostic_step, open_support_ticket

# Os modelos da Groq ocasionalmente emitem uma tool call malformada e o
# servidor responde 400 com code 'tool_use_failed'. É intermitente — uma nova
# tentativa quase sempre resolve. Quantas vezes reenviar antes de desistir.
MAX_TOOL_RETRIES = 3

# Erros transitórios de rede/servidor (conexão caída, timeout, 5xx). O SDK do
# Groq já repete internamente (max_retries), mas se ele esgotar nós tentamos
# mais algumas vezes com backoff antes de desistir, em vez de derrubar a sessão.
MAX_NETWORK_RETRIES = 3
NETWORK_BACKOFF_SECONDS = 2

# Carrega GROQ_API_KEY do arquivo .env
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


def main():
    # timeout: quanto esperar por resposta antes de abortar a requisição (o
    # default do SDK costuma ser curto demais quando o modelo demora a gerar).
    # max_retries: o próprio SDK reenvia em erros de conexão/timeout/5xx/429
    # com backoff exponencial — é a primeira linha de defesa contra rede instável.
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        timeout=60,
        max_retries=3,
    )

    # MemorySaver mantém o histórico da conversa em memória durante a sessão,
    # permitindo que o agente acesse turnos anteriores via thread_id
    memory = MemorySaver()

    # create_react_agent cria um agente ReAct com LangGraph:
    # o LLM decide dinamicamente quando e qual ferramenta chamar a cada turno
    agent = create_react_agent(
        model=llm,
        tools=TOOLS,
        prompt=SYSTEM_PROMPT,
        checkpointer=memory,
    )

    # thread_id identifica esta sessão — o agente recupera o histórico completo
    # a cada chamada usando esse identificador
    config = {"configurable": {"thread_id": "sessao-001"}}

    print("Atendimento iniciado. Digite 'sair' para encerrar.\n")

    while True:
        print("Você: ", end="")
        user_input = input().strip()

        if not user_input:
            continue

        if user_input.lower() in ("sair", "exit", "quit"):
            print("Atendimento encerrado.")
            break

        # Envia a mensagem do usuário ao agente; ele retorna a lista completa
        # de mensagens da sessão — pegamos apenas a última (resposta do assistente).
        # Reenviamos em caso de tool call malformada (tool_use_failed do Groq).
        try:
            response = invoke_with_retry(agent, user_input, config)
        except RateLimitError as e:
            # Limite de tokens da Groq atingido (ex.: cota diária do free tier).
            # Não adianta reenviar — informamos e mantemos a sessão viva.
            print(
                "Assistente: Atingi o limite de uso da API da Groq agora. "
                f"{_rate_limit_hint(e)}\n"
            )
            continue

        if response is None:
            print(
                "Assistente: Tive um problema técnico ao processar isso. "
                "Pode repetir, por favor?\n"
            )
            continue

        last_message = response["messages"][-1]
        print(f"Assistente: {last_message.content}\n")


def _rate_limit_hint(error):
    """Extrai a sugestão de quando tentar de novo da mensagem de erro da Groq."""
    message = getattr(getattr(error, "body", None), "get", lambda *_: None)("message") \
        if isinstance(getattr(error, "body", None), dict) else None
    if not message:
        message = str(error)
    if "try again in" in message:
        wait = message.split("try again in", 1)[1].split(".", 1)[0].strip()
        return f"Tente novamente em {wait}."
    return "Tente novamente mais tarde ou troque para um modelo menor (ex.: llama-3.1-8b-instant)."


def invoke_with_retry(agent, user_input, config):
    """Invoca o agente reenviando em falhas intermitentes do Groq.

    Trata dois tipos de falha transitória:
      - tool_use_failed (BadRequestError 400): tool call malformada — reenvia
        imediatamente, pois quase sempre passa na tentativa seguinte.
      - rede/servidor (APIConnectionError, que inclui APITimeoutError, e
        InternalServerError 5xx): reenvia com backoff. RateLimitError (429) NÃO
        é tratado aqui — sobe para o main(), que avisa o usuário.

    Retorna a resposta do agente, ou None se esgotar as tentativas.
    """
    tool_attempt = 0
    network_attempt = 0
    while True:
        try:
            return agent.invoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
            )
        except BadRequestError as e:
            is_tool_failure = (
                getattr(e, "code", None) == "tool_use_failed"
                or "tool_use_failed" in str(e)
            )
            tool_attempt += 1
            if not is_tool_failure or tool_attempt >= MAX_TOOL_RETRIES:
                raise
            # Tool call malformada e ainda há retries — reenvia na hora.
        except (APIConnectionError, InternalServerError):
            # Conexão caída, timeout ou erro 5xx — transitório. Backoff e retry.
            network_attempt += 1
            if network_attempt >= MAX_NETWORK_RETRIES:
                return None
            time.sleep(NETWORK_BACKOFF_SECONDS * network_attempt)


if __name__ == "__main__":
    main()