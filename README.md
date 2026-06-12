# 💬 Assistente de Suporte — Provedor de Internet

Chatbot de suporte técnico para um provedor de internet (ISP), construído com
**LangChain / LangGraph** e **OpenAI**. O agente atende clientes no estilo
WhatsApp: faz a triagem por CPF, consulta o histórico de chamados, conduz um
diagnóstico passo a passo e, quando não resolve remotamente, abre um ticket e
escala para um humano.

Disponível em duas interfaces:

- **Web (Streamlit)** — `src/app.py`
- **Terminal (CLI)** — `src/chatbot.py`

## Arquitetura

| Arquivo | Responsabilidade |
|---|---|
| `src/app.py` | Interface web em Streamlit (chat, memória por sessão, retries) |
| `src/chatbot.py` | Interface de linha de comando |
| `src/bot_context.py` | Contexto central do bot: carrega o `.env`, o system prompt e a lista de ferramentas |
| `src/tools.py` | Ferramentas do agente (`verify_client_by_cpf`, `get_client_history`, `run_diagnostic_step`, `open_support_ticket`) |
| `src/customer_check.py` | Helpers de consulta de clientes no banco |
| `src/setup_db.py` | Cria/reinicializa o banco SQLite e insere dados de teste |
| `support.md` | System prompt do agente (identidade, fluxo de triagem, regras das ferramentas) |
| `data/chatbot.db` | Banco SQLite local (gerado, ignorado pelo git) |
| `config/.env` | Variáveis de ambiente / segredos (ignorado pelo git) |

## Pré-requisitos

- Python 3.12+
- Uma chave de API da OpenAI

## Instalação

```bash
# Clonar e entrar no diretório
cd chatbot

# Criar e ativar o ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# Instalar dependências
pip install -r requirements.txt
```

## Configuração

Crie o arquivo `config/.env` com a sua chave da OpenAI:

```env
OPENAI_API_KEY=sk-...
```

> O `config/.env` está no `.gitignore` e não é versionado.

## Banco de dados

Antes do primeiro uso, inicialize o banco SQLite com os dados de teste:

```bash
python src/setup_db.py
```

Isso cria `data/chatbot.db` com as tabelas `customers` e `tickets` e insere 3
clientes de teste:

| Nome | CPF | Pacote |
|---|---|---|
| João Silva | `12345678900` | Plano 500 Mega |
| Maria Oliveira | `09876543211` | Plano 1 Giga |
| Carlos Coutinho | `11122233344` | Plano 300 Mega |

> Rodar o script novamente **recria** os clientes (limpa a tabela `customers` antes de inserir).

## Como executar

### Interface web (Streamlit)

```bash
streamlit run src/app.py
```

Acesse em **http://localhost:8501**.

### Interface de terminal (CLI)

```bash
python src/chatbot.py
```

Digite `sair` para encerrar.

## Como funciona o agente

1. **Triagem** — valida o CPF do cliente (`verify_client_by_cpf`).
2. **Diagnóstico** — consulta o histórico de chamados (`get_client_history`) e
   percorre a árvore de decisão de sintomas (`run_diagnostic_step`).
3. **Escalada** — quando não há solução remota, abre um chamado
   (`open_support_ticket`) na fila de `suporte` ou `vendas`.

A conversa usa `create_agent` (LangChain) com um `MemorySaver` do LangGraph,
mantendo o histórico por sessão via `thread_id`.

## Stack

- [LangChain](https://www.langchain.com/) / LangGraph — orquestração do agente
- [OpenAI](https://platform.openai.com/) `gpt-4o-mini` — modelo de linguagem
- [Streamlit](https://streamlit.io/) — interface web
- SQLite — persistência local de clientes e tickets