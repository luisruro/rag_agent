from typing import TypedDict, List, Dict, Optional
from langgraph.graph import StateGraph, END, START
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_weaviate.vectorstores import WeaviateVectorStore
import weaviate
import os
import re
from dotenv import load_dotenv

from config import *
from prompts import *
from currency_exchange import currency_exchanger
from invoice_model import Invoice
from structured_extraction import extract_structured_invoice, format_invoice_response

load_dotenv()

# State definition
class GraphState(TypedDict):
    """State of the graph"""
    question: str
    is_specific_query: bool
    generated_queries: List[str]
    documents: List
    formatted_context: str
    detected_country: str
    target_currency: str
    structured_invoice: Optional[Invoice]
    currency_conversions: List[Dict]
    response: str
    docs_info: List[dict]
    
client = weaviate.connect_to_local(
    host=WEAVIATE_HOST,
    port=WEAVIATE_PORT
)

embedding = OpenAIEmbeddings(
    model=EMBEDDING_MODEL,
    api_key=os.getenv("OPENAI_API_KEY")
)

vector_store = WeaviateVectorStore(
    client=client,
    index_name="DocumentChunk",
    text_key="text",
    embedding=embedding
)

llm_queries = ChatOpenAI(model=QUERY_MODEL, temperature=0)
llm_generation = ChatOpenAI(model=GENERATION_MODEL, temperature=0)

# Retriever with MMR
base_retriever = vector_store.as_retriever(
    search_type=SEARCH_TYPE,
    search_kwargs={
        "k": SEARCH_K,
        "lambda_mult": MMR_DIVERSITY_LAMBDA,
        "fetch_k": MMR_FETCH_K
    }
)

COUNTRY_CURRENCY_MAP = {
    "russia": "RUB",
    "dominican republic": "DOP",
    "pakistan": "PKR",
    "australia": "AUD",
    "germany": "EUR",
    "austria": "EUR",
    "turkey": "TRY",
    "liberia": "LRD",
    "sweden": "SEK",
    "zambia": "ZMW",
    "china": "CNY",
    "cote d'ivoire": "XOF",
    "india": "INR",
    "new zealand": "NZD",
    "bangladesh": "BDT",
    "spain": "EUR",
    "france": "EUR",
    "brazil": "BRL",
    "guatemala": "GTQ",
    "mexico": "MXN",
    "méxico": "MXN",
    "canada": "CAD",
    "united kingdom": "GBP",
    "uk": "GBP",
    "germany": "EUR",
    "france": "EUR",
    "spain": "EUR",
    "italy": "EUR",
    "colombia": "COP",
    "argentina": "ARS",
    "chile": "CLP",
    "peru": "PEN",
    "brazil": "BRL",
    "usa": "USD",
    "united states": "USD",
}

def detect_specific_query(question: str) -> bool:
    """
    Detect if the user is asking for a specific piece of information
    vs. a general overview
    
    Returns False for queries asking for "all invoices" or multiple items
    """
    question_lower = question.lower()
    
    # If asking for "all" or multiple invoices, it's NOT specific
    if any(keyword in question_lower for keyword in ['all invoices', 'all invoice', 'multiple invoice', 'list of invoice', 'every invoice']):
        return False
    
    specific_patterns = [
        r'\bjust\b.*\bthe\b',           # "just the balance"
        r'\bonly\b.*\bthe\b',           # "only the amount"
        r'\bwhat\s+is\s+the\b',         # "what is the balance"
        r'\bwhat\'?s\s+the\b',          # "what's the total"
        r'\bhow\s+much\b',              # "how much is"
        r'\bget\s+(?:me\s+)?the\b',     # "get the invoice number"
        r'\bshow\s+(?:me\s+)?the\b',    # "show the date"
        r'\btell\s+me\s+the\b',         # "tell me the amount"
        r'\bgive\s+me\s+the\b',         # "give me the balance"
    ]
    
    for pattern in specific_patterns:
        if re.search(pattern, question_lower):
            return True
    
    return False

