# app/utils/currency_formatter.py
"""
Utility functions for formatting currency amounts
"""

CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CAD": "CA$",
    "AUD": "A$",
    "CNY": "¥",
    "RUB": "₽",
    "INR": "₹",
    "BRL": "R$",
    "MXN": "MX$",
    "KRW": "₩",
    "TRY": "₺",
    "CHF": "CHF",
    "SEK": "kr",
    "NOK": "kr",
    "DKK": "kr",
    "PLN": "zł",
    "HUF": "Ft",
    "CZK": "Kč",
    "ILS": "₪",
    "ZAR": "R",
    "SGD": "S$",
    "HKD": "HK$",
    "NZD": "NZ$",
    "THB": "฿",
    "PHP": "₱",
    "IDR": "Rp",
    "MYR": "RM",
    "SAR": "ر.س",
    "AED": "د.إ",
    "COP": "COL$",
    "CLP": "CLP$",
    "PEN": "S/",
    "ARS": "AR$",
    "VES": "Bs.",
}

def format_currency_amount(amount, currency_code="USD", include_symbol=True):
    """
    Format a currency amount with proper symbol and decimal places.
    
    Args:
        amount (float): The amount to format
        currency_code (str): ISO currency code (e.g., "USD", "EUR")
        include_symbol (bool): Whether to include currency symbol
    
    Returns:
        str: Formatted currency string
    """
    # Determine decimal places based on currency
    zero_decimal_currencies = ["JPY", "KRW", "VND", "ISK", "CLP", "PYG"]
    
    if currency_code in zero_decimal_currencies:
        formatted_amount = f"{int(round(amount)):,}"
        decimals = 0
    else:
        formatted_amount = f"{amount:,.2f}"
        decimals = 2
    
    # Add currency symbol if requested
    if include_symbol:
        symbol = CURRENCY_SYMBOLS.get(currency_code, f"{currency_code} ")
        return f"{symbol}{formatted_amount}"
    else:
        return f"{formatted_amount} {currency_code}"

def extract_numeric_value(currency_string):
    """
    Extract numeric value from a currency string.
    
    Args:
        currency_string (str): String like "$1,234.56 USD" or "€1.234,56"
    
    Returns:
        float: Numeric value or None if not found
    """
    import re
    
    if not currency_string:
        return None
    
    # Remove currency symbols and codes
    cleaned = re.sub(r'[^\d\.,\- ]', '', currency_string).strip()
    
    if not cleaned:
        return None
    
    # Handle European format (1.234,56)
    if '.' in cleaned and ',' in cleaned:
        # Check if . is thousand separator (1.234,56)
        if cleaned.count('.') == 1 and len(cleaned.split('.')[-1].replace(',', '')) == 2:
            # European format: 1.234,56 -> 1234.56
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            # Mixed format, clean commas and dots
            cleaned = cleaned.replace(',', '')
    
    # Handle US format (1,234.56)
    elif ',' in cleaned:
        cleaned = cleaned.replace(',', '')
    
    try:
        return float(cleaned)
    except ValueError:
        # Try to extract using regex as fallback
        match = re.search(r'([\d\.,]+)', currency_string)
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except ValueError:
                return None
        return None

def parse_currency_string(currency_string):
    """
    Parse a currency string to extract amount and currency code.
    
    Args:
        currency_string (str): String like "$1,234.56 USD"
    
    Returns:
        tuple: (amount, currency_code) or (None, None)
    """
    from app.currency_exchange import currency_exchanger
    
    if not currency_string:
        return None, None
    
    # Extract numeric value
    amount = extract_numeric_value(currency_string)
    if amount is None:
        return None, None
    
    # Detect currency
    currency_code = currency_exchanger.detect_currency(currency_string)
    
    return amount, currency_code