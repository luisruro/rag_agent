from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Annotated
import operator
import streamlit as st

from langchain_weaviate.vectorstores import WeaviateVectorStore
import weaviate

import os
from dotenv import load_dotenv

from config import *
from prompts import *

# Load environment variables
load_dotenv()

# Define state schema
class GraphState(TypedDict):
    """State for the RAG graph"""
    question: str
    queries: List[str]
    documents: List[dict]
    context: str
    answer: str

# Initialize components
@st.cache_resource
def initialize_components():
    """Initialize all components once"""
    # Weaviate vector store
    client = weaviate.connect_to_local(
        host="weaviate",
        port=8080
    )
    
    vector_store = WeaviateVectorStore(
        client=client,
        index_name="DocumentChunk",
        text_key="text",
        embedding=OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            api_key=os.getenv("OPENAI_API_KEY")
        )
    )
    
    # LLMs
    query_llm = ChatOpenAI(
        model=QUERY_MODEL,
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    generation_llm = ChatOpenAI(
        model=GENERATION_MODEL,
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    return vector_store, query_llm, generation_llm, client

def format_docs(docs):
    """Format documents for context"""
    formatted = []
    
    for i, doc in enumerate(docs, 1):
        header = f'[Fragment {i}]'
        if doc.metadata:
            if 'source' in doc.metadata:
                source = doc.metadata['source'].split("\\")[-1] if '\\' in doc.metadata['source'] else doc.metadata['source']
                header += f' - Source: {source}'
            if 'page_label' in doc.metadata:
                header += f" - Pagina: {doc.metadata['page_label']}"
                
        content = doc.page_content.strip()
        formatted.append(f'{header}\n{content}')
        
    return "\n\n".join(formatted)

def generate_query_variations(state: GraphState):
    """Generate multiple query variations"""
    query_llm = state['query_llm']
    
    prompt = ChatPromptTemplate.from_template(
        "Generate exactly 3 different versions of this query for document retrieval:\n\n"
        "Original: {question}\n\n"
        "Variations (one per line, no numbering):"
    )
    
    chain = prompt | query_llm
    response = chain.invoke({"question": state["question"]})
    
    # Parse the response into 3 queries
    queries = [state["question"]]  # Always include original query
    variations = [line.strip() for line in response.content.split('\n') if line.strip()]
    queries.extend(variations[:3])  # Add up to 3 variations
    
    return {"queries": queries}

def retrieve_documents(state: GraphState):
    """Retrieve documents using MMR search"""
    vector_store = state['vector_store']
    queries = state['queries']
    
    all_docs = []
    
    for query in queries:
        # Perform MMR search
        docs = vector_store.similarity_search_with_relevance_scores(
            query=query,
            k=MMR_FETCH_K
        )
        
        # Apply MMR diversity manually
        if len(docs) > SEARCH_K:
            # Simple MMR implementation
            selected_docs = []
            docs_scores = sorted(docs, key=lambda x: x[1], reverse=True)
            
            for doc, score in docs_scores:
                if len(selected_docs) >= SEARCH_K:
                    break
                # Check similarity with already selected docs
                should_add = True
                for selected_doc, _ in selected_docs:
                    # Simple similarity check (can be enhanced)
                    if doc.page_content[:50] == selected_doc.page_content[:50]:
                        should_add = False
                        break
                
                if should_add:
                    selected_docs.append((doc, score))
            
            docs = selected_docs
        
        all_docs.extend([doc for doc, _ in docs[:SEARCH_K]])
    
    # Remove duplicates
    unique_docs = []
    seen_content = set()
    for doc in all_docs:
        content_start = doc.page_content[:100]
        if content_start not in seen_content:
            seen_content.add(content_start)
            unique_docs.append(doc)
    
    return {"documents": unique_docs[:SEARCH_K]}

def format_context(state: GraphState):
    """Format retrieved documents into context"""
    formatted_context = format_docs(state["documents"])
    return {"context": formatted_context}

def generate_answer(state: GraphState):
    """Generate final answer using context"""
    generation_llm = state['generation_llm']
    
    prompt = ChatPromptTemplate.from_template(RAG_TEMPLATE)
    
    chain = prompt | generation_llm
    response = chain.invoke({
        "context": state["context"],
        "question": state["question"]
    })
    
    return {"answer": response.content}

def build_rag_graph():
    """Build the LangGraph workflow"""
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("generate_queries", generate_query_variations)
    workflow.add_node("retrieve", retrieve_documents)
    workflow.add_node("format_context", format_context)
    workflow.add_node("generate_answer", generate_answer)
    
    # Add edges
    workflow.add_edge("generate_queries", "retrieve")
    workflow.add_edge("retrieve", "format_context")
    workflow.add_edge("format_context", "generate_answer")
    workflow.add_edge("generate_answer", END)
    
    # Set entry point
    workflow.set_entry_point("generate_queries")
    
    return workflow.compile()

@st.cache_resource
def initialize_rag_system():
    """Initialize the complete RAG system"""
    vector_store, query_llm, generation_llm, client = initialize_components()
    
    # Build the graph
    graph = build_rag_graph()
    
    return graph, vector_store, query_llm, generation_llm, client

def query_rag(question):
    """Main function to query the RAG system"""
    try:
        # Get initialized components
        graph, vector_store, query_llm, generation_llm, client = initialize_rag_system()
        
        # Prepare initial state
        initial_state = {
            "question": question,
            "queries": [],
            "documents": [],
            "context": "",
            "answer": "",
            "vector_store": vector_store,
            "query_llm": query_llm,
            "generation_llm": generation_llm
        }
        
        # Execute the graph
        final_state = graph.invoke(initial_state)
        
        # Format documents for display
        docs_info = []
        for i, doc in enumerate(final_state["documents"][:5], 1):
            doc_info = {
                "fragment": i,
                "content": doc.page_content[:1000] + "..." if len(doc.page_content) > 1000 else doc.page_content,
                "source": doc.metadata.get('source', 'No specified').split("\\")[-1],
                "page": doc.metadata.get('page_label', 'No specified')
            }
            docs_info.append(doc_info)
        
        return final_state["answer"], docs_info
        
    except Exception as e:
        error_msg = f'Could not process the query: {str(e)}'
        return error_msg, []

def get_retriever_info():
    """Get retriever configuration information"""
    return {
        "tipo": f'{SEARCH_TYPE.upper()} with LangGraph',
        "documentos": SEARCH_K,
        "diversidad": MMR_DIVERSITY_LAMBDA,
        "candidatos": MMR_FETCH_K,
        "umbral": None
    }