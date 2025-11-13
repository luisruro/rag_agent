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

## 🧰 Run with Virtual Environment

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

## Weaviate Vector Database Setup

This project uses Weaviate as a vector database to store and query embeddings generated with OpenAI.

### 🚀 How to Start Weaviate

1. Make sure Docker is installed and running.

2. Start Weaviate with the following command:

`docker-compose up -d`

This will launch Weaviate locally on the following ports:

- 8080 → REST API
- 50051 → gRPC

### ✅ Verify Weaviate is Running

You can check if the server is running by visiting:

👉 http://localhost:8080/v1/meta

### 📚 Collection Used

This project creates (if not already existing) a collection named DocumentChunk, which stores text fragments (chunks) extracted from PDF documents along with their embeddings.

**Main properties:**

- text: The chunk text content
- source: The original PDF file the chunk came from
- chunk_index: The position of the chunk within the document