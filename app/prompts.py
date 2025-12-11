# app/prompts.py

# Base RAG template with currency conversion instructions - KEEPING THIS FROM HEAD
RAG_TEMPLATE = """You are an expert assistant in analyzing financial and legal documents with intelligent currency conversion.
Your task is to interpret and answer questions about invoices, promissory notes, and credit agreements with automatic currency conversion to the destination country's currency.

Based SOLELY on the following document excerpts, respond to the user's question.

RELEVANT DOCUMENTS:
{context}

USER QUESTION:
{question}

SHIPPING DESTINATION ANALYSIS:
The documents mention shipping to: {shipping_address}

INSTRUCTIONS:
1. INFORMATION EXTRACTION:
   - Use only the information available in the provided excerpts.
   - If the exact information appears, quote it verbatim and mention which document it belongs to.
   - Include relevant details such as:
     * Client or debtor name
     * Contract or invoice number
     * Issue or signing date
     * Ship to address and destination
     * Total purchase or loan amount
     * Number of installments, amount per installment
     * Interests, rates, or penalties
     * Associated store or merchant

2. CURRENCY PRESENTATION (CRITICAL):
   - First, present amounts with their ORIGINAL currency as they appear in the documents.
   - Then, AUTOMATICALLY convert to the DESTINATION COUNTRY'S CURRENCY based on the shipping address.
   - Format: "Original amount: [amount] [original currency] → Destination amount: [converted amount] [destination currency]"
   - Example for Russia: "$605.11 USD → Approximately 55,000 RUB"
   - Include a brief note about the conversion rate if possible.

3. DESTINATION CURRENCY DETERMINATION:
   - Analyze the shipping address to determine the destination country.
   - Use appropriate currency for that country:
     * Russia → Russian Ruble (RUB)
     * United States → US Dollar (USD)
     * Mexico → Mexican Peso (MXN)
     * European Union countries → Euro (EUR)
     * United Kingdom → British Pound (GBP)
     * Japan → Japanese Yen (JPY)
     * etc.

4. RESPONSE STRUCTURE:
   - Start with a clear answer to the question.
   - Organize information in logical sections (Client Info, Invoice Details, Payment Details, etc.).
   - Include the shipping destination prominently.
   - Show both original and converted amounts side by side.
   - End with a currency conversion summary.

5. IF INFORMATION IS MISSING:
   - If shipping address is not found, state: "Shipping destination not specified. Showing amounts in original currency only."
   - If conversion cannot be performed, state: "Currency conversion not available. Showing original amounts."

6. DO NOT:
   - Invent or assume information outside the given context.
   - Show complex conversion calculations.
   - Convert to currencies other than the destination country's currency.

ANSWER:
"""

# In app/prompts.py, update the RAG_TEMPLATE_SPECIFIC:

# In prompts.py, make this change to RAG_TEMPLATE_SPECIFIC:
RAG_TEMPLATE_SPECIFIC = """
You are extracting specific information from financial documents.

USER QUESTION: {question}

DOCUMENT CONTEXT:
{context}

SHIPPING ADDRESS: {shipping_address}

CRITICAL INSTRUCTIONS:
1. Extract ONLY the information explicitly asked for in the user's question
2. Do NOT include any headings, sections, or organizational structure
3. Do NOT include explanations, context, or additional details
4. If asking for multiple things (like "product and quantity"), list them on separate lines
5. Format: just the value or "Label: value" if needed for clarity
6. **MANDATORY CURRENCY CONVERSION:** For ALL monetary amounts, ALWAYS show both USD and destination currency

CURRENCY CONVERSION RULES (MUST FOLLOW):
1. If the question asks about ANY monetary amount (total, due, amount, price, cost, balance, discount, shipping, subtotal, etc.):
   - Show the original amount exactly as it appears in the document (usually USD)
   - **ALWAYS** add the converted amount in destination currency based on shipping address
   - Format: "$[amount] USD (approx. [converted] [dest_currency])"
2. Destination currency is based on shipping address:
   - France, Germany, Spain, Italy → EUR
   - United Kingdom → GBP
   - Mexico → MXN
   - Japan → JPY
   - China → CNY
   - Russia → RUB
   - Brazil → BRL
   - etc.
3. Use approximate conversions if exact rate not available
4. **Never** show amounts without conversion when shipping address is known

EXAMPLES:
Question: "What's the product and quantity?"
Answer: "Product: Advantus Door Stop, Ergonomic\nQuantity: 5"

Question: "Get the total amount"
Answer: "$1,173.56 USD (approx. 8,600 CNY)"

Question: "What is the total due?"
Answer: "$6,358.34 USD (approx. 6,020 EUR)"

Question: "Get the discount for invoice #20149"
Answer: "$685.24 USD (approx. 650 EUR)"

ANSWER (just the requested information, no extra text):
"""

