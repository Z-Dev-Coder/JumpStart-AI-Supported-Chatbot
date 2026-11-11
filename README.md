# 🚀 JumpStart AI — Intelligent Customer Support Agent & Chatbot

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.0-092E20.svg?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg?logo=react&logoColor=black)](https://react.dev/)
[![TailwindCSS](https://img.shields.io/badge/Tailwind-CSS-38B2AC.svg?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-black.svg?logo=ollama&logoColor=white)](https://ollama.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**JumpStart** is an enterprise-grade AI customer support platform combining full-stack web capabilities, local Large Language Models (LLM), and Retrieval-Augmented Generation (RAG) with vector embeddings. It features real-time chat, automated agent routing, sentiment & confidence scoring, and seamless human-agent handover.

---

## 🌟 Key Features

- 🤖 **Agentic AI Workflow**: Multi-step LLM reasoning graph equipped with specialized tool execution (orders, tickets, knowledge retrieval, accounts, handovers).
- 📚 **Retrieval-Augmented Generation (RAG)**: Vector similarity search using `pgvector` in PostgreSQL to ground responses against official business knowledge bases.
- ⚡ **Real-Time Streaming**: Live WebSocket bi-directional communication powered by Django Channels.
- 🔒 **Enterprise Guardrails**: Pre/post safety checks, hallucinations prevention, and confidence scoring before delivering answers.
- 👥 **Human Handover System**: Automatic escalation to human support staff when user dissatisfaction or complex queries exceed agent thresholds.
- 📊 **Audit & Analytics**: Complete conversation tracing, tool call logging, sentiment evaluation, and staff management dashboards.

---

## 🛠️ Architecture

```
├── backend/
│   ├── accounts/     # User authentication & role management (JWT)
│   ├── agents/       # LangGraph agent definitions & runner state
│   ├── chatbot/      # WebSocket consumers & chat sessions
│   ├── knowledge/    # Document ingestion & knowledge base management
│   ├── rag/          # Embeddings generation, chunking & vector retrieval
│   ├── services/     # Confidence, sentiment analysis & audit logging
│   ├── staff/        # Human agent dashboard & case management
│   ├── store/        # E-commerce mock models (products, orders, promos)
│   └── tools/        # Agent tools (order lookup, ticket creation, etc.)
├── frontend/
│   ├── src/          # React components, chat interface & staff portal
│   └── public/       # Static assets
└── Reports/          # Evaluation data, project documentation & presentations
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ & npm
- PostgreSQL 15+ (with `pgvector` extension)
- [Ollama](https://ollama.com) running locally with your chosen model (e.g. `mistral` or `llama3`)

### 1. Database Setup

Create the PostgreSQL database and enable `vector`:

```sql
CREATE USER jumpstart_user WITH PASSWORD 'your_password';
CREATE DATABASE jumpstart_db OWNER jumpstart_user;
GRANT ALL PRIVILEGES ON DATABASE jumpstart_db TO jumpstart_user;
\c jumpstart_db
CREATE EXTENSION IF NOT EXISTS vector;
GRANT ALL ON SCHEMA public TO jumpstart_user;
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env  # Update with your DB credentials
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