def detect_country_from_context(context: str) -> str:
    """Detect country from ship_to address in context"""
    context_lower = context.lower()
    
    # Look for country patterns in ship_to sections
    ship_to_pattern = r'ship\s+to[:\s]+(.*?)(?:\n|$)'
    matches = re.finditer(ship_to_pattern, context_lower, re.MULTILINE | re.IGNORECASE)
    
    for match in matches:
        ship_info = match.group(1).lower()
        
        # Check for country names
        for country, currency in COUNTRY_CURRENCY_MAP.items():
            if country in ship_info:
                print(f"   Detected country: {country.upper()} -> Currency: {currency}")
                return country
    
    # Also check for country field explicitly
    country_pattern = r'country[:\s]+([\w\s]+?)(?:\n|,|$)'
    country_matches = re.finditer(country_pattern, context_lower, re.MULTILINE | re.IGNORECASE)
    
    for match in country_matches:
        country_text = match.group(1).strip().lower()
        for country, currency in COUNTRY_CURRENCY_MAP.items():
            if country in country_text:
                print(f"   Detected country: {country.upper()} -> Currency: {currency}")
                return country
    
    print("No country detected, defaulting to USA")
    return "usa"

def get_currency_for_country(country: str) -> str:
    """Get currency code for a country"""
    return COUNTRY_CURRENCY_MAP.get(country.lower(), "USD")

# Node Functions

def classify_query_node(state: GraphState) -> GraphState:
    """Classify if the query is specific or general"""
    
    question = state["question"]
    is_specific = detect_specific_query(question)
    
    query_type = "SPECIFIC" if is_specific else "GENERAL"
    print(f"Query classified as: {query_type}")
    
    return {
        "is_specific_query": is_specific
    }
    
def generate_queries_node(state: GraphState) -> GraphState:
    """Generate multiple query variations using LLM"""

    question = state["question"]
    
    # Create prompt for query generation
    multi_query_prompt = PromptTemplate.from_template(MULTI_QUERY_PROMPT)
    
    # Generate queries
    query_chain = multi_query_prompt | llm_queries | StrOutputParser()
    generated_text = query_chain.invoke({"question": question})
    
    # Parse queries (one per line)
    queries = [q.strip() for q in generated_text.split("\n") if q.strip()]
    
    # Include original question
    all_queries = [question] + queries
    
    print(f"Generated {len(all_queries)} queries")
    
    return {
        "generated_queries": all_queries
    }
    
def retrieve_documents_node(state: GraphState) -> GraphState:
    """Retrieve documents for all generated queries using MMR"""
    
    queries = state["generated_queries"]
    all_docs = []
    
    # Retrieve docs for each query
    for query in queries:
        docs = base_retriever.invoke(query)
        all_docs.extend(docs)
    
    # Deduplicate based on content
    unique_docs = []
    seen_content = set()
    
    for doc in all_docs:
        content_hash = hash(doc.page_content)
        if content_hash not in seen_content:
            seen_content.add(content_hash)
            unique_docs.append(doc)
    
    print(f"Retrieved {len(unique_docs)} unique documents")
    
    return {
        "documents": unique_docs
    }
    
def format_context_node(state: GraphState) -> GraphState:
    """Format retrieved documents into context string"""
    
    docs = state["documents"]
    formatted = []
    docs_info = []
    
    # Limit documents for context generation
    for i, doc in enumerate(docs[:SEARCH_K], 1):
        header = f'[Fragment {i}]'
        if doc.metadata:
            if 'source' in doc.metadata:
                source = doc.metadata['source'].split("\\")[-1] if '\\' in doc.metadata['source'] else doc.metadata['source']
                header += f' - Source: {source}'
            if 'page_label' in doc.metadata:
                header += f" - Page: {doc.metadata['page_label']}"
        
        content = doc.page_content.strip()
        formatted.append(f'{header}\n{content}')
    
    # Store only top 5 most relevant docs for UI display
    TOP_DOCS_FOR_UI = 5
    for i, doc in enumerate(docs[:TOP_DOCS_FOR_UI], 1):
        doc_info = {
            "fragment": i,
            "content": doc.page_content[:1000] + "..." if len(doc.page_content) > 1000 else doc.page_content,
            "source": doc.metadata.get('source', 'Not specified').split("\\")[-1] if doc.metadata.get('source') else 'Not specified',
            "page": doc.metadata.get('page_label', 'Not specified')
        }
        docs_info.append(doc_info)
    
    formatted_context = "\n\n".join(formatted)
    
    print(f"Formatted {SEARCH_K} documents for context, showing top {TOP_DOCS_FOR_UI} in UI")
    
    return {
        "formatted_context": formatted_context,
        "docs_info": docs_info
    }

