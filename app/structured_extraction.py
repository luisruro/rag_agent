from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from typing import Optional
import json
import re
from invoice_model import Invoice, ShipTo, CurrencyConversion
from currency_exchange import currency_exchanger
from config import GENERATION_MODEL

# LLM for structured extraction
llm_structured = ChatOpenAI(model=GENERATION_MODEL, temperature=0)

EXTRACTION_PROMPT = """You are an expert at extracting structured information from invoice documents.

Extract ALL available information from the following invoice document and return it as a JSON object.

IMPORTANT INSTRUCTIONS:
- Extract ALL fields that are present in the document
- For fields not found, use null
- Be precise with numbers (do not round unnecessarily)
- Extract dates in YYYY-MM-DD format
- For ship_to address, extract all available fields (postal_code, city, state, country)
- Extract ALL items with complete details
- Do NOT perform any currency conversions (they will be done separately)
- Carefully distinguish between subtotal, discount, shipping, balance_due, and total_amount_payable
- Return ONLY valid JSON, no markdown, no explanations, no preamble

INVOICE DOCUMENT:
{context}

Return the extracted data as JSON following this EXACT structure:
{{
    "invoice_id": "string or null",
    "order_id": "string or null",
    "order_date": "YYYY-MM-DD or null",
    "ship_mode": "string or null",
    "bill_to": "customer name or null",
    "ship_to": {{
        "postal_code": "string or null",
        "city": "string or null",
        "state": "string or null",
        "country": "string or null"
    }},
    "items": [
        {{
            "product_name": "string or null",
            "subcategory": "string or null",
            "category": "string or null",
            "product_id": "string or null",
            "quantity": number or null,
            "unit_cost": number or null,
            "subtotal": number or null,
            "discount_percent": number or null,
            "shipping_fee": number or null,
            "total_amount_payable": number or null
        }}
    ],
    "notes": "string or null",
    "subtotal_amount": number or null,
    "discount_amount": number or null,
    "shipping_amount": number or null,
    "balance_due_amount": number or null,
    "total_amount_payable": number or null
}}

CRITICAL: Return ONLY the JSON object, nothing else. No markdown formatting, no code blocks, no explanations.

JSON OUTPUT:
"""

