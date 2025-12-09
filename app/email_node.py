#app/email_node.py
import os
import re
from typing import Dict, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

try:
    from currency_exchange import currency_exchanger
    CURRENCY_CONVERSION_AVAILABLE = True
    print(" Currency conversion enabled for emails")
except ImportError:
    CURRENCY_CONVERSION_AVAILABLE = False
    print(" Currency conversion not available for emails")

STRICT_EMAIL_REGEX = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"


def detect_email_request(question: str) -> bool:
    """Check if user wants to generate/send an email."""
    question_lower = question.lower()
    email_keywords = [
        'email', 'send email', 'write email', 'compose email', 'draft email',
        'send an email', 'write an email', 'compose an email', 'draft an email',
        'email about', 'email regarding', 'email concerning', 'email to',
        'mail', 'send mail', 'write mail'
    ]

    has_email_keyword = any(keyword in question_lower for keyword in email_keywords)

    email_patterns = [
        r'^send\s+(?:an?\s+)?email',
        r'^write\s+(?:an?\s+)?email',
        r'^compose\s+(?:an?\s+)?email',
        r'^draft\s+(?:an?\s+)?email',
        r'email\s+to\s+' + STRICT_EMAIL_REGEX,
        r'send\s+to\s+' + STRICT_EMAIL_REGEX
    ]

    has_email_pattern = any(re.search(pattern, question_lower, re.IGNORECASE)
                            for pattern in email_patterns)

    return has_email_keyword or has_email_pattern


