# 📄 RAG Invoice Assistant

This project is a **Retrieval-Augmented Generation (RAG)** system built with **LangChain**, **OpenAI**, and **Streamlit**.  
It allows you to query and analyze PDF invoices, contracts, or other financial documents in natural language.

---

## 🚀 Features
- Query PDF invoices using natural language.
- Multi-query retriever (MMR + LangChain).
- Streamlit web interface.
- ChromaDB as vector store.
- Easy setup with **Docker** or **virtual environment**.

---

## 🐳 Run with Docker (recommended)

### 1️ Build the image

`docker compose build`

### 2️ Start the container

`docker compose up -d`

Then open http://localhost:8501 (or your configured port).

### 3️ Stop the container

`docker compose down`

🔁 Rebuild after code changes

If you modify any Python file or prompt, you must rebuild the image before running again:

`docker compose build`
`docker compose up -d`

🧰 Run with Virtual Environment

### 1️ Create and activate the environment Git Bash

`python -m venv .venv`
`source .venv/Scripts/activate`

### 2️ Install dependencies

`pip install -r requirements.txt`

### 3️ Set your environment variable

Make sure .env contains your OpenAI API key.

### 4️ Run the app

streamlit run app/app.py

Then visit http://localhost:8501