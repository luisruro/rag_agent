# app/rag_system.py
from typing import TypedDict, List, Dict, Optional
from langgraph.graph import StateGraph, END, START
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
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

CURRENCY_ENABLED = False
currency_exchanger = None

try:
    from currency_exchange import currency_exchanger
    
    if os.getenv("EXCHANGERATE_API_KEY"):
        CURRENCY_ENABLED = True
        print(" Currency exchange enabled with API key")
    else:
        print(" EXCHANGERATE_API_KEY not found. Currency conversion will use free APIs.")
        CURRENCY_ENABLED = True  
except ImportError as e:
    print(f" Currency exchange module not found: {e}")
    
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

def extract_all_usd_amounts(text: str) -> List[Dict]:
    """Extract ALL USD amounts from text with their positions"""
    patterns = [
        # Pattern 1: $1,234.56
        (r'(\$\s*[\d,]+\.?\d*)', 0),
        # Pattern 2: 1,234.56 USD
        (r'([\d,]+\.?\d*\s*USD)', 1),
        # Pattern 3: USD 1,234.56
        (r'(USD\s*[\d,]+\.?\d*)', 0),
        # Pattern 4: total: $1,234.56
        (r'(total|amount|balance|due|cost|price|discount|shipping|subtotal)[\s:]*\$?\s*([\d,]+\.?\d*)', 2),
    ]
    
    matches = []
    for pattern, amount_group in patterns:
        pattern_matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in pattern_matches:
            if amount_group == 0:
                
                amount_text = match.group(0)
            else:
                amount_text = match.group(amount_group)
            
            amount_match = re.search(r'[\d,]+\.?\d*', amount_text)
            if not amount_match:
                continue
            
            try:
                amount_str = amount_match.group().replace(',', '')
                amount = float(amount_str)
                if amount <= 0.01:  
                    continue
                    
                matches.append({
                    "full_match": match.group(0),
                    "amount_text": amount_text,
                    "amount": amount,
                    "start": match.start(),
                    "end": match.end(),
                    "pattern": pattern
                })
            except ValueError:
                continue
    
    matches.sort(key=lambda x: x["start"], reverse=True)
    return matches

def convert_usd_to_currency(amount: float, dest_currency: str) -> Optional[float]:
    """Convert USD amount to destination currency"""
    if dest_currency == "USD":
        return amount
    
    try:
        if CURRENCY_ENABLED and currency_exchanger:
            return currency_exchanger.convert_amount(amount, "USD", dest_currency)
    except:
        pass
    
    fallback_rates = {
        "EUR": 0.95,
        "GBP": 0.80,
        "MXN": 20,
        "JPY": 150,
        "CNY": 7.2,
        "RUB": 90,
        "BRL": 5,
        "CAD": 1.35,
        "AUD": 1.50,
        "INR": 83,
        "KRW": 1300,
        "CHF": 0.90,
        "SEK": 10.5,
        "NOK": 10.5,
        "DKK": 7.0,
        "PLN": 4.0,
        "TRY": 32,
        "ZAR": 18,
        "SGD": 1.35,
        "HKD": 7.8,
        "TWD": 32,
        "THB": 36,
        "IDR": 15600,
        "PHP": 56,
        "MYR": 4.7,
        "VND": 24800,
    }
    
    rate = fallback_rates.get(dest_currency, 1.0)
    return round(amount * rate, 2)

