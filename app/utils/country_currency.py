# app/utils/country_currency.py
"""
Utility functions for country to currency mapping and address parsing
"""

COUNTRY_CURRENCY_MAP = {
    # North America
    "United States": "USD", "USA": "USD", "US": "USD", "America": "USD",
    "Canada": "CAD",
    "Mexico": "MXN",
    
    # Europe
    "United Kingdom": "GBP", "UK": "GBP", "Britain": "GBP", "England": "GBP",
    "Germany": "EUR", "Deutschland": "EUR",
    "France": "EUR",
    "Italy": "EUR", "Italia": "EUR",
    "Spain": "EUR", "España": "EUR",
    "Netherlands": "EUR", "Holland": "EUR",
    "Belgium": "EUR",
    "Portugal": "EUR",
    "Ireland": "EUR", "Éire": "EUR",
    "Austria": "EUR", "Österreich": "EUR",
    "Finland": "EUR", "Suomi": "EUR",
    "Greece": "EUR", "Ελλάδα": "EUR",
    "Russia": "RUB", "Russian Federation": "RUB", "Россия": "RUB",
    "Switzerland": "CHF", "Swiss": "CHF",
    "Sweden": "SEK", "Sverige": "SEK",
    "Norway": "NOK",
    "Denmark": "DKK",
    "Poland": "PLN", "Polska": "PLN",
    "Czech Republic": "CZK", "Czechia": "CZK",
    "Hungary": "HUF", "Magyarország": "HUF",
    "Romania": "RON",
    "Bulgaria": "BGN", "България": "BGN",
    "Ukraine": "UAH", "Україна": "UAH",
    "Bashkortostan": "RUB",  # Region in Russia
    
    # Asia
    "Japan": "JPY", "日本": "JPY",
    "China": "CNY", "中国": "CNY",
    "India": "INR",
    "South Korea": "KRW", "Korea": "KRW", "대한민국": "KRW",
    "Australia": "AUD",
    "New Zealand": "NZD",
    "Singapore": "SGD",
    "Hong Kong": "HKD",
    "Taiwan": "TWD", "Taiwan Province": "TWD",
    "Thailand": "THB", "ไทย": "THB",
    "Vietnam": "VND", "Việt Nam": "VND",
    "Philippines": "PHP",
    "Malaysia": "MYR",
    "Indonesia": "IDR",
    
    # Middle East
    "Saudi Arabia": "SAR", "السعودية": "SAR",
    "United Arab Emirates": "AED", "UAE": "AED",
    "Qatar": "QAR", "قطر": "QAR",
    "Kuwait": "KWD", "الكويت": "KWD",
    "Israel": "ILS", "ישראל": "ILS",
    "Turkey": "TRY", "Türkiye": "TRY",
    
    # South America
    "Brazil": "BRL", "Brasil": "BRL",
    "Argentina": "ARS",
    "Chile": "CLP",
    "Colombia": "COP",
    "Peru": "PEN", "Perú": "PEN",
    "Venezuela": "VES",
    
    # Africa
    "South Africa": "ZAR",
    "Egypt": "EGP", "مصر": "EGP",
    "Nigeria": "NGN",
    "Kenya": "KES",
    "Ghana": "GHS",
    "Morocco": "MAD", "المغرب": "MAD",
}

# City/Region to country mapping (for cases where only city is mentioned)
CITY_COUNTRY_MAP = {
    "Salavat": "Russia",
    "Moscow": "Russia", "Москва": "Russia",
    "London": "United Kingdom",
    "Paris": "France",
    "Berlin": "Germany",
    "Tokyo": "Japan",
    "Beijing": "China", "上海": "China",
    "New York": "United States", "NYC": "United States",
    "Los Angeles": "United States", "LA": "United States",
    "Toronto": "Canada",
    "Sydney": "Australia",
    "Dubai": "United Arab Emirates",
    "Mumbai": "India",
    "São Paulo": "Brazil",
    "Mexico City": "Mexico", "Ciudad de México": "Mexico",
}

def extract_country_from_address(address):
    """
    Extract country from shipping address string.
    
    Args:
        address (str): Shipping address (e.g., "Salavat, Bashkortostan, Russia")
    
    Returns:
        str: Country name or None if not found
    """
    if not address:
        return None
    
    # Clean and normalize the address
    address_lower = address.strip().lower()
    address_original = address.strip()
    
    # Split by common separators
    parts = [part.strip() for part in address_original.split(',')]
    
    # Check from end to start (country is usually at the end)
    for i in range(len(parts)-1, -1, -1):
        part = parts[i]
        
        # Check if part is a known country
        for country in COUNTRY_CURRENCY_MAP:
            if country.lower() == part.lower():
                return country
        
        # Check for abbreviated countries
        if part.upper() in ["USA", "US", "UK", "UAE"]:
            if part.upper() == "USA" or part.upper() == "US":
                return "United States"
            elif part.upper() == "UK":
                return "United Kingdom"
            elif part.upper() == "UAE":
                return "United Arab Emirates"
    
    # If no country found, check if we can infer from city/region
    for part in parts:
        # Check if part is a known city
        for city, country in CITY_COUNTRY_MAP.items():
            if city.lower() == part.lower():
                return country
        
        # Check for regions that imply a country
        if "bashkortostan" in address_lower:
            return "Russia"
        if "california" in address_lower or "texas" in address_lower:
            return "United States"
        if "ontario" in address_lower or "quebec" in address_lower:
            return "Canada"
        if "england" in address_lower or "scotland" in address_lower:
            return "United Kingdom"
    
    return None

def get_currency_for_country(country):
    """
    Get currency code for a given country.
    
    Args:
        country (str): Country name
    
    Returns:
        str: ISO currency code or "USD" if country not found
    """
    if not country:
        return "USD"
    
    return COUNTRY_CURRENCY_MAP.get(country, "USD")

def get_currency_for_address(address):
    """
    Get currency code for a shipping address.
    
    Args:
        address (str): Shipping address
    
    Returns:
        str: ISO currency code
    """
    country = extract_country_from_address(address)
    return get_currency_for_country(country)