def extract_structured_invoice(context: str) -> Optional[Invoice]:
    """
    Extract structured invoice data from document context using LLM
    
    Args:
        context: Document text containing invoice information
        
    Returns:
        Invoice model with extracted and validated data, or None if extraction fails
    """
    try:
        print("📊 Extracting structured data with Pydantic...")
        
        # Create prompt
        prompt = ChatPromptTemplate.from_template(EXTRACTION_PROMPT)
        
        # Extract data using LLM
        chain = prompt | llm_structured
        response = chain.invoke({"context": context})
        
        # Parse JSON response
        json_text = response.content.strip()
        
        # Remove markdown code blocks if present
        if json_text.startswith("```json"):
            json_text = json_text.replace("```json", "").replace("```", "").strip()
        elif json_text.startswith("```"):
            json_text = json_text.replace("```", "").strip()
        
        extracted_data = json.loads(json_text)
        
        # Build Invoice model with currency conversions
        invoice_dict = {
            "invoice_id": extracted_data.get("invoice_id"),
            "order_id": extracted_data.get("order_id"),
            "order_date": extracted_data.get("order_date"),
            "ship_mode": extracted_data.get("ship_mode"),
            "bill_to": extracted_data.get("bill_to"),
            "ship_to": None,
            "items": [],
            "notes": extracted_data.get("notes"),
            "currency": "USD",
            "local_currency": None
        }
        
        # Parse ship_to
        if extracted_data.get("ship_to"):
            ship_to_data = extracted_data["ship_to"]
            invoice_dict["ship_to"] = ShipTo(
                postal_code=ship_to_data.get("postal_code"),
                city=ship_to_data.get("city"),
                state=ship_to_data.get("state"),
                country=ship_to_data.get("country")
            )
            
            # Determine local currency from country
            if ship_to_data.get("country"):
                country = ship_to_data["country"].lower()
                country_map = {
                    "mexico": "MXN",
                    "méxico": "MXN",
                    "canada": "CAD",
                    "united kingdom": "GBP",
                    "uk": "GBP",
                    "colombia": "COP",
                    "usa": "USD",
                    "united states": "USD"
                }
                invoice_dict["local_currency"] = country_map.get(country, "USD")
        
        # Parse items
        if extracted_data.get("items"):
            for item_data in extracted_data["items"]:
                invoice_dict["items"].append({
                    "product_name": item_data.get("product_name"),
                    "subcategory": item_data.get("subcategory"),
                    "category": item_data.get("category"),
                    "product_id": item_data.get("product_id"),
                    "quantity": item_data.get("quantity"),
                    "unit_cost": item_data.get("unit_cost"),
                    "subtotal": item_data.get("subtotal"),
                    "discount_percent": item_data.get("discount_percent"),
                    "shipping_fee": item_data.get("shipping_fee"),
                    "total_amount_payable": item_data.get("total_amount_payable")
                })
        
        # Helper function to create CurrencyConversion
        def create_currency_conversion(amount: Optional[float], local_currency: Optional[str]) -> Optional[CurrencyConversion]:
            if amount is None:
                return None
            
            conversion_data = {
                "original_amount": amount,
                "original_currency": "USD",
                "converted_amount": None,
                "local_currency": local_currency,
                "exchange_rate": None
            }
            
            # Perform conversion if local currency is different
            if local_currency and local_currency != "USD":
                try:
                    converted = currency_exchanger.convert_amount(amount, "USD", local_currency)
                    rate = currency_exchanger.get_exchange_rate("USD", local_currency)
                    conversion_data["converted_amount"] = converted
                    conversion_data["exchange_rate"] = rate
                except Exception as e:
                    print(f"   Warning: Could not convert {amount} USD to {local_currency}: {e}")
            
            return CurrencyConversion(**conversion_data)
        
        # Add financial fields with conversions
        local_curr = invoice_dict["local_currency"]
        
        invoice_dict["subtotal"] = create_currency_conversion(
            extracted_data.get("subtotal_amount"), local_curr
        )
        invoice_dict["discount"] = create_currency_conversion(
            extracted_data.get("discount_amount"), local_curr
        )
        invoice_dict["shipping"] = create_currency_conversion(
            extracted_data.get("shipping_amount"), local_curr
        )
        invoice_dict["balance_due"] = create_currency_conversion(
            extracted_data.get("balance_due_amount"), local_curr
        )
        invoice_dict["total_amount_payable"] = create_currency_conversion(
            extracted_data.get("total_amount_payable"), local_curr
        )
        
        # Create and validate Invoice model
        invoice = Invoice(**invoice_dict)
        
        print(f"✅ Structured data extracted successfully")
        print(f"   Invoice ID: {invoice.invoice_id}")
        print(f"   Customer: {invoice.bill_to}")
        print(f"   Country: {invoice.ship_to.country if invoice.ship_to else 'N/A'}")
        print(f"   Local Currency: {invoice.local_currency}")
        print(f"   Items count: {len(invoice.items) if invoice.items else 0}")
        print(f"   Balance Due: ${invoice.balance_due.original_amount if invoice.balance_due else 'N/A'}")
        print(f"   Total Payable: ${invoice.total_amount_payable.original_amount if invoice.total_amount_payable else 'N/A'}")
        
        return invoice
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"   Response was: {json_text[:200]}...")
        return None
    except Exception as e:
        print(f"❌ Structured extraction error: {e}")
        return None


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


