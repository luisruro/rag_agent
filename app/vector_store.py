from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

import weaviate
from weaviate.classes.config import Property, Configure, DataType
from tqdm import tqdm
import os
from dotenv import load_dotenv
from config import *

load_dotenv()

def create_vector_store():
    """Create and populate the vector store"""
    # Read PDFs
    loader = PyPDFDirectoryLoader("./app/data")
    documents = loader.load()
    print(f'{len(documents)} documents were uploaded from directory')
    
    # Create chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )
    docs_split = text_splitter.split_documents(documents)
    print(f'{len(docs_split)} text chunks were created')
    
    # Create OpenAI embeddings
    embedding = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Weaviate connection
    client = weaviate.connect_to_local(
        host="weaviate",
        port=8088
    )
    
    try:
        # Create collection if not exists
        collection_name = "DocumentChunk"
        
        # Check if collection exists
        if client.collections.exists(collection_name):
            print(f"Collection '{collection_name}' already exists")
            collection = client.collections.get(collection_name)
        else:
            # Create new collection
            collection = client.collections.create(
                name=collection_name,
                description="Text chunks from PDFs with OpenAI embeddings",
                properties=[
                    Property(name="source", data_type=DataType.TEXT),
                    Property(name="text", data_type=DataType.TEXT),
                    Property(name="page_label", data_type=DataType.TEXT),
                    Property(name="chunk_index", data_type=DataType.INT),
                ],
                vectorizer_config=Configure.Vectorizer.none(),
            )
            print(f"Collection '{collection_name}' created")
        
        print("'DocumentChunk' collection ready to receive embeddings.")
        
        # Check if collection already has data
        existing_count = collection.aggregate.over_all(total_count=True).total_count
        if existing_count > 0:
            print(f"Collection already has {existing_count} records. Skipping insertion.")
            return client, embedding
        
        # Insert the chunks into Weaviate
        batch_size = 50
        for i in range(0, len(docs_split), batch_size):
            batch = docs_split[i:i+batch_size]
            objects = []
            
            for j, doc in enumerate(batch):
                vector = embedding.embed_query(doc.page_content)
                objects.append({
                    "properties": {
                        "source": str(doc.metadata.get("source", "unknown")),
                        "text": doc.page_content,
                        "page_label": str(doc.metadata.get("page", "")),
                        "chunk_index": i + j,
                    },
                    "vector": vector
                })
            
            # Insert batch
            collection.data.insert_many(objects)
            print(f"Inserted batch {i//batch_size + 1}/{(len(docs_split)-1)//batch_size + 1}")
        
        print("Knowledge base successfully created in Weaviate.")
        return client, embedding
        
    finally:
        client.close()

if __name__ == "__main__":
    create_vector_store()