def detect_currency_node(state: GraphState) -> GraphState:
    """Detect country from context and determine target currency"""
    
    context = state["formatted_context"]
    
    # Detect country from shipping address
    detected_country = detect_country_from_context(context)
    target_currency = get_currency_for_country(detected_country)
    
    print(f"Target currency set to: {target_currency}")
    
    return {
        "detected_country": detected_country,
        "target_currency": target_currency
    }

# OJO
def extract_structured_data_node(state: GraphState) -> GraphState:
    """Extract structured invoice data using Pydantic"""
    
    context = state["formatted_context"]
    question = state["question"].lower()
    
    # Check if asking for multiple invoices
    asking_for_multiple = any(keyword in question for keyword in ['all invoices', 'all invoice', 'multiple invoice', 'list of invoice', 'every invoice'])
    
    try:
        if asking_for_multiple:
            print("User asking for multiple invoices - extracting from all fragments")
            # For now, extract from the main context (which contains all fragments)
            # In the future, you could split by source and extract multiple Invoice objects
            invoice = extract_structured_invoice(context)
        else:
            print("Extracting single invoice")
            invoice = extract_structured_invoice(context)
        
        if invoice:
            print(f"Invoice extracted: {invoice.invoice_id or 'Unknown ID'}")
        else:
            print("Could not extract structured invoice data")
        
        return {
            "structured_invoice": invoice
        }
    except Exception as e:
        print(f"Structured extraction error: {e}")
        return {
            "structured_invoice": None
        }
        
def generate_response_node(state: GraphState) -> GraphState:
    """Generate final response using structured data when available"""
    
    question = state["question"]
    context = state["formatted_context"]
    is_specific = state.get("is_specific_query", False)
    target_currency = state.get("target_currency", "USD")
    structured_invoice = state.get("structured_invoice")
    
    # Check if we have structured data
    print(f"DEBUG: structured_invoice = {structured_invoice is not None}")
    print(f"DEBUG: is_specific = {is_specific}")
    
    # Try to use structured data first
    if structured_invoice:
        print("Using structured invoice data (Pydantic model)")#OJO
        response = format_invoice_response(structured_invoice, question, is_specific)
        
        # Extract conversions from structured data
        conversions = []
        question_lower = question.lower()
        
        # Determine which field was asked about for specific queries
        conv = None
        if is_specific:
            if "balance" in question_lower and "due" in question_lower and structured_invoice.balance_due:
                conv = structured_invoice.balance_due
            elif "subtotal" in question_lower and structured_invoice.subtotal:
                conv = structured_invoice.subtotal
            elif "discount" in question_lower and structured_invoice.discount:
                conv = structured_invoice.discount
            elif "shipping" in question_lower and structured_invoice.shipping:
                conv = structured_invoice.shipping
            elif "total" in question_lower and structured_invoice.total_amount_payable:
                conv = structured_invoice.total_amount_payable
        else:
            # For general queries, show the main financial field (balance_due or total_payable)
            conv = structured_invoice.balance_due if structured_invoice.balance_due else structured_invoice.total_amount_payable
        
        # Add conversion if available (regardless of whether local_currency == USD)
        # We show the conversion panel if there's a local currency defined and it differs from USD
        if conv and conv.converted_amount and conv.local_currency and conv.local_currency != "USD":
            conversions.append({
                "original_amount": f"{conv.original_amount:.2f}",
                "original_currency": conv.original_currency,
                "converted_amount": f"{conv.converted_amount:.2f}",
                "target_currency": conv.local_currency,
                "rate": f"{conv.exchange_rate:.4f}" if conv.exchange_rate else "N/A"
            })
            print(f"dded conversion: {conv.original_amount} USD → {conv.converted_amount} {conv.local_currency}")
        else:
            print(f"No conversion needed (local_currency={conv.local_currency if conv else 'N/A'})")
        
        print(f"Response generated from structured data (Pydantic)")
        print(f"Conversions to show: {len(conversions)}")
        
        return {
            "response": response,
            "currency_conversions": conversions
        }
    
    # Select appropriate prompt template
    if is_specific:
        print("Using SPECIFIC query template")
        selected_template = RAG_TEMPLATE_SPECIFIC
    else:
        print("   Using GENERAL query template")
        selected_template = RAG_TEMPLATE_GENERAL
    
    # Create RAG prompt
    rag_prompt = PromptTemplate.from_template(selected_template)
    
    # Generate response
    rag_chain = rag_prompt | llm_generation | StrOutputParser()
    response = rag_chain.invoke({
        "context": context,
        "question": question
    })
    
    # Extract and convert amounts from response
    conversions = []
    if target_currency != "USD":
        print(f"Extracting amounts from response to convert to {target_currency}...")
        try:
            # STRICT MODE: Only extract amounts with explicit currency symbols ($, USD, etc.)
            # This prevents converting quantities, IDs, or other numbers
            raw_conversions = currency_exchanger.extract_and_convert_amounts(
                response, 
                target_currency,
                strict_mode=True
            )
            
            # Deduplicate conversions by unique amount
            seen_amounts = set()
            for conv in raw_conversions:
                amount_key = f"{conv['original_amount']:.2f}"
                if amount_key not in seen_amounts:
                    seen_amounts.add(amount_key)
                    conversions.append({
                        "original_amount": f"{conv['original_amount']:.2f}",
                        "original_currency": conv["original_currency"],
                        "converted_amount": f"{conv['converted_amount']:.2f}",
                        "target_currency": conv["target_currency"],
                        "rate": f"{conv['rate']:.4f}"
                    })
            
            print(f"Extracted {len(conversions)} unique monetary amounts from response")
        except Exception as e:
            print(f"Currency conversion error: {e}")
    
    print("Response generated (traditional RAG fallback)")
    
    return {
        "response": response,
        "currency_conversions": conversions
    }
    
