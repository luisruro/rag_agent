 # app/rag_system.py
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from typing import TypedDict, List
import streamlit as st

from langchain_weaviate.vectorstores import WeaviateVectorStore
import weaviate

import os
from dotenv import load_dotenv
import re

from config import *
from prompts import *

# Load environment variables
load_dotenv()

# Try to import currency_exchange with error handling
CURRENCY_ENABLED = False
currency_exchanger = None

try:
    from currency_exchange import currency_exchanger
    # Test if API key is available
    if os.getenv("EXCHANGERATE_API_KEY"):
        CURRENCY_ENABLED = True
        print(" Currency exchange enabled with API key")
    else:
        print(" EXCHANGERATE_API_KEY not found. Currency conversion will use free APIs.")
        CURRENCY_ENABLED = True  # Still enabled but will use free APIs
except ImportError as e:
    print(f" Currency exchange module not found: {e}")
    # Create a dummy currency exchanger
    class DummyCurrencyExchanger:
        def extract_and_convert_amounts(self, text, target_currency="USD"):
            return []
        def convert_amount(self, amount, from_currency, to_currency):
            return amount
    currency_exchanger = DummyCurrencyExchanger()
except Exception as e:
    print(f" Error loading currency exchange: {e}")
    class DummyCurrencyExchanger:
        def extract_and_convert_amounts(self, text, target_currency="USD"):
            return []
        def convert_amount(self, amount, from_currency, to_currency):
            return amount
    currency_exchanger = DummyCurrencyExchanger()

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
    query_llm: ChatOpenAI
    generation_llm: ChatOpenAI
    vector_store: WeaviateVectorStore
    currency_conversions: List[dict]
    should_convert_currency: bool

