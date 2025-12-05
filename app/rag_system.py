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
        def get_currency_for_country(self, country):
            return "USD"
        def get_currency_for_address(self, address):
            return "USD"
        def get_country_from_address(self, address):
            return None
        def enhance_answer_with_conversion(self, answer, shipping_address):
            return answer
    currency_exchanger = DummyCurrencyExchanger()
except Exception as e:
    print(f" Error loading currency exchange: {e}")
    class DummyCurrencyExchanger:
        def extract_and_convert_amounts(self, text, target_currency="USD"):
            return []
        def convert_amount(self, amount, from_currency, to_currency):
            return amount
        def get_currency_for_country(self, country):
            return "USD"
        def get_currency_for_address(self, address):
            return "USD"
        def get_country_from_address(self, address):
            return None
        def enhance_answer_with_conversion(self, answer, shipping_address):
            return answer
    currency_exchanger = DummyCurrencyExchanger()

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
    shipping_address: str
    destination_country: str
    dest_currency: str

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

def extract_shipping_address(context):
    """Extract shipping address from context"""
    # Look for shipping address patterns
    patterns = [
        r'Ship To:\s*(.+?)(?:\n|$)',
        r'Shipping Address:\s*(.+?)(?:\n|$)',
        r'Address:\s*(.+?)(?:\n|$)',
        r'Destination:\s*(.+?)(?:\n|$)',
        r'Deliver To:\s*(.+?)(?:\n|$)',
        r'Shipped to:\s*(.+?)(?:\n|$)',
        r'Bill To:\s*(.+?)(?:\n|$)',
        r'Invoice To:\s*(.+?)(?:\n|$)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, context, re.IGNORECASE | re.DOTALL)
        if match:
            # Clean up the address - take first 200 chars max
            address = match.group(1).strip()
            # Remove any additional labels that might be captured
            address = re.sub(r'^\s*(?:Name|Contact|Phone|Email|Date|Invoice).*?:.*?$', '', address, flags=re.MULTILINE | re.IGNORECASE)
            address = ' '.join(address.split('\n')[:3]).strip()  # Take first 3 lines
            if address:
                return address
    
    return None

def extract_country_from_address(address):
    """Extract country from shipping address"""
    if not address:
        return None
    
    # Country detection patterns
    country_patterns = [
        # Common country names
        (r'\b(?:United States|USA|U\.S\.A\.|US)\b', 'United States'),
        (r'\b(?:Mexico|México|Mex)\b', 'Mexico'),
        (r'\b(?:Canada|CAN|Ca)\b', 'Canada'),
        (r'\b(?:United Kingdom|UK|U\.K\.|Great Britain|England|Scotland|Wales|Northern Ireland)\b', 'United Kingdom'),
        (r'\b(?:France|FR|FRA)\b', 'France'),
        (r'\b(?:Germany|DE|DEU|Deutschland)\b', 'Germany'),
        (r'\b(?:Spain|ES|ESP|España)\b', 'Spain'),
        (r'\b(?:Italy|IT|ITA|Italia)\b', 'Italy'),
        (r'\b(?:Russia|RU|RUS|Russian Federation|Россия)\b', 'Russia'),
        (r'\b(?:Japan|JP|JPN|日本)\b', 'Japan'),
        (r'\b(?:China|CN|CHN|中国)\b', 'China'),
        (r'\b(?:Brazil|BR|BRA|Brasil)\b', 'Brazil'),
        (r'\b(?:Australia|AU|AUS)\b', 'Australia'),
        (r'\b(?:India|IN|IND)\b', 'India'),
        (r'\b(?:South Korea|Korea|KR|KOR|한국|대한민국)\b', 'South Korea'),
        
        # Country codes (ISO 3166-1 alpha-3)
        (r'\bMEX\b', 'Mexico'),
        (r'\bGBR\b', 'United Kingdom'),
        (r'\bFRA\b', 'France'),
        (r'\bDEU\b', 'Germany'),
        (r'\bESP\b', 'Spain'),
        (r'\bITA\b', 'Italy'),
        (r'\bRUS\b', 'Russia'),
        (r'\bJPN\b', 'Japan'),
        (r'\bCHN\b', 'China'),
        (r'\bBRA\b', 'Brazil'),
        (r'\bAUS\b', 'Australia'),
        (r'\bIND\b', 'India'),
        (r'\bKOR\b', 'South Korea'),
    ]
    
    # First try to find country in address
    for pattern, country in country_patterns:
        if re.search(pattern, address, re.IGNORECASE):
            return country
    
    # If no country found, try to extract from common patterns
    # Look for city, state/province patterns that might indicate country
    if re.search(r'\b(?:Paris|Lyon|Marseille|Nice|Toulouse)\b', address, re.IGNORECASE):
        return 'France'
    elif re.search(r'\b(?:Berlin|Munich|Hamburg|Frankfurt|Cologne)\b', address, re.IGNORECASE):
        return 'Germany'
    elif re.search(r'\b(?:Madrid|Barcelona|Valencia|Seville|Bilbao)\b', address, re.IGNORECASE):
        return 'Spain'
    elif re.search(r'\b(?:Rome|Milan|Naples|Turin|Florence)\b', address, re.IGNORECASE):
        return 'Italy'
    elif re.search(r'\b(?:Moscow|St\. Petersburg|Saint Petersburg|Novosibirsk|Yekaterinburg)\b', address, re.IGNORECASE):
        return 'Russia'
    elif re.search(r'\b(?:Tokyo|Osaka|Kyoto|Yokohama|Nagoya)\b', address, re.IGNORECASE):
        return 'Japan'
    elif re.search(r'\b(?:Beijing|Shanghai|Guangzhou|Shenzhen|Chengdu)\b', address, re.IGNORECASE):
        return 'China'
    
    return None

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
        'usd', 'eur', 'mxn', 'gbp', 'jpy', 'rub'
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
    """Format retrieved documents into context and extract shipping address"""
    formatted_context = format_docs(state["documents"])
    
    # Extract shipping address from context
    shipping_address = extract_shipping_address(formatted_context)
    
    # Extract country from address
    destination_country = None
    dest_currency = "USD"
    
    if shipping_address and CURRENCY_ENABLED and currency_exchanger:
        # Try to get country from address
        destination_country = extract_country_from_address(shipping_address)
        
        if destination_country:
            # Get currency for country
            try:
                dest_currency = currency_exchanger.get_currency_for_country(destination_country)
            except:
                # Fallback to address-based detection
                dest_currency = currency_exchanger.get_currency_for_address(shipping_address)
        else:
            # Fallback if no country detected
            dest_currency = currency_exchanger.get_currency_for_address(shipping_address)
    
    return {
        "context": formatted_context,
        "shipping_address": shipping_address,
        "destination_country": destination_country,
        "dest_currency": dest_currency
    }

def generate_answer(state: GraphState):
    """Generate final answer using context with optional currency conversion"""
    generation_llm = state['generation_llm']
    context = state["context"]
    question = state["question"]
    should_convert = state.get("should_convert_currency", False)
    shipping_address = state.get("shipping_address")
    destination_country = state.get("destination_country")
    dest_currency = state.get("dest_currency", "USD")
    
    # Create the prompt with all required variables
    prompt = ChatPromptTemplate.from_template(RAG_TEMPLATE)
    
    # Prepare variables for the template
    template_vars = {
        "context": context,
        "question": question,
        "shipping_address": shipping_address or "Not specified"
    }
    
    # Generate answer
    chain = prompt | generation_llm
    initial_answer = chain.invoke(template_vars).content
    
    # Apply currency conversion if needed
    conversions = []
    final_answer = initial_answer
    
    if should_convert and CURRENCY_ENABLED and currency_exchanger:
        if shipping_address and shipping_address != "Not specified":
            try:
                # Enhance answer with conversion
                final_answer = currency_exchanger.enhance_answer_with_conversion(
                    initial_answer, 
                    shipping_address
                )
                
                # Also extract conversions for display
                conversions = currency_exchanger.extract_and_convert_amounts(
                    initial_answer,
                    target_currency=dest_currency
                )
            except Exception as e:
                print(f"Error in currency conversion: {e}")
                final_answer = initial_answer + f"\n\n*Note: Currency conversion failed: {str(e)}*"
    
    return {
        "answer": final_answer, 
        "currency_conversions": conversions,
        "dest_currency": dest_currency if should_convert else None,
        "shipping_address": shipping_address,
        "destination_country": destination_country
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
            "should_convert_currency": False,
            "shipping_address": None,
            "destination_country": None,
            "dest_currency": "USD"
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
        info["currency"] = "Enabled (Destination-based)"
        info["currency_logic"] = "Converts to shipping destination currency"
        if os.getenv("EXCHANGERATE_API_KEY"):
            info["currency_api"] = "ExchangeRate-API"
        else:
            info["currency_api"] = "Free APIs (Frankfurter/ECB)"
    else:
        info["currency"] = "Disabled"
    
    return info