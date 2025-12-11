# app/rag_guardrails.py
import re

def validate_rag_response(response: str, query_type: str = "general") -> dict:
    """Validate RAG response based on query type"""
    
    checks = []
    issues = []
    
    # 1. Check for empty response
    if not response or len(response.strip()) < 10:
        return {
            "valid": False,
            "text": response,
            "issues": ["Empty or too short response"],
            "fixed": False
        }
    
    # 2. Check for basic invoice structure based on query type
    if query_type in ["general", "listing", "financial"]:
       
        has_structure = any(marker in response for marker in ['##', '###', '- ', '• ', '1.', '2.', 'Invoice #'])
        
        if not has_structure:
            issues.append("Response lacks structure for query type")
            checks.append({"check": "has_structure", "passed": False})
        else:
            checks.append({"check": "has_structure", "passed": True})
    
    # 3. Check currency format consistency
    currency_patterns = [
        (r'\$[\d,]+\.?\d*\s*USD', "correct_format"),
        (r'[\d,]+\.?\d*\s*USD\b', "missing_dollar"),
        (r'USD\s*[\d,]+\.?\d*', "wrong_order"),
        (r'\$\d+(?:,\d{3})*(?:\.\d{2})?\s*(?!USD)', "missing_usd"),
    ]
    
    currency_issues = []
    for pattern, issue_type in currency_patterns:
        matches = re.findall(pattern, response, re.IGNORECASE)
        if matches:
            if issue_type == "missing_dollar":
                currency_issues.append(f"USD amount missing $: {matches[0]}")
            elif issue_type == "wrong_order":
                currency_issues.append(f"USD in wrong position: {matches[0]}")
            elif issue_type == "missing_usd":
                currency_issues.append(f"Missing USD suffix: {matches[0]}")
    
    if currency_issues:
        issues.extend(currency_issues)
        checks.append({"check": "currency_format", "passed": False})
    else:
        checks.append({"check": "currency_format", "passed": True})
    
    # 4. Check for bare amounts without context (just numbers)
    bare_amounts = re.findall(r'^\s*[\d,]+\.?\d*\s*(?:USD|EUR|GBP|MXN|RUB|CNY|INR|JPY)', response, re.MULTILINE | re.IGNORECASE)
    if bare_amounts and len(bare_amounts) > 3:  
        issues.append(f"Found {len(bare_amounts)} bare currency amounts without context")
        checks.append({"check": "no_bare_amounts", "passed": False})
    else:
        checks.append({"check": "no_bare_amounts", "passed": True})
    
    # 5. Validate invoice listings have proper metadata
    if "invoice" in response.lower() and len(response) > 200:
       
        has_invoice_numbers = bool(re.search(r'Invoice\s*#?\s*\w+', response, re.IGNORECASE))
        has_customers = bool(re.search(r'(?:Customer|Client)[:\s]+\w+', response, re.IGNORECASE)) or \
                       bool(re.search(r'Bill To[:\s]+\w+', response, re.IGNORECASE))
        has_dates = bool(re.search(r'\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\w+ \d{1,2}, \d{4}', response))
        
        if not has_invoice_numbers and "invoice" in query_type.lower():
            issues.append("Invoice listing missing invoice numbers")
            checks.append({"check": "has_invoice_numbers", "passed": False})
        else:
            checks.append({"check": "has_invoice_numbers", "passed": has_invoice_numbers})
            
        if not has_customers and "invoice" in query_type.lower():
            issues.append("Invoice listing missing customer names")
            checks.append({"check": "has_customers", "passed": False})
        else:
            checks.append({"check": "has_customers", "passed": has_customers})
    
    # 6. Check conversion consistency
    usd_amounts = re.findall(r'\$([\d,]+\.?\d*)\s*USD', response, re.IGNORECASE)
    conversions = re.findall(r'\(approx\.\s*[\d,]+\s*\w+\)', response, re.IGNORECASE)
    
    if usd_amounts and conversions:
        if len(usd_amounts) > len(conversions) * 1.5: 
            issues.append(f"{len(usd_amounts)} USD amounts but only {len(conversions)} conversions")
            checks.append({"check": "conversion_coverage", "passed": False})
        else:
            checks.append({"check": "conversion_coverage", "passed": True})
    
    # 7. Check number formatting (commas for thousands)
    bad_numbers = re.findall(r'\$\d{4,}(?!,)', response) 
    if bad_numbers:
        issues.append(f"Large numbers missing commas: {bad_numbers[:3]}")
        checks.append({"check": "number_formatting", "passed": False})
    else:
        checks.append({"check": "number_formatting", "passed": True})
    
    all_passed = all(c["passed"] for c in checks if "passed" in c)
    
    return {
        "valid": all_passed,
        "text": response,
        "checks": checks,
        "issues": issues,
        "fixed": False
    }

