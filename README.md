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

### 3 Credentials

**user**: admin

**Password**: 1234

### 3️ Stop the container

`docker compose down`

🔁 Rebuild after code changes

If you modify any Python file or prompt, you must rebuild the image before running again:

`docker compose build`
`docker compose up -d`

## 🧰 Run with UV (Python Environment + Dependencies)

### 1️ Install uv (if you don’t have it locally) Git Bash

`curl -LsSf https://astral.sh/uv/install.sh | sh`

### 2️ Sync dependencies

`uv sync`

### 3️ Set your environment variable

Make sure .env contains your OpenAI API key.

### 4️ Run the app
`docker compose up -d`
`uv run streamlit run app/app.py`

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

## 📊 Langfuse Integration (LLM Observability)

This project uses Langfuse to track prompts, responses, performance, and LLM costs.
Langfuse runs as a separate service, and this application connects to it only through the SDK.

### 🚀 How to Run Langfuse

1. Clone the official Langfuse repository.
`git clone https://github.com/langfuse/langfuse.git`
`cd langfuse`

2. Start the Langfuse service using Docker
`docker compose up`

Once it finishes starting, open http://localhost:3000 in your browser to access the Langfuse UI.

3. Create an account (only the first time)

4. Generate API keys and add them to your **.env** file
```
LANGFUSE_SECRET_KEY=sk-xxxxx 
LANGFUSE_PUBLIC_KEY=pk-xxxxx
```

5. Rebuild your application image (so it loads the new .env values)

`docker compose build`
`docker compose up -d`

### Notes

If you deploy Langfuse in the cloud later, only change the LANGFUSE_HOST value.