# Initialize components
@st.cache_resource
def initialize_components():
    """Initialize all components once"""
    # Weaviate connection
    client = weaviate.connect_to_local(
        host=WEAVIATE_HOST,
        port=WEAVIATE_PORT
    )
    
    # Create embeddings
    embedding = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Create vector store
    vector_store = WeaviateVectorStore(
        client=client,
        index_name="DocumentChunk",
        text_key="text",
        embedding=embedding
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
    
    return vector_store, query_llm, generation_llm, client, embedding

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

def check_if_currency_needed(state: GraphState):
    """Check if currency conversion is needed for this query"""
    question = state["question"].lower()
    
    # Keywords that indicate currency/billing questions
    currency_keywords = [
        'bill', 'invoice', 'factura', 'payment', 'pago', 
        'cost', 'costo', 'price', 'precio', 'amount', 'cantidad',
        'total', 'balance', 'saldo', 'money', 'dinero',
        'dollar', 'dólar', 'euro', 'peso', 'currency', 'moneda',
        'convert', 'conversión', 'exchange', 'cambio',
        'usd', 'eur', 'mxn', 'gbp', 'jpy'
    ]
    
    # Check if any keyword is in the question
    should_convert = any(keyword in question for keyword in currency_keywords)
    
    return {"should_convert_currency": should_convert and CURRENCY_ENABLED}

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
        # Perform similarity search
        docs = vector_store.similarity_search_with_score(
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
                    # Simple similarity check
                    if doc.page_content[:100] == selected_doc.page_content[:100]:
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
        content_start = doc.page_content[:200]
        if content_start not in seen_content:
            seen_content.add(content_start)
            unique_docs.append(doc)
    
    return {"documents": unique_docs[:SEARCH_K]}

def format_context(state: GraphState):
    """Format retrieved documents into context"""
    formatted_context = format_docs(state["documents"])
    return {"context": formatted_context}

def generate_answer(state: GraphState):
    """Generate final answer using context with optional currency conversion"""
    generation_llm = state['generation_llm']
    context = state["context"]
    question = state["question"]
    should_convert = state.get("should_convert_currency", False)
    
    # Determine target currency based on question
    target_currency = "USD"
    
    # Check if user specified a different target currency
    question_lower = question.lower()
    if 'euro' in question_lower or 'eur' in question_lower:
        target_currency = "EUR"
    elif 'peso' in question_lower or 'mxn' in question_lower:
        target_currency = "MXN"
    elif 'pound' in question_lower or 'gbp' in question_lower:
        target_currency = "GBP"
    elif 'yen' in question_lower or 'jpy' in question_lower:
        target_currency = "JPY"
    
    # Extract and convert currencies from the GENERATED ANSWER (not from context)
    conversions = []
    if should_convert and CURRENCY_ENABLED and currency_exchanger:
        # First generate answer without currency conversion
        prompt = ChatPromptTemplate.from_template(RAG_TEMPLATE)
        chain = prompt | generation_llm
        initial_answer = chain.invoke({
            "context": context,
            "question": question
        }).content
        
        # Extract currency amounts from the generated answer
        try:
            conversions = currency_exchanger.extract_and_convert_amounts(
                initial_answer, 
                target_currency=target_currency
            )
        except Exception as e:
            print(f"Error in currency conversion: {e}")
            conversions = []
        
        # Generate enhanced answer with conversions
        if conversions:
            # Create a new prompt that includes conversion instructions
            enhanced_prompt = RAG_TEMPLATE + """
            
            ADDITIONAL CURRENCY INSTRUCTIONS:
            Your answer contains monetary amounts. For each monetary amount in your answer:
            1. Include the original currency and amount
            2. Add the equivalent in {target_currency} in parentheses
            3. Use the following conversions:
            {currency_conversions}
            
            Example format: "The invoice total was €100 (approximately $110 USD)"
            
            Make sure the conversions are accurate and clearly presented.
            """
            
            # Format currency conversions for the prompt
            conv_text = "Currency conversions found in your answer:\n"
            for conv in conversions:
                conv_text += f"- {conv['original_amount']} {conv['original_currency']} = {conv['converted_amount']} {target_currency} (rate: {conv['rate']})\n"
            
            prompt = ChatPromptTemplate.from_template(enhanced_prompt)
            chain = prompt | generation_llm
            response = chain.invoke({
                "context": context,
                "question": question,
                "currency_conversions": conv_text,
                "target_currency": target_currency
            })
            
            final_answer = response.content
        else:
            final_answer = initial_answer
    else:
        # Generate normal answer without currency conversion
        prompt = ChatPromptTemplate.from_template(RAG_TEMPLATE)
        chain = prompt | generation_llm
        response = chain.invoke({
            "context": context,
            "question": question
        })
        final_answer = response.content
    
    return {
        "answer": final_answer, 
        "currency_conversions": conversions if should_convert else [],
        "target_currency": target_currency if should_convert else None
    }

def build_rag_graph():
    """Build the LangGraph workflow"""
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("check_currency", check_if_currency_needed)
    workflow.add_node("generate_queries", generate_query_variations)
    workflow.add_node("retrieve", retrieve_documents)
    workflow.add_node("format_context", format_context)
    workflow.add_node("generate_answer", generate_answer)
    
    # Add edges
    workflow.add_edge("check_currency", "generate_queries")
    workflow.add_edge("generate_queries", "retrieve")
    workflow.add_edge("retrieve", "format_context")
    workflow.add_edge("format_context", "generate_answer")
    workflow.add_edge("generate_answer", END)
    
    # Set entry point
    workflow.set_entry_point("check_currency")
    
    return workflow.compile()

@st.cache_resource
def initialize_rag_system():
    """Initialize the complete RAG system"""
    vector_store, query_llm, generation_llm, client, embedding = initialize_components()
    
    # Build the graph
    graph = build_rag_graph()
    
    return graph, vector_store, query_llm, generation_llm, client

def query_rag(question):
    """Main function to query the RAG system"""
    try:
        # Get initialized components
        graph, vector_store, query_llm, generation_llm, client = initialize_rag_system()
        
        # Prepare initial state with ALL required components
        initial_state = {
            "question": question,
            "queries": [],
            "documents": [],
            "context": "",
            "answer": "",
            "query_llm": query_llm,
            "generation_llm": generation_llm,
            "vector_store": vector_store,
            "currency_conversions": [],
            "should_convert_currency": False
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
        
        return final_state["answer"], docs_info, final_state.get("currency_conversions", [])
        
    except Exception as e:
        error_msg = f'Could not process the query: {str(e)}'
        import traceback
        error_msg += f'\n\nDetailed error:\n{traceback.format_exc()}'
        return error_msg, [], []

def get_retriever_info():
    """Get retriever configuration information"""
    info = {
        "tipo": f'{SEARCH_TYPE.upper()} with LangGraph',
        "documentos": SEARCH_K,
        "diversidad": MMR_DIVERSITY_LAMBDA,
        "candidatos": MMR_FETCH_K,
        "umbral": None
    }
    
    # Add currency info
    if CURRENCY_ENABLED:
        info["currency"] = "Enabled (Smart detection)"
        if os.getenv("EXCHANGERATE_API_KEY"):
            info["currency_api"] = "ExchangeRate-API"
        else:
            info["currency_api"] = "Free APIs (Frankfurter/ECB)"
    else:
        info["currency"] = "Disabled"
    
    return info