def fix_currency_format(text: str) -> str:
    """Fix common currency format issues"""
    
    fixed = re.sub(r'([^$])(\d[\d,]*\.?\d*)\s+USD\b', r'\1$\2 USD', text, flags=re.IGNORECASE)
    
    fixed = re.sub(r'USD\s+(\$?[\d,]+\.?\d*)', r'$\1 USD', fixed, flags=re.IGNORECASE)
    
    fixed = re.sub(r'(\$[\d,]+\.?\d*)(?:\s|$)(?!USD|\d)', r'\1 USD ', fixed)
  
    lines = fixed.split('\n')
    fixed_lines = []
    for line in lines:
        line = line.strip()
        
        if re.match(r'^[\d,]+\.?\d*\s+USD\b', line, re.IGNORECASE):
            line = '$' + line
        fixed_lines.append(line)
    fixed = '\n'.join(fixed_lines)
    
    def add_commas(match):
        num = match.group(1).replace(',', '')
        if len(num) > 3:
           
            parts = []
            while num:
                parts.append(num[-3:])
                num = num[:-3]
            num = ','.join(reversed(parts))
        return f'${num}'
    
    fixed = re.sub(r'\$(\d{4,})', add_commas, fixed)
    
    fixed = re.sub(r'→\s*Destination\s+Amount:\s*Approximately', '(approx.', fixed, flags=re.IGNORECASE)
    fixed = re.sub(r'→\s*Approximately', '(approx.', fixed, flags=re.IGNORECASE)
    
    return fixed

def fix_response_structure(response: str, query_type: str) -> str:
    """Fix response structure issues"""
    
    if query_type == "listing" and "invoice" in response.lower():
        # Try to structure raw amounts
        lines = response.strip().split('\n')
        structured = []
        
        current_invoice = 1
        for line in lines:
            line = line.strip()
            if not line:
                continue
                t
            amount_match = re.search(r'(\$[\d,]+\.?\d*\s*USD.*)', line)
            if amount_match and len(line) < 100:  
                structured.append(f"{current_invoice}. Amount: {line}")
                current_invoice += 1
            elif 'invoice' in line.lower() or '#' in line:
                structured.append(line)
            else:
                structured.append(line)
        
        if len(structured) > 3:
            header = "## Invoice Listing\n\n"
            return header + '\n'.join(structured)
    
    return response

def validate_and_fix_response(response: str, query_type: str = "general") -> dict:
    """Validate and fix response if needed"""
    
    validation = validate_rag_response(response, query_type)
    
    if not validation["valid"]:
       
        fixed = fix_currency_format(response)
        fixed = fix_response_structure(fixed, query_type)
        
        recheck = validate_rag_response(fixed, query_type)
        
        if recheck["valid"]:
            return {
                "valid": True,
                "text": fixed,
                "checks": recheck["checks"],
                "issues": validation["issues"],
                "fixed": True,
                "original": response
            }
    
    return validation

def extract_invoice_from_response(response: str) -> dict:
    """Extract basic invoice info"""
    
    invoice_data = {
        "invoice_number": None,
        "client_name": None,
        "total_amount": None,
        "shipping_address": None,
        "issue_date": None
    }
    
    inv_patterns = [
        r'invoice\s*#?\s*([A-Z0-9\-]+)',
        r'INV-(\w+)',
        r'Invoice\s+(\d+)',
    ]
    
    for pattern in inv_patterns:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            invoice_data["invoice_number"] = match.group(1)
            break
    
    name_patterns = [
        r'Customer[:\s]+([A-Za-z\s]+?)(?:\n|$)',
        r'Client[:\s]+([A-Za-z\s]+?)(?:\n|$)',
        r'Bill To[:\s]+([A-Za-z\s]+?)(?:\n|$)',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            invoice_data["client_name"] = match.group(1).strip()
            break
    
    amount_patterns = [
        r'Total[:\s]+\$([\d,]+\.?\d*)',
        r'Amount[:\s]+\$([\d,]+\.?\d*)',
        r'\$([\d,]+\.?\d*)\s+USD',
    ]
    
    for pattern in amount_patterns:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            invoice_data["total_amount"] = match.group(1)
            break
    
    return invoice_data