def force_currency_conversion_in_text(text: str, dest_currency: str, shipping_address: str = None) -> str:
    """
    Force currency conversion on ALL USD amounts in text
    Returns: (converted_text, conversions_list)
    """
    if dest_currency == "USD" or not text:
        return text, []
    
    matches = extract_all_usd_amounts(text)
    if not matches:
        return text, []
    
    result = text
    conversions = []
    
    for match in matches:
        amount = match["amount"]
        converted_amount = convert_usd_to_currency(amount, dest_currency)
        
        if converted_amount and converted_amount != amount:
            
            if dest_currency in ["JPY", "KRW", "IDR", "VND", "INR"]:
                
                converted_str = f"{converted_amount:,.0f}"
            else:
                converted_str = f"{converted_amount:,.2f}"
            
            replacement = f"{match['full_match']} (approx. {converted_str} {dest_currency})"
            result = result[:match["start"]] + replacement + result[match["end"]:]
            
            conversions.append({
                "original_amount": f"{amount:.2f}",
                "original_currency": "USD",
                "converted_amount": f"{converted_amount:.2f}",
                "target_currency": dest_currency,
                "original_text": match['full_match']
            })
    
    if conversions and shipping_address:
        result += f"\n\n*Note: Converted from USD to {dest_currency} based on shipping to {shipping_address}*"
    
    return result, conversions

def should_apply_currency_conversion(question: str, response: str) -> bool:
    """Check if currency conversion should be applied"""
    # Check if response contains monetary amounts
    monetary_patterns = [
        r'\$\s*[\d,]+\.?\d*',
        r'[\d,]+\.?\d*\s*USD',
        r'USD\s*[\d,]+\.?\d*',
        r'(?:total|amount|balance|due|cost|price|discount|shipping|subtotal)[\s:]*\$?\s*[\d,]+\.?\d*',
    ]
    
    has_monetary = any(re.search(pattern, response, re.IGNORECASE) for pattern in monetary_patterns)
    
    # Check if question asks for monetary values
    monetary_keywords = [
        'total', 'due', 'amount', 'balance', 'cost', 'price', 
        'discount', 'shipping', 'subtotal', 'money', 'currency',
        'dollar', 'euro', 'peso', 'pound', 'yen', 'convert'
    ]
    question_asks_money = any(keyword in question.lower() for keyword in monetary_keywords)
    
    return has_monetary or question_asks_money

# ===== END OF NEW HELPER FUNCTIONS =====

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
    # Adding currency-specific fields from HEAD
    should_convert_currency: bool
    shipping_address: str
    destination_country: str
    dest_currency: str
    
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

def extract_shipping_address(context):
    """Extract shipping address from context"""
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
            address = match.group(1).strip()
            address = re.sub(r'^\s*(?:Name|Contact|Phone|Email|Date|Invoice).*?:.*?$', '', address, flags=re.MULTILINE | re.IGNORECASE)
            address = ' '.join(address.split('\n')[:3]).strip()
            if address:
                return address
    
    return None

