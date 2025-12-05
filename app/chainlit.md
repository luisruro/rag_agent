# Welcome to Invoice RAG Assistant 

This is a RAG (Retrieval-Augmented Generation) system for invoice and billing document analysis.

## Features

-  **Document Upload**: Upload PDF and text documents
-  **Smart Search**: MMR-based document retrieval
-  **Currency Conversion**: Automatic currency detection and conversion
-  **AI-Powered**: GPT-4o for intelligent responses
-  **Source Attribution**: See which documents were used

## How to Use

1. **Upload Documents**: Click the upload button (📎) to add invoice/billing documents
2. **Ask Questions**: Query about invoice amounts, dates, clients, etc.
3. **Get Answers**: The system retrieves relevant information and converts currencies automatically

## System Architecture

- **Vector Store**: Weaviate
- **Embedding Model**: OpenAI text-embedding-3-small
- **Query LLM**: GPT-4o-mini
- **Generation LLM**: GPT-4o
- **Retrieval**: MMR (Maximal Marginal Relevance)

## Authentication

Default credentials:
- User: `admin`
- Password: `1234`