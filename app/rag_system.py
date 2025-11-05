from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
#from langchain.prompts import PromptTemplate
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
#from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain_classic.retrievers.multi_query import MultiQueryRetriever
import streamlit as st

import os
from dotenv import load_dotenv

from config import *
from prompts import *
from vector_store import embedding

def initialize_rag_system():
    
    # Vector Store
    vector_store = Chroma(
        embedding_function=embedding,
        persist_directory=CHROMA_DB_PATH
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
    
    rag_chain = (
        {
            "context" : mmr_multi_retriever,
            "question" : RunnablePassthrough()
        }
        | prompt 
        | llm_generation 
        | StrOutputParser()
    )
    
    return rag_chain, mmr_multi_retriever