def extract_email_info_from_context(context: str) -> Dict:
    """Extract email addresses and recipient names from context."""
    emails = re.findall(STRICT_EMAIL_REGEX, context)

    # Name extraction patterns
    name_patterns = [
        r'Customer[:\s]+([\w\s]+?)(?:\n|$)',
        r'Bill To[:\s]+([\w\s]+?)(?:\n|$)',
        r'Ship To[:\s]+([\w\s]+?)(?:\n|$)',
        r'Invoice To[:\s]+([\w\s]+?)(?:\n|$)',
        r'Contact[:\s]+([\w\s]+?)(?:\n|$)',
    ]

    recipient_name = "Customer"
    for pattern in name_patterns:
        match = re.search(pattern, context, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if name and len(name) < 50:
                recipient_name = name
                break

    return {
        "emails": emails,
        "recipient_name": recipient_name,
        "primary_email": emails[0] if emails else None
    }


def extract_shipping_address_from_context(context: str) -> Optional[str]:
    """Extract shipping address from context for currency conversion"""
    patterns = [
        r'Ship To:\s*(.+?)(?:\n|$)',
        r'Shipping Address:\s*(.+?)(?:\n|$)',
        r'Address:\s*(.+?)(?:\n|$)',
        r'Destination:\s*(.+?)(?:\n|$)',
        r'Deliver To:\s*(.+?)(?:\n|$)',
        r'Shipped to:\s*(.+?)(?:\n|$)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, context, re.IGNORECASE | re.DOTALL)
        if match:
            address = match.group(1).strip()
            address = re.sub(r'^\s*(?:Name|Contact|Phone|Email|Date|Invoice).*?:.*?$', '', 
                           address, flags=re.MULTILINE | re.IGNORECASE)
            address = ' '.join(address.split('\n')[:3]).strip()
            if address:
                return address
    
    return None


def convert_amounts_in_text(text: str, shipping_address: str) -> str:
    """Convert USD amounts in text to destination currency"""
    if not CURRENCY_CONVERSION_AVAILABLE or not shipping_address:
        return text
    
    try:
        # Get destination currency
        dest_currency = currency_exchanger.get_currency_for_address(shipping_address)
        
        if dest_currency == "USD":
            return text  # No conversion needed
        
        # Extract USD amounts and convert
        conversions = currency_exchanger.extract_and_convert_amounts(
            text, 
            target_currency=dest_currency, 
            strict_mode=False
        )
        
        if not conversions:
            return text
        
        # Apply conversions to text
        result = text
        for conv in sorted(conversions, key=lambda x: x.get('original_text', ''), reverse=True):
            original_text = conv.get('original_text', '')
            if original_text and original_text in result:
                converted_amount = conv.get('converted_amount', 0)
                target_currency = conv.get('target_currency', dest_currency)
                
                # Format the converted amount nicely
                if target_currency in ["JPY", "KRW", "IDR", "INR", "VND"]:
                    converted_str = f"{converted_amount:,.0f}"
                else:
                    converted_str = f"{converted_amount:,.2f}"
                
                # Add conversion next to original amount
                replacement = f"{original_text} (approx. {converted_str} {target_currency})"
                result = result.replace(original_text, replacement)
        
        # Add conversion note
        if conversions:
            rate = conversions[0].get('rate', 1.0)
            country = currency_exchanger.extract_country_from_address(shipping_address) or "destination"
            result += f"\n\n*Note: Amounts converted from USD to {dest_currency} for {country}. Exchange rate: 1 USD ≈ {rate:.4f} {dest_currency}*"
        
        return result
        
    except Exception as e:
        print(f"Currency conversion error in email: {e}")
        return text  # Return original text if conversion fails


def generate_email(llm: ChatOpenAI, question: str, context: str, invoice_data: Optional[Dict] = None) -> Dict:
    """Generate professional email based on context."""

    email_info = extract_email_info_from_context(context)

    # Default fallback if none extracted
    recipient_email = email_info["primary_email"] or "colombiastorecommerce@gmail.com"
    recipient_name = email_info["recipient_name"]

    # Check if question itself contains an email
    question_emails = re.findall(STRICT_EMAIL_REGEX, question)
    if question_emails:
        recipient_email = question_emails[0]

    # SAFETY — Fully validate final recipient email
    if not re.match(rf"^{STRICT_EMAIL_REGEX}$", recipient_email):
        recipient_email = "colombiastorecommerce@gmail.com"

    # Extract shipping address for currency conversion
    shipping_address = extract_shipping_address_from_context(context)
    
    # Prepare invoice details block
    invoice_details = ""
    if invoice_data:
        invoice_details = f"""
Invoice Details:
- Invoice Number: {invoice_data.get('invoice_id', 'Not specified')}
- Invoice Date: {invoice_data.get('invoice_date', 'Not specified')}
- Total Amount: {invoice_data.get('total_amount', 'Not specified')}
- Due Date: {invoice_data.get('due_date', 'Not specified')}
- Status: {invoice_data.get('payment_status', 'Not specified')}
"""
    
    # Determine email type
    question_lower = question.lower()
    if "follow" in question_lower or "remind" in question_lower:
        email_type = "follow_up"
        base_subject = "Follow-up on Invoice"
    elif "summary" in question_lower or "report" in question_lower:
        email_type = "summary"
        base_subject = "Invoice Summary Report"
    elif "payment" in question_lower or "due" in question_lower:
        email_type = "payment"
        base_subject = "Payment Request"
    else:
        email_type = "general"
        base_subject = "Invoice Information"

    if invoice_data and invoice_data.get('invoice_id'):
        base_subject = f"{base_subject} #{invoice_data['invoice_id']}"

    # Create email prompt WITH currency conversion instructions
    email_system_prompt = """You are a professional email writer for invoice management.

Available invoice context:
{context}

Invoice details:
{invoice_details}

IMPORTANT: When mentioning monetary amounts, ALWAYS include both the original USD amount AND the converted local currency amount.
Example: "Total Amount: $1,071.25 USD (approximately ₹89,500 INR)"

Write a professional email with the following requirements:
1. Start with "Subject: [Your subject here]"
2. Use proper salutation (e.g., "Dear client,")
3. Clear, concise body with relevant invoice information
4. Professional closing
5. NO markdown
6. Under 200 words
7. Polite, formal
8. Include ALL relevant invoice details from context
9. For monetary amounts: Show USD amount first, then converted amount in parentheses

Format EXACTLY like this:

Subject: [Your subject]

Dear [Recipient],

[Email body]

Best regards,
Invoice Management Team
"""
    
    email_prompt = ChatPromptTemplate.from_messages([
        ("system", email_system_prompt),
        ("human", "Write an email about: {question}")
    ])

    chain = email_prompt | llm

    email_content = chain.invoke({
        "question": question,
        "context": context[:1500],
        "invoice_details": invoice_details,
    }).content

    # Apply currency conversion to the generated email
    if shipping_address and CURRENCY_CONVERSION_AVAILABLE:
        print(f"Applying currency conversion for shipping to: {shipping_address}")
        email_content = convert_amounts_in_text(email_content, shipping_address)

    # Ensure subject exists
    if not email_content.strip().startswith("Subject:"):
        email_content = f"Subject: {base_subject}\n\n{email_content}"

    # Extract subject line
    subject = base_subject
    for line in email_content.split("\n"):
        if line.lower().startswith("subject:"):
            subject = line[8:].strip()
            break

    return {
        "recipient_email": recipient_email,
        "recipient_name": recipient_name,
        "subject": subject,
        "email_content": email_content,
        "email_type": email_type,
        "shipping_address": shipping_address
    }


def email_generation_node(state: Dict) -> Dict:
    """
    Email generation node for LangGraph - FIXED VERSION with currency conversion
    """
    from langchain_openai import ChatOpenAI
    
    question = state.get("question", "")
    context = state.get("formatted_context", "")
    structured_invoice = state.get("structured_invoice")

    print(f"Email generation activated for: {question[:50]}...")

    # Create LLM instance
    llm = ChatOpenAI(model="gpt-4o", temperature=0)  # Use GPT-4o for email generation

    # Prepare structured invoice data SAFELY
    invoice_data = None
    if structured_invoice:
        # SAFELY get invoice_id with fallback
        invoice_id = getattr(structured_invoice, 'invoice_id', None)
        if not invoice_id:
            invoice_id = getattr(structured_invoice, 'id', None)
        invoice_id = invoice_id or "Not specified"
        
        # SAFELY get invoice_date - try multiple attribute names
        invoice_date = getattr(structured_invoice, 'invoice_date', None)
        if not invoice_date:
            invoice_date = getattr(structured_invoice, 'order_date', None)
        if not invoice_date:
            invoice_date = getattr(structured_invoice, 'date', None)
        invoice_date = invoice_date or "Not specified"
        
        # SAFELY get total_amount
        total_amount = "Not specified"
        if hasattr(structured_invoice, 'total_amount_payable') and structured_invoice.total_amount_payable:
            if hasattr(structured_invoice.total_amount_payable, 'original_amount'):
                amount = structured_invoice.total_amount_payable.original_amount
                currency = getattr(structured_invoice.total_amount_payable, 'original_currency', 'USD')
                total_amount = f"{amount:.2f} {currency}"
            else:
                try:
                    total_amount = f"{structured_invoice.total_amount_payable:.2f} USD"
                except:
                    pass
        elif hasattr(structured_invoice, 'total_amount'):
            try:
                total_amount = f"{structured_invoice.total_amount:.2f} USD"
            except:
                pass
        elif hasattr(structured_invoice, 'amount'):
            try:
                total_amount = f"{structured_invoice.amount:.2f} USD"
            except:
                pass
        
        # SAFELY get due_date
        due_date = getattr(structured_invoice, 'due_date', 'Not specified')
        
        # SAFELY get payment_status
        payment_status = getattr(structured_invoice, 'payment_status', 'Not specified')
        
        invoice_data = {
            "invoice_id": invoice_id,
            "invoice_date": invoice_date,
            "total_amount": total_amount,
            "due_date": due_date,
            "payment_status": payment_status
        }

    email_result = generate_email(llm, question, context, invoice_data)

    full_response = f"""📧 Email Prepared:

**To:** {email_result['recipient_name']} ({email_result['recipient_email']})
**Subject:** {email_result['subject']}

{email_result['email_content']}

*Would you like to send this email? (Reply with 'yes' to send or 'no' to discard)*"""

    return {
        **state,
        "response": full_response,
        "email_draft": email_result['email_content'],
        "email_recipient": email_result['recipient_email'],
        "email_subject": email_result['subject'],
        "email_body": email_result['email_content'],
        "shipping_address": email_result.get('shipping_address')
    }