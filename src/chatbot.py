import time
from openai import (
    APIConnectionError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from bot_context import SYSTEM_PROMPT, TOOLS

# O modelo ocasionalmente pode emitir uma tool call malformada e a API
# responder 400. É intermitente — uma nova tentativa quase sempre resolve.
# Quantas vezes reenviar antes de desistir.
MAX_TOOL_RETRIES = 3

# Erros transitórios de rede/servidor (conexão caída, timeout, 5xx). O SDK da
# OpenAI já repete internamente (max_retries), mas se ele esgotar nós tentamos
# mais algumas vezes com backoff antes de desistir, em vez de derrubar a sessão.
MAX_NETWORK_RETRIES = 3
NETWORK_BACKOFF_SECONDS = 2

# SYSTEM_PROMPT (system prompt do support.md), TOOLS e o carregamento do .env
# ficam centralizados em bot_context.py — ver import no topo.


def main():
    # timeout: quanto esperar por resposta antes de abortar a requisição (o
    # default do SDK costuma ser curto demais quando o modelo demora a gerar).
    # max_retries: o próprio SDK reenvia em erros de conexão/timeout/5xx/429
    # com backoff exponencial — é a primeira linha de defesa contra rede instável.
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        timeout=60,
        max_retries=3,
    )

    # MemorySaver mantém o histórico da conversa em memória durante a sessão,
    # permitindo que o agente acesse turnos anteriores via thread_id
    memory = MemorySaver()

    # create_agent cria um agente ReAct com LangChain/LangGraph:
    # o LLM decide dinamicamente quando e qual ferramenta chamar a cada turno
    agent = create_agent(
        model=llm,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
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
        # Reenviamos em caso de tool call malformada retornada pela API.
        try:
            response = invoke_with_retry(agent, user_input, config)
        except RateLimitError as e:
            # Limite de uso/cota da OpenAI atingido. Não adianta reenviar —
            # informamos e mantemos a sessão viva.
            print(
                "Assistente: Atingi o limite de uso da API da OpenAI agora. "
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
    """Extrai a sugestão de quando tentar de novo da mensagem de erro da OpenAI."""
    message = getattr(getattr(error, "body", None), "get", lambda *_: None)("message") \
        if isinstance(getattr(error, "body", None), dict) else None
    if not message:
        message = str(error)
    if "try again in" in message:
        wait = message.split("try again in", 1)[1].split(".", 1)[0].strip()
        return f"Tente novamente em {wait}."
    return "Tente novamente mais tarde ou troque para um modelo menor (ex.: gpt-4o-mini)."


def invoke_with_retry(agent, user_input, config):
    """Invoca o agente reenviando em falhas intermitentes da OpenAI.

    Trata dois tipos de falha transitória:
      - tool call malformada (BadRequestError 400): reenvia imediatamente,
        pois quase sempre passa na tentativa seguinte.
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