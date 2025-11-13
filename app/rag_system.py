from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_classic.retrievers.multi_query import MultiQueryRetriever
import streamlit as st

from langchain_weaviate.vectorstores import WeaviateVectorStore
import weaviate

import os
from dotenv import load_dotenv

from config import *
from prompts import *
from vector_store import embedding, client

@st.cache_resource
def initialize_rag_system():

    vector_store = WeaviateVectorStore(
        client=client,
        index_name="DocumentChunk",  # 👈 debe coincidir con el nombre que creaste en vector_store.py
        text_key="text",             # 👈 el campo donde guardaste el contenido
        embedding=embedding
    )
    
    # Modelos
    llm_queries = ChatOpenAI(model=QUERY_MODEL, temperature=0)
    llm_generation = ChatOpenAI(model=GENERATION_MODEL, temperature=0)
    
    #No solo se centra en la similutd si no en la diversidad, es mas avanzado que el de similitud de coseno
    # Retriever MMR (Maxima Margin Relevance)
    base_retriever = vector_store.as_retriever(
        search_type = SEARCH_TYPE,
        search_kwargs = {
            "k" : SEARCH_K,
            "lambda_mult": MMR_DIVERSITY_LAMBDA,
            "fetch_k" : MMR_FETCH_K
        }
        
    )
    
    # Customized prompt for MultiQueryRetriever
    multi_query_prompt = PromptTemplate.from_template(MULTI_QUERY_PROMPT)
    
    # MultiQueryRetriever with customized prompt
    mmr_multi_retriever = MultiQueryRetriever.from_llm(
        retriever=base_retriever,
        llm=llm_queries,
        prompt=multi_query_prompt
    )
    
    prompt = PromptTemplate.from_template(RAG_TEMPLATE)
    
    # function to format and preprocess the recovered documents
    def format_docs(docs):
        formatted = []
        
        for i, doc in enumerate(docs, 1):
            header = f'[Fragment {1}]'
            if doc.metadata:
                if 'source' in doc.metadata:
                    source = doc.metadata['source'].split("\\")[-1] if '\\' in doc.metadata['source'] else doc.metadata['source']
                    header += f' - Source: {source}'
                if 'page_label' in doc.metadata:
                    header += f" - Pagina: {doc.metadata['page_label']}"
                    
            content = doc.page_content.strip()
            formatted.append(f'{header}\n{content}')
            
        return "\n\n".join(formatted)
    
    rag_chain = (
        {
            "context" : mmr_multi_retriever | format_docs,
            "question" : RunnablePassthrough()
        }
        | prompt 
        | llm_generation 
        | StrOutputParser()
    )
    
    return rag_chain, mmr_multi_retriever

def query_rag(question):
    try:
        rag_chain, retriever = initialize_rag_system()
        
        # Get Answer
        response = rag_chain.invoke(question)
        
        # Get docs to show them
        docs = retriever.invoke(question)
        
        # Format docs to show
        docs_info = []
        for i, doc in enumerate(docs[:SEARCH_K], 1):
            doc_info = {
                "fragment" : i,
                "content" : doc.page_content[:1000] + "..." if len(doc.page_content) > 1000 else doc.page_content,
                "source" : doc.metadata.get('source', 'No specified').split("\\")[-1],
                "page" : doc.metadata.get('page_label', 'No specified')
            }
            docs_info.append(doc_info)
            
        return response, docs_info
    except Exception as e:
        error_msg = f'Could not process the query: {str(e)}'
        return error_msg, []
    
def get_retriever_info():
    """Obtiene información sobre la configuración del retriever"""
    return{
        "tipo" : f'{SEARCH_TYPE.upper()}',
        "documentos" : SEARCH_K,
        "diversidad" : MMR_DIVERSITY_LAMBDA,
        "candidatos" : MMR_FETCH_K,
        "umbral" : None
    }