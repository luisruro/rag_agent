from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

import weaviate
from weaviate.classes.config import Property, Configure, DataType
from tqdm import tqdm
import os
from dotenv import load_dotenv
from config import *

# 1️⃣ Cargar variables de entorno
load_dotenv()

# 2️⃣ Leer los PDF
loader = PyPDFDirectoryLoader("./app/data")
documents = loader.load()
print(f'{len(documents)} documents were uploaded from directory')

# 3️⃣ Dividir en chunks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100
)
docs_split = text_splitter.split_documents(documents)
print(f'{len(docs_split)} text chunks were created')

# 4️⃣ Crear embeddings de OpenAI
embedding = OpenAIEmbeddings(
    model=EMBEDDING_MODEL,
    api_key=os.getenv("OPENAI_API_KEY")
)

# 5️⃣ Conectar con Weaviate
client = weaviate.connect_to_local(
    host="weaviate",
    port=8080
)

# 6️⃣ Crear la colección si no existe
collection_name = "DocumentChunk"
existing_collections = [c for c in client.collections.list_all()]

if collection_name not in existing_collections:
    client.collections.insert(
        name=collection_name,
        description="Chunks de texto de los PDF con embeddings de OpenAI",
        properties=[
            Property(name="text", data_type=DataType.TEXT),
            Property(name="source", data_type=DataType.TEXT),
            Property(name="chunk_index", data_type=DataType.INT),
        ],
        vectorizer_config=Configure.Vectorizer.none(),
    )

collection = client.collections.get(collection_name)
print("✅ Colección 'DocumentChunk' lista para recibir embeddings.")

# 7️⃣ Insertar los chunks en Weaviate (solo una vez)
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

print("✅ Base de conocimiento creada exitosamente en Weaviate.")

# 8️⃣ Verificar inserción
response = collection.query.fetch_objects(limit=3)
for obj in response.objects:
    print(f"📄 {obj.properties['source']}")
    print(obj.properties['text'][:300])
    print("—" * 60)

#client.close()