def create_rag_graph():
    """Create and compile the RAG graph with structured extraction"""
    
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("classify_query", classify_query_node)
    workflow.add_node("generate_queries", generate_queries_node)
    workflow.add_node("retrieve_documents", retrieve_documents_node)
    workflow.add_node("format_context", format_context_node)
    workflow.add_node("detect_currency", detect_currency_node)
    workflow.add_node("extract_structured_data", extract_structured_data_node)
    workflow.add_node("generate_response", generate_response_node)
    
    # Define edges
    workflow.add_edge(START, "classify_query")
    workflow.add_edge("classify_query", "generate_queries")
    workflow.add_edge("generate_queries", "retrieve_documents")
    workflow.add_edge("retrieve_documents", "format_context")
    workflow.add_edge("format_context", "detect_currency")
    workflow.add_edge("detect_currency", "extract_structured_data")
    workflow.add_edge("extract_structured_data", "generate_response")
    workflow.add_edge("generate_response", END)
    
    # Compile graph
    app = workflow.compile()
    
    return app

def query_rag_graph(question: str):
    """
    Execute RAG query using LangGraph with currency conversion
    
    Args:
        question: User's question
        
    Returns:
        tuple: (response, docs_info, currency_conversions)
    """
    try:
        print(f"\n{'='*60}")
        print(f"Starting RAG Graph for question: {question[:50]}...")
        print(f"{'='*60}\n")
        
        # Create graph
        app = create_rag_graph()
        
        # Initial state
        initial_state = {
            "question": question,
            "is_specific_query": False,
            "generated_queries": [],
            "documents": [],
            "formatted_context": "",
            "detected_country": "usa",
            "target_currency": "USD",
            "structured_invoice": None,
            "currency_conversions": [],
            "response": "",
            "docs_info": []
        }
        
        # Execute graph
        final_state = app.invoke(initial_state)
        
        print(f"\n{'='*60}")
        print("RAG Graph completed successfully")
        print(f"{'='*60}\n")
        
        return (
            final_state["response"], 
            final_state["docs_info"],
            final_state["currency_conversions"]
        )
        
    except Exception as e:
        error_msg = f'Could not process the query: {str(e)}'
        print(f"Error: {error_msg}")
        return error_msg, [], []


def get_retriever_info():
    """Get retriever configuration info"""
    return {
        "tipo": f'{SEARCH_TYPE.upper()}',
        "documentos": SEARCH_K,
        "diversidad": MMR_DIVERSITY_LAMBDA,
        "candidatos": MMR_FETCH_K,
        "umbral": None
    }