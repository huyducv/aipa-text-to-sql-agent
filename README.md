# Enterprise Text-to-SQL Agent (Local Execution Architecture)

**An AI-driven decision support system translating natural language to secure, locally executed SQL queries.**

## 📖 Project Overview

Stakeholders in modern enterprises often require immediate insights from structured data but are bottlenecked by the technical requirement of writing SQL. This project presents an MVP for an intelligent **Text-to-SQL Agent** that bridges this gap. 

Designed for a 1-week rapid prototyping cycle, this solution integrates multiple AI paradigms to deliver a secure, scalable, and highly accurate query generation pipeline. Crucially, the architecture strictly separates the generative reasoning environment from the local data execution environment, ensuring absolute data privacy.

### 🧠 Integrated AI Paradigms
1. **Generative AI (LLMs):** Utilizing `gemini-2.0-flash` strictly as a translation layer (Natural Language → SQLite syntax).
2. **Structural Knowledge Representation:** Deterministic extraction and injection of the database schema (Data Definition Language) into the LLM context, grounding the model to prevent hallucinations.
3. **Deterministic Logic / Expert Rules:** A programmatic safety boundary that intercepts the generated SQL and evaluates it against strict read-only rules prior to execution.

---

## 🏗️ System Architecture

To ensure data privacy and system integrity, **the LLM never accesses the actual database records**.

1. **Schema Extraction:** The Python backend queries the local `.db` file for its `CREATE TABLE` definitions.
2. **Context Injection:** The user's plain-English question and the database schema are bundled and sent to the Gemini API.
3. **Generative Translation:** The LLM returns a raw SQL string.
4. **Safety Validation:** A deterministic Python function scans the SQL string to ensure no destructive keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`) are present.
5. **Local Execution:** If safe, the query is executed natively against the local SQLite database.
6. **Delivery:** Results are fetched locally and rendered in the Streamlit UI.

---

## 🚀 Installation & Setup

### Prerequisites
* Python 3.9+
* Google Gemini API Key

### 1. Clone the repository
```bash
git clone [https://github.com/huyducv/aipa-text-to-sql-agent.git](https://github.com/huyducv/aipa-text-to-sql-agent.git)
cd aipa-text-to-sql-agent
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set your API Key
Create a `.env` file in the root directory or set it in your terminal:
```bash
export GEMINI_API_KEY="your_api_key_here"
```

---

## 💻 Usage

### Step 1: Initialize the Database
Before running the app, you must convert the raw CSV files into the local SQLite database. Run the initialization script:
```bash
python scripts/init_database.py
```
*This script uses Pandas to ingest `students.csv`, `courses.csv`, and `grades.csv`, creating `university_agent.db`.*

### Step 2: Launch the App
Start the Streamlit interface:
```bash
streamlit run app.py
```

---

## 📁 Project Structure
```text
├── data/
│   ├── students.csv          # Raw data
│   ├── courses.csv           # Raw data
│   └── grades.csv            # Raw data
├── scripts/
│   └── init_database.py      # Pandas script to build SQLite .db
├── app.py                    # Streamlit frontend & master pipeline
├── core_logic.ipynb          # Jupyter Notebook used for initial testing/prompt engineering
├── university_agent.db       # Generated SQLite database (Ignored in .gitignore)
└── README.md
```

---

## 🔬 Critical Reflection & Trade-offs (Academic Evaluation)

This MVP was intentionally designed with specific constraints to explore the trade-offs of applied AI engineering:

* **Scalability vs. Context Limits:** The current architecture utilizes **Static Schema Injection**, which is highly efficient and 100% accurate for small-to-medium databases. However, for enterprise databases containing thousands of tables, this approach would exceed the LLM's context window. 
    * *Future Optimization:* Implementing a **Retrieval-Augmented Generation (RAG)** pipeline using vector embeddings to dynamically retrieve only the mathematically relevant table schemas before generating the SQL.
* **Flexibility vs. Security:** While GenAI is highly flexible, it introduces the risk of generating destructive code (e.g., hallucinating a `DROP TABLE` command). This project explicitly trades some generative flexibility for strict data security by routing all LLM outputs through a deterministic logic gate before local execution.
* **Cost vs. Latency:** By choosing `gemini-2.0-flash` over heavier models (like GPT-4 or Gemini 1.5 Pro), the system achieves near-instantaneous translation (low latency) at a fraction of the compute cost, which is the optimal configuration for a user-facing chatbot interface.