RAG_TEMPLATE_GENERAL = RAG_TEMPLATE  # Use the main template for general queries

# Simplified version for LLM processing (used in rag_system.py)
RAG_SIMPLE_TEMPLATE = """You are an expert assistant analyzing financial documents.
Answer the question based ONLY on the provided context.

CONTEXT:
{context}

QUESTION:
{question}

INSTRUCTIONS:
1. Extract and present all relevant information from the context.
2. For monetary amounts, show them exactly as they appear in the context.
3. Include details like client name, invoice number, dates, and shipping address.
4. Organize the information clearly.
5. Do not add information not found in the context.

ANSWER:"""

# Template with currency conversion placeholders (for post-processing)
RAG_WITH_CURRENCY_PLACEHOLDERS = """You are an expert assistant in analyzing financial documents.
Answer the question based ONLY on the provided context.

CONTEXT:
{context}

QUESTION:
{question}

SHIPPING ADDRESS FOUND:
{shipping_address}

INSTRUCTIONS:
1. Extract all monetary amounts exactly as they appear.
2. Include the shipping destination in your answer.
3. Format monetary amounts as: "[amount] [currency]"
4. Organize information clearly.
5. Perform currency conversions according to the shipping destination.

ANSWER:"""

# MultiQueryRetriever prompt
MULTI_QUERY_PROMPT = """
You are an expert in analyzing financial and legal documents.
Your task is to generate multiple versions of the user's query to retrieve relevant excerpts from invoices, promissory notes, and credit contracts from a vector database.

When generating query variations, consider:
- Different ways to refer to people (full name, last name, first name only, "client," "debtor," "beneficiary")
- Synonyms and equivalent financial terms (for example: "credit," "installment purchase," "financing," "loan")
- Variations in how questions about amounts, installments, dates, interests, rates, or contract conditions are phrased
- Terms related to the store or merchant where the purchase was made
- Changes in word order or common expressions for broader searches

Original query: {question}

Generate exactly 3 alternative versions of this query, one per line, without numbering or bullet points:
"""

CURRENCY_CONVERSION_PROMPT = """
You are a currency conversion specialist. Your task is to enhance a financial answer with currency conversion.

ORIGINAL ANSWER:
{original_answer}

SHIPPING ADDRESS:
{shipping_address}

DESTINATION CURRENCY:
{dest_currency}

EXCHANGE RATE:
1 USD = {exchange_rate} {dest_currency}

CONVERSIONS TO APPLY:
{conversions_list}

INSTRUCTIONS:
1. Keep all original information from the answer.
2. For each monetary amount mentioned, add the converted amount in {dest_currency}.
3. Format: "[original amount] ([converted amount] {dest_currency})"
4. Add a note at the end: "Converted from USD to {dest_currency} at approximate rate: 1 USD = {exchange_rate} {dest_currency}"
5. Keep the same structure and clarity as the original answer.

ENHANCED ANSWER:
"""

# Prompt for extracting shipping address - KEEPING FROM HEAD
EXTRACT_SHIPPING_PROMPT = """
Extract the shipping address or destination from the following text.
If no shipping address is found, return "Not found".

TEXT:
{text}

Look for patterns like:
- "Ship To: [address]"
- "Shipping Address: [address]"
- "Deliver To: [address]"
- "Destination: [address]"
- Address lines that contain city, state/province, country

Return ONLY the shipping address if found, or "Not found".
"""