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

# Create open AI embeddings
embedding = OpenAIEmbeddings(
    model=EMBEDDING_MODEL,
    api_key=os.getenv("OPENAI_API_KEY")
)

# Weaviate connection
client = weaviate.connect_to_local(
    host="weaviate",
    port=8080
)

# create collection if not exists
collection_name = "DocumentChunk"
existing_collections = [c for c in client.collections.list_all()]

if collection_name not in existing_collections:
    client.collections.create(
        name=collection_name,
        description="Text chunks from PDFs with OpenAI embeddings",
        properties=[
            Property(name="text", data_type=DataType.TEXT),
            Property(name="source", data_type=DataType.TEXT),
            Property(name="chunk_index", data_type=DataType.INT),
        ],
        vectorizer_config=Configure.Vectorizer.none(),
    )

collection = client.collections.get(collection_name)
print("'DocumentChunk' collection ready to receive embeddings.")

# Insert the chunks into Weaviate
for i, doc in enumerate(tqdm(docs_split, desc="Cargando chunks en Weaviate")):
    vector = embedding.embed_query(doc.page_content)
    collection.data.insert(
        properties={
            "source": doc.metadata.get("source", "unknown"),
            "text": doc.page_content,
            "chunk_index": i,
        },
        vector=vector
    )

print("Knowledge base successfully created in Weaviate.")

#client.close()
