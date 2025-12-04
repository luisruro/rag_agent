# app/vector_store.py
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

import weaviate
from weaviate.classes.config import Property, Configure, DataType
import os
from dotenv import load_dotenv
from config import *

load_dotenv()

def create_vector_store():
    """Create and populate the vector store"""
    print("Loading PDFs into Vector Store")
    
    # Read PDFs
    loader = PyPDFDirectoryLoader("./app/data")
    documents = loader.load()
    print(f'Loaded {len(documents)} documents from PDFs')
    
    # Create chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )
    docs_split = text_splitter.split_documents(documents)
    print(f'Created {len(docs_split)} text chunks')
    
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
    
    # Create collection if not exists
    collection_name = "DocumentChunk"
    
    # Check if collection exists
    if client.collections.exists(collection_name):
        print(f"Collection '{collection_name}' already exists")
        collection = client.collections.get(collection_name)
    else:
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
    
    print("Inserting documents into Weaviate")
    
    # Prepare data for insertion
    objects_to_insert = []
    for i, doc in enumerate(docs_split):
        try:
            # Generate embedding
            vector = embedding.embed_query(doc.page_content)
            
            # Create data object
            data_object = {
                "source": str(doc.metadata.get("source", "unknown")),
                "text": doc.page_content,
                "page_label": str(doc.metadata.get("page", "")),
                "chunk_index": i,
            }
            
            objects_to_insert.append({
                "properties": data_object,
                "vector": vector
            })
            
        except Exception as e:
            print(f"Error preparing document {i}: {e}")
            continue
    
    # Insert documents one by one
    inserted_count = 0
    for i, obj in enumerate(objects_to_insert):
        try:
            collection.data.insert(
                properties=obj["properties"],
                vector=obj["vector"]
            )
            inserted_count += 1
            if (i + 1) % 10 == 0:
                print(f"Inserted {i + 1}/{len(objects_to_insert)} documents")
                
        except Exception as e:
            print(f"Error inserting document {i}: {e}")
            continue
    
    print(f"Successfully inserted {inserted_count}/{len(objects_to_insert)} documents")
    
    # Verify
    count = collection.aggregate.over_all(total_count=True).total_count
    print(f"Total documents in vector store: {count}")
    
    if count > 0:
        print("Vector store is ready")
        # Show a sample
        response = collection.query.fetch_objects(limit=1)
        if response.objects:
            obj = response.objects[0]
            print(f"\nSample document:")
            print(f"Source: {obj.properties.get('source', 'N/A')}")
            print(f"Page: {obj.properties.get('page_label', 'N/A')}")
            text = obj.properties.get('text', '')[:200]
            print(f"Text: {text}...")
    else:
        print("Failed to insert documents")
        print("Check your OpenAI API key in the .env file")
    
    client.close()
    return embedding

if __name__ == "__main__":
    create_vector_store()