import os
import time
import uuid
import re
import streamlit as st
from dotenv import load_dotenv
from groq import APIConnectionError, BadRequestError, InternalServerError, RateLimitError
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

#streamlit run src/app.py
# Importando suas ferramentas existentes.
from tools import verify_client_by_cpf, get_client_history, run_diagnostic_step, open_support_ticket

# Configurações iniciais
load_dotenv(os.path.join(os.path.dirname(__file__), "../config/.env"))
SUPPORT_MD_PATH = os.path.join(os.path.dirname(__file__), "../support.md")
with open(SUPPORT_MD_PATH, encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

TOOLS = [verify_client_by_cpf, get_client_history, run_diagnostic_step, open_support_ticket]

# Configuração da página do Streamlit
st.set_page_config(page_title="Atendimento de Suporte", page_icon="💬")
st.title("💬 Assistente de Suporte")

# Função para inicializar o agente apenas uma vez por sessão
@st.cache_resource
def get_agent():
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        timeout=60,
        max_retries=3,
    )
    memory = MemorySaver()
    agent = create_react_agent(model=llm, tools=TOOLS, prompt=SYSTEM_PROMPT, checkpointer=memory)
    return agent

agent = get_agent()
# --- INÍCIO DA NOVA CONFIGURAÇÃO DE MEMÓRIA ---

# Cria um ID único para a sessão atual se não existir
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# Usa o ID dinâmico da sessão
config = {"configurable": {"thread_id": st.session_state.thread_id}}

# Cria um menu lateral com o botão de limpar histórico
with st.sidebar:
    st.header("Opções")
    if st.button("🔄 Novo Atendimento"):
        # Reseta as mensagens da tela
        st.session_state.messages = [{"role": "assistant", "content": "Olá! Como posso ajudar você hoje?"}]
        # Gera um novo ID para o LangGraph esquecer a conversa anterior
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun() # Atualiza a página

# --- FIM DA NOVA CONFIGURAÇÃO DE MEMÓRIA ---
# Inicializa o histórico de mensagens na tela
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Olá! Como posso ajudar você hoje?"}]

# Mostra o histórico de mensagens na tela
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Tratamento de retries (adaptado do seu chatbot.py)
def invoke_with_retry_streamlit(agent_instance, user_input, agent_config):
    MAX_TOOL_RETRIES = 3
    MAX_NETWORK_RETRIES = 3
    NETWORK_BACKOFF_SECONDS = 2
    
    tool_attempt = 0
    network_attempt = 0
    while True:
        try:
            return agent_instance.invoke({"messages": [HumanMessage(content=user_input)]}, config=agent_config)
        except BadRequestError as e:
            is_tool_failure = getattr(e, "code", None) == "tool_use_failed" or "tool_use_failed" in str(e)
            tool_attempt += 1
            if not is_tool_failure or tool_attempt >= MAX_TOOL_RETRIES:
                raise
        except (APIConnectionError, InternalServerError):
            network_attempt += 1
            if network_attempt >= MAX_NETWORK_RETRIES:
                return None
            time.sleep(NETWORK_BACKOFF_SECONDS * network_attempt)

# Captura a entrada do usuário
user_input = st.chat_input("Digite sua mensagem aqui...")
if user_input:
    # Adiciona a mensagem do usuário na tela e no estado
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Mostra um "digitando..." enquanto o modelo processa
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("⏳ *Pensando...*")
        
        try:
            response = invoke_with_retry_streamlit(agent, user_input, config)
            if response:
                bot_reply = response["messages"][-1].content
                
                # --- LINHA NOVA: Limpa tags de função vazadas do Llama 3 ---
                bot_reply = re.sub(r'<function.*?>.*?</function>', '', bot_reply, flags=re.DOTALL).strip()
                # ------------------------------------------------------------
                
                # Se a mensagem ficar vazia após limpar (IA mandou SÓ a tool call), não exibe nada
                if bot_reply:
                    message_placeholder.markdown(bot_reply)
                    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            else:
                error_msg = "Tive um problema técnico ao processar isso. Pode repetir, por favor?"
                message_placeholder.markdown(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
        except RateLimitError:
            rate_limit_msg = "Atingi o limite de uso da API da Groq agora. Tente novamente em alguns instantes."
            message_placeholder.markdown(rate_limit_msg)
            st.session_state.messages.append({"role": "assistant", "content": rate_limit_msg})