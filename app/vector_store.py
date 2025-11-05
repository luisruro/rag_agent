from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

import os
from dotenv import load_dotenv
from config import *

load_dotenv()

loader = PyPDFDirectoryLoader("./app/data")
documents = loader.load()

print(f'{len(documents)} documents were uploaded from directory')

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size = 5000,
    chunk_overlap = 1000
)

docs_split = text_splitter.split_documents(documents)

print(f'{len(docs_split)} text chunks were created')

embedding = OpenAIEmbeddings(
    model=EMBEDDING_MODEL,
    api_key=os.getenv("OPENAI_API_KEY")
)

vectorstore = Chroma.from_documents(
    docs_split,
    embedding= embedding,
    persist_directory="./app/chroma_db"
)

# query = "¿en que mes se efectuó la compra en el almacen Exito?"

# output = vectorstore.similarity_search(query, k=2)

# print("Similar documents in the query: \n")
# for i, doc in enumerate(output, start=1):
#     print(f'Content = {doc.page_content}')
#     print(f'Metadata = {doc.metadata}')

