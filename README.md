# JumpStart — Agentic AI Customer Support Chatbot with Human Handover

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.0-092E20.svg)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791.svg)](https://www.postgresql.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Academic Capstone Project (HDSE-CPL)**  
> **Course**: Higher National Diploma in Software Engineering (EduCLaaS)  
> **Author**: Zaw Myo Tun  
> **Topic**: *Designing and Evaluating an Agentic AI Customer-Support Chatbot with Human Handover for JumpStart Retail*

---

## 📖 Project Overview & Academic Background

This project represents the summative Capstone Project for the **Higher National Diploma in Software Engineering**. In retail customer support, purely autonomous chatbots often hallucinate or fail on nuanced requests, while purely human support is difficult to scale. 

JumpStart addresses this challenge by implementing a **hybrid AI-human support architecture** combining:
1. **Agentic Reasoning Graph (LangGraph)** for multi-step query planning, tool execution, and clarification.
2. **Structure-Aware RAG (Retrieval-Augmented Generation)** with PostgreSQL `pgvector` to ground replies in official retail policy documents.
3. **Deterministic Human Handover Layer** that evaluates confidence, negative sentiment, and repeated query failures to automatically transfer conversations to a human staff dashboard.

---

## 🎯 Research Questions & Core Objectives

- **RQ1 (Grounded Retrieval)**: How can RAG and agentic clarification prevent hallucinations and ground responses in real retail catalog and shipping data?
- **RQ2 (Handover Thresholds)**: Under what operational conditions (sentiment dip, low confidence, unresolved return/refund requests) should the agent escalate to a human agent?
- **RQ3 (Usability & Performance)**: How effectively does the prototype achieve acceptable latency and high user satisfaction across simulated customer scenarios?

---

## 🛠️ System Architecture

```
├── backend/
│   ├── accounts/     # JWT Authentication & role permissions (Customer vs Support Staff)
│   ├── agents/       # LangGraph state graph, node transitions, and agent prompt templates
│   ├── chatbot/      # Real-time WebSocket consumers (Django Channels)
│   ├── knowledge/    # Knowledge base document ingestion & chunk management
│   ├── rag/          # Embeddings generation and pgvector similarity retrieval
│   ├── services/     # Sentiment scoring, confidence evaluation & audit logging
│   ├── staff/        # Human staff inbox, live handover takeover & case resolution
│   ├── store/        # Retail store mock data (products, orders, tracking, promos)
│   └── tools/        # Agent tools (order lookup, ticket creation, handover trigger)
├── frontend/
│   ├── src/          # React frontend with dual views: Customer Chat Widget & Staff Live Portal
│   └── public/
└── Reports/          # Academic submission docs, test sets, evaluation data & presentations
```

---

## ✨ Key Features & Handover Criteria

- **Autonomous Agent Tool Calling**: Interactively queries order status, shipping ETA, product availability, and promo codes without human intervention.
- **pgvector Semantic Search**: Chunks and embeds store policies, return conditions, and FAQs using cosine similarity retrieval.
- **Safety & Groundedness Checks**: Validates model output before dispatching to the client; flags ungrounded statements.
- **Seamless Live Escalation**: When triggered, creates a prioritized `SupportCase` for staff, transfers conversation history via WebSockets, and allows staff to intervene in real-time.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- PostgreSQL 15+ with `pgvector` extension installed
- [Ollama](https://ollama.com) running locally (e.g. `mistral` or `llama3`)

### 1. Database Configuration
```sql
CREATE USER jumpstart_user WITH PASSWORD 'your_password';
CREATE DATABASE jumpstart_db OWNER jumpstart_user;
GRANT ALL PRIVILEGES ON DATABASE jumpstart_db TO jumpstart_user;
\c jumpstart_db
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate       # Windows
# source venv/bin/activate    # Linux/macOS

pip install -r requirements.txt
cp .env.example .env          # Set your DB connection and Ollama model
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

This academic project is licensed under the [MIT License](LICENSE).