def format_invoice_response(invoice: Invoice, question: str, is_specific: bool) -> str:
    """
    Format invoice data into a response based on query type
    
    Args:
        invoice: Structured invoice data
        question: User's question
        is_specific: Whether this is a specific query
        
    Returns:
        Formatted response string
    """
    if not invoice:
        return "Unable to extract structured invoice information."
    
    question_lower = question.lower()
    
    # For specific queries, return only what was asked
    if is_specific:
        # Balance due
        if "balance" in question_lower and "due" in question_lower:
            if invoice.balance_due:
                response = f"${invoice.balance_due.original_amount:.2f} USD"
                if invoice.balance_due.converted_amount:
                    response += f" ({invoice.balance_due.converted_amount:.2f} {invoice.balance_due.local_currency})"
                if "customer" in question_lower or "name" in question_lower:
                    response += f", customer: {invoice.bill_to}"
                return response
        
        # Subtotal
        elif "subtotal" in question_lower:
            if invoice.subtotal:
                response = f"${invoice.subtotal.original_amount:.2f} USD"
                if invoice.subtotal.converted_amount:
                    response += f" ({invoice.subtotal.converted_amount:.2f} {invoice.subtotal.local_currency})"
                return response
        
        # Discount
        elif "discount" in question_lower:
            if invoice.discount:
                response = f"${invoice.discount.original_amount:.2f} USD"
                if invoice.discount.converted_amount:
                    response += f" ({invoice.discount.converted_amount:.2f} {invoice.discount.local_currency})"
                return response
        
        # Shipping
        elif "shipping" in question_lower:
            if invoice.shipping:
                response = f"${invoice.shipping.original_amount:.2f} USD"
                if invoice.shipping.converted_amount:
                    response += f" ({invoice.shipping.converted_amount:.2f} {invoice.shipping.local_currency})"
                return response
        
        # Customer name
        elif "customer" in question_lower or ("bill" in question_lower and "to" in question_lower):
            return invoice.bill_to or "Customer name not found"
        
        # Invoice number/ID
        elif "invoice" in question_lower and ("number" in question_lower or "id" in question_lower):
            return invoice.invoice_id or "Invoice ID not found"
    
    # For general queries, return structured full response
    response_parts = []
    
    # Header
    response_parts.append("**📄 Invoice Information**\n")
    
    # Basic info
    if invoice.invoice_id:
        response_parts.append(f"**Invoice ID:** {invoice.invoice_id}")
    if invoice.order_id:
        response_parts.append(f"**Order ID:** {invoice.order_id}")
    if invoice.order_date:
        response_parts.append(f"**Order Date:** {invoice.order_date}")
    if invoice.ship_mode:
        response_parts.append(f"**Ship Mode:** {invoice.ship_mode}")
    
    # Customer info
    if invoice.bill_to:
        response_parts.append(f"\n**👤 Customer:** {invoice.bill_to}")
    
    # Shipping info
    if invoice.ship_to:
        ship_parts = []
        if invoice.ship_to.city:
            ship_parts.append(invoice.ship_to.city)
        if invoice.ship_to.state:
            ship_parts.append(invoice.ship_to.state)
        if invoice.ship_to.country:
            ship_parts.append(invoice.ship_to.country)
        if invoice.ship_to.postal_code:
            ship_parts.append(f"({invoice.ship_to.postal_code})")
        
        if ship_parts:
            response_parts.append(f"**📍 Ship To:** {', '.join(ship_parts)}")
    
    # Items section
    if invoice.items and len(invoice.items) > 0:
        response_parts.append("\n**🛒 Items Ordered:**")
        for idx, item in enumerate(invoice.items, 1):
            item_line = f"{idx}. "
            if item.product_name:
                item_line += f"**{item.product_name}**"
            if item.quantity:
                item_line += f" (Qty: {item.quantity})"
            if item.unit_cost:
                item_line += f" @ ${item.unit_cost:.2f} each"
            if item.category:
                item_line += f" - Category: {item.category}"
            response_parts.append(f"   {item_line}")
            
            # Item financial details
            if item.subtotal:
                response_parts.append(f"   - Subtotal: ${item.subtotal:.2f}")
            if item.discount_percent:
                response_parts.append(f"   - Discount: {item.discount_percent}%")
            if item.shipping_fee:
                response_parts.append(f"   - Shipping: ${item.shipping_fee:.2f}")
            if item.total_amount_payable:
                response_parts.append(f"   - Item Total: ${item.total_amount_payable:.2f}")
    
    # Financial summary
    response_parts.append("\n**💰 Financial Summary:**")
    
    if invoice.subtotal:
        line = f"- **Subtotal:** ${invoice.subtotal.original_amount:.2f} USD"
        if invoice.subtotal.converted_amount:
            line += f" ({invoice.subtotal.converted_amount:.2f} {invoice.subtotal.local_currency})"
        response_parts.append(line)
    
    if invoice.discount:
        line = f"- **Discount:** ${invoice.discount.original_amount:.2f} USD"
        if invoice.discount.converted_amount:
            line += f" ({invoice.discount.converted_amount:.2f} {invoice.discount.local_currency})"
        response_parts.append(line)
    
    if invoice.shipping:
        line = f"- **Shipping:** ${invoice.shipping.original_amount:.2f} USD"
        if invoice.shipping.converted_amount:
            line += f" ({invoice.shipping.converted_amount:.2f} {invoice.shipping.local_currency})"
        response_parts.append(line)
    
    if invoice.total_amount_payable:
        line = f"- **Total Amount Payable:** ${invoice.total_amount_payable.original_amount:.2f} USD"
        if invoice.total_amount_payable.converted_amount:
            line += f" ({invoice.total_amount_payable.converted_amount:.2f} {invoice.total_amount_payable.local_currency})"
        response_parts.append(line)
    
    if invoice.balance_due:
        line = f"- **Balance Due:** ${invoice.balance_due.original_amount:.2f} USD"
        if invoice.balance_due.converted_amount:
            line += f" ({invoice.balance_due.converted_amount:.2f} {invoice.balance_due.local_currency})"
        response_parts.append(line)
    
    # Notes
    if invoice.notes:
        response_parts.append(f"\n**📝 Notes:** {invoice.notes}")
    
    return "\n".join(response_parts)