def extract_country_from_address(address):
    """Extract country from shipping address"""
    if not address:
        return None
    
    country_patterns = [
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
    
    for pattern, country in country_patterns:
        if re.search(pattern, address, re.IGNORECASE):
            return country
    
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

def detect_specific_query(question: str) -> bool:
    """Detect if the user is asking for a specific piece of information"""
    question_lower = question.lower()
    
    question_lower = question_lower.replace('ant ', 'and ')
    question_lower = question_lower.replace('inovice', 'invoice')
    
    if any(keyword in question_lower for keyword in ['all invoices', 'all invoice', 'multiple invoice', 'list of invoice', 'every invoice']):
        return False
    
    specific_fields = ['product', 'quantity', 'amount', 'total', 'price', 'cost', 'balance', 'date', 'number', 'invoice', 'due']
    field_count = 0
    for field in specific_fields:
        if field in question_lower:
            field_count += 1
    
    if 1 <= field_count <= 4:
        return True
    
    specific_patterns = [
        r'\bget\s+(?:the|me)?\s*(?:product|quantity|amount|total|due|balance)\b',
        r'\bshow\s+(?:me)?\s*(?:the)?\s*(?:product|quantity|amount|total|due|balance)\b',
        r'\btell\s+(?:me)?\s*(?:the)?\s*(?:product|quantity|amount|total|due|balance)\b',
        r'\bwhat\s+(?:is|are)\s+(?:the)?\s*(?:product|quantity|amount|total|due|balance)\b',
        r'\bjust\b.*\bthe\b',
        r'\bonly\b.*\bthe\b',
        r'\bhow\s+much\b',
        r'\bproduct.*quantity.*total\b',
        r'\bget the.*product.*quantity.*total\b',
        r'\btotal\s+due\b',
        r'\bwhat.*total.*due\b',
        r'\bshow.*total.*due\b',
    ]
    
    for pattern in specific_patterns:
        if re.search(pattern, question_lower):
            return True
    
    return False

def detect_country_from_context(context: str) -> str:
    """Detect country from ship_to address in context"""
    context_lower = context.lower()
    
    shipping_address = extract_shipping_address(context)
    if shipping_address:
        country = extract_country_from_address(shipping_address)
        if country:
            print(f"   Detected country from address: {country}")
            return country.lower()
    
    ship_to_pattern = r'ship\s+to[:\s]+(.*?)(?:\n|$)'
    matches = re.finditer(ship_to_pattern, context_lower, re.MULTILINE | re.IGNORECASE)
    
    for match in matches:
        ship_info = match.group(1).lower()
        for country, currency in COUNTRY_CURRENCY_MAP.items():
            if country in ship_info:
                return country
    
    country_pattern = r'country[:\s]+([\w\s]+?)(?:\n|,|$)'
    country_matches = re.finditer(country_pattern, context_lower, re.MULTILINE | re.IGNORECASE)
    
    for match in country_matches:
        country_text = match.group(1).strip().lower()
        for country, currency in COUNTRY_CURRENCY_MAP.items():
            if country in country_text:
                return country
    
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
    
    multi_query_prompt = PromptTemplate.from_template(MULTI_QUERY_PROMPT)
    
    query_chain = multi_query_prompt | llm_queries | StrOutputParser()
    generated_text = query_chain.invoke({"question": question})
    
    queries = [q.strip() for q in generated_text.split("\n") if q.strip()]
    all_queries = [question] + queries
    
    print(f"Generated {len(all_queries)} queries")
    
    return {
        "generated_queries": all_queries
    }
    
def retrieve_documents_node(state: GraphState) -> GraphState:
    """Retrieve documents for all generated queries using MMR"""
    
    queries = state["generated_queries"]
    all_docs = []
    
    for query in queries:
        docs = base_retriever.invoke(query)
        all_docs.extend(docs)
    
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
    
    shipping_address = extract_shipping_address(formatted_context)
    print(f"DEBUG: Extracted shipping address: '{shipping_address}'")
    
    destination_country = None
    dest_currency = "USD"
    
    if shipping_address and CURRENCY_ENABLED and currency_exchanger:
        destination_country = extract_country_from_address(shipping_address)
        if destination_country:
            try:
                dest_currency = currency_exchanger.get_currency_for_country(destination_country)
                print(f"DEBUG: Destination currency set to: {dest_currency}")
            except:
                dest_currency = currency_exchanger.get_currency_for_address(shipping_address)
        else:
            dest_currency = currency_exchanger.get_currency_for_address(shipping_address)
    
    print(f"Formatted {SEARCH_K} documents for context, showing top {TOP_DOCS_FOR_UI} in UI")
    
    return {
        "formatted_context": formatted_context,
        "docs_info": docs_info,
        "shipping_address": shipping_address,
        "destination_country": destination_country,
        "dest_currency": dest_currency
    }

def detect_currency_node(state: GraphState) -> GraphState:
    """Detect country from context and determine target currency"""
    
    context = state["formatted_context"]
    
    shipping_address = state.get("shipping_address")
    if shipping_address and shipping_address != "Not found":
        country = extract_country_from_address(shipping_address)
        if country:
            detected_country = country.lower()
        else:
            detected_country = detect_country_from_context(context)
    else:
        detected_country = detect_country_from_context(context)
    
    target_currency = get_currency_for_country(detected_country)
    
    print(f"Target currency set to: {target_currency}")
    
    return {
        "detected_country": detected_country,
        "target_currency": target_currency
    }

def extract_structured_data_node(state: GraphState) -> GraphState:
    """Extract structured invoice data using Pydantic"""
    
    context = state["formatted_context"]
    question = state["question"].lower()
    
    asking_for_multiple = any(keyword in question for keyword in ['all invoices', 'all invoice', 'multiple invoice', 'list of invoice', 'every invoice'])
    
    try:
        if asking_for_multiple:
            print("User asking for multiple invoices - extracting from all fragments")
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
    shipping_address = state.get("shipping_address", "Not specified")
    dest_currency = state.get("dest_currency", "USD")
    
    print(f"DEBUG PATH CHECK: is_specific={is_specific}, structured_invoice={structured_invoice is not None}")
    print(f"DEBUG: Shipping address='{shipping_address}'")
    print(f"DEBUG: Destination currency='{dest_currency}'")
    
    if is_specific:
        print("FORCING SPECIFIC QUERY PATH - using specific template only")
        
        selected_template = RAG_TEMPLATE_SPECIFIC
        
        rag_prompt = PromptTemplate.from_template(selected_template)
        
        rag_chain = rag_prompt | llm_generation | StrOutputParser()
        response = rag_chain.invoke({
            "context": context,
            "question": question,
            "shipping_address": shipping_address
        })
        
        response = re.sub(r'^(Answer\s*(?:to\s+the\s+Question)?:\s*)?', '', response, flags=re.IGNORECASE)
        response = response.strip()
        
        print(f"DEBUG Specific response (before conversion): {response[:200]}...")
        
        conversions = []
        
        should_convert = should_apply_currency_conversion(question, response)
        can_convert = (shipping_address and shipping_address != "Not specified" and dest_currency != "USD")
        
        print(f"DEBUG: Should convert? {should_convert}, Can convert? {can_convert}")
        
        if should_convert and can_convert:
            print(f"DEBUG: Applying FORCED currency conversion to {dest_currency}")
            
            if CURRENCY_ENABLED and currency_exchanger:
                try:
                    enhanced_response = currency_exchanger.enhance_answer_with_conversion(
                        response, 
                        shipping_address
                    )
                    
                    if enhanced_response != response:
                        response = enhanced_response
                        print("DEBUG: Currency conversion applied via currency_exchanger")
                    else:
                        print("DEBUG: currency_exchanger didn't work, using forced conversion")
                        response, new_conversions = force_currency_conversion_in_text(
                            response, dest_currency, shipping_address
                        )
                        conversions.extend(new_conversions)
                except Exception as e:
                    print(f"DEBUG: currency_exchanger failed, using forced conversion: {e}")
                    response, new_conversions = force_currency_conversion_in_text(
                        response, dest_currency, shipping_address
                    )
                    conversions.extend(new_conversions)
            else:
                response, new_conversions = force_currency_conversion_in_text(
                    response, dest_currency, shipping_address
                )
                conversions.extend(new_conversions)
            
          
            if CURRENCY_ENABLED and currency_exchanger and dest_currency != "USD":
                try:
                    raw_conversions = currency_exchanger.extract_and_convert_amounts(
                        response,
                        target_currency=dest_currency,
                        strict_mode=False  
                    )
                    
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
                except Exception as e:
                    print(f"DEBUG: Error extracting conversions: {e}")
        
        elif should_convert and not can_convert:
            print("DEBUG: Should convert but can't (no shipping address or USD destination)")
            if not shipping_address or shipping_address == "Not specified":
                response = response + "\n\n**"
            elif dest_currency == "USD":
                response = response + "\n\n*Note: Destination currency is USD - no conversion needed*"
        
        print(f"DEBUG Specific response (after conversion): {response[:200]}...")
        print(f"Response generated (SPECIFIC template path) with {len(conversions)} conversions")
        
        return {
            "response": response,
            "currency_conversions": conversions
        }
  
    print("GENERAL QUERY - using structured data if available")
    
    if structured_invoice:
        print("Using structured invoice data (Pydantic model)")
        response = format_invoice_response(structured_invoice, question, is_specific)
        
        should_convert = should_apply_currency_conversion(question, response)
        can_convert = (shipping_address and shipping_address != "Not specified" and dest_currency != "USD")
        
        if should_convert and can_convert:
            print(f"DEBUG: Applying currency conversion to structured response ({dest_currency})")
            
            if CURRENCY_ENABLED and currency_exchanger:
                try:
                    enhanced_response = currency_exchanger.enhance_answer_with_conversion(
                        response, 
                        shipping_address
                    )
                    if enhanced_response != response:
                        response = enhanced_response
                except Exception as e:
                    print(f"DEBUG: currency_exchanger failed for structured response: {e}")
                    # Try forced conversion
                    response, _ = force_currency_conversion_in_text(response, dest_currency, shipping_address)
            else:
                response, _ = force_currency_conversion_in_text(response, dest_currency, shipping_address)
        
        conversions = []
        conv = structured_invoice.balance_due if structured_invoice.balance_due else structured_invoice.total_amount_payable
        
        if conv and conv.converted_amount and conv.local_currency and conv.local_currency != "USD":
            conversions.append({
                "original_amount": f"{conv.original_amount:.2f}",
                "original_currency": conv.original_currency,
                "converted_amount": f"{conv.converted_amount:.2f}",
                "target_currency": conv.local_currency,
                "rate": f"{conv.exchange_rate:.4f}" if conv.exchange_rate else "N/A"
            })
        
        print(f"Response generated from structured data (Pydantic)")
        print(f"Conversions to show: {len(conversions)}")
        
        return {
            "response": response,
            "currency_conversions": conversions
        }
    
    # Fallback: Use general template if no structured data
    print("No structured data - using GENERAL template")
    selected_template = RAG_TEMPLATE_GENERAL
    
    # Create RAG prompt
    rag_prompt = PromptTemplate.from_template(selected_template)
    
    # Generate response
    rag_chain = rag_prompt | llm_generation | StrOutputParser()
    response = rag_chain.invoke({
        "context": context,
        "question": question,
        "shipping_address": shipping_address
    })
    
    conversions = []
    should_convert = should_apply_currency_conversion(question, response)
    can_convert = (shipping_address and shipping_address != "Not specified" and dest_currency != "USD")
    
    if should_convert and can_convert:
        print(f"DEBUG: Applying currency conversion to general response ({dest_currency})")
        
        if CURRENCY_ENABLED and currency_exchanger:
            try:
                response = currency_exchanger.enhance_answer_with_conversion(
                    response, 
                    shipping_address
                )
                
                if dest_currency != "USD":
                    raw_conversions = currency_exchanger.extract_and_convert_amounts(
                        response,
                        target_currency=dest_currency,
                        strict_mode=False
                    )
                    
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
                
                print(f"Applied currency conversion for {shipping_address}")
            except Exception as e:
                print(f"Currency conversion error: {e}")
                response = response + f"\n\n*Note: Currency conversion failed: {str(e)}*"
        else:
            response, new_conversions = force_currency_conversion_in_text(response, dest_currency, shipping_address)
            conversions.extend(new_conversions)
    
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
            "docs_info": [],
            "should_convert_currency": False,
            "shipping_address": None,
            "destination_country": None,
            "dest_currency": "USD"
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
    info = {
        "tipo": f'{SEARCH_TYPE.upper()}',
        "documentos": SEARCH_K,
        "diversidad": MMR_DIVERSITY_LAMBDA,
        "candidatos": MMR_FETCH_K,
        "umbral": None
    }
    
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