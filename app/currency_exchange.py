# app/currency_exchange.py
import requests
import json
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import re

load_dotenv()

class CurrencyExchange:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("EXCHANGERATE_API_KEY")
        self.base_url = "https://v6.exchangerate-api.com/v6"
        self.cache = {}
        self.cache_duration = timedelta(hours=1)
    
    def get_exchange_rate(self, from_currency, to_currency):
        """Get exchange rate between two currencies using API"""
        if from_currency == to_currency:
            return 1.0
            
        # Check cache first
        cache_key = f"{from_currency}_{to_currency}"
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < self.cache_duration:
                return cached_data
        
        try:
            # Use ExchangeRate-API with API key
            if not self.api_key:
                raise Exception("EXCHANGERATE_API_KEY not found in environment variables")
                
            url = f"{self.base_url}/{self.api_key}/pair/{from_currency}/{to_currency}"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if data.get("result") == "success":
                rate = data.get("conversion_rate")
                # Cache the result
                self.cache[cache_key] = (rate, datetime.now())
                return rate
            else:
                error_type = data.get('error-type', 'Unknown error')
                raise Exception(f"ExchangeRate-API error: {error_type}")
                
        except Exception as e:
            print(f"Error getting exchange rate from API: {e}")
            # Try fallback free API
            try:
                return self._get_fallback_rate(from_currency, to_currency)
            except Exception as fallback_error:
                print(f"Fallback also failed: {fallback_error}")
                # Last resort: Use ECB API (free, no key needed)
                return self._get_ecb_rate(from_currency, to_currency)
    
    def _get_fallback_rate(self, from_currency, to_currency):
        """Try Frankfurter API (free, no key needed)"""
        try:
            url = f"https://api.frankfurter.app/latest?from={from_currency}"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if "rates" in data:
                rate = data["rates"].get(to_currency)
                if rate:
                    cache_key = f"{from_currency}_{to_currency}"
                    self.cache[cache_key] = (rate, datetime.now())
                    return rate
            
            raise Exception(f"Currency {to_currency} not available in Frankfurter API")
                
        except Exception as e:
            print(f"Frankfurter API error: {e}")
            raise
    
    def _get_ecb_rate(self, from_currency, to_currency):
        """Try ECB API as last resort (EUR based, free)"""
        try:
            # ECB API only provides rates relative to EUR
            if from_currency == "EUR":
                url = "https://api.exchangeratesapi.io/latest?base=EUR"
                response = requests.get(url, timeout=10)
                data = response.json()
                
                if "rates" in data:
                    rate = data["rates"].get(to_currency)
                    if rate:
                        cache_key = f"{from_currency}_{to_currency}"
                        self.cache[cache_key] = (rate, datetime.now())
                        return rate
            
            # For non-EUR currencies, we need to convert through EUR
            # This is a limitation of the free ECB API
            if from_currency != "EUR":
                # Get EUR to from_currency rate
                url_from = f"https://api.exchangeratesapi.io/latest?base=EUR"
                response_from = requests.get(url_from, timeout=10)
                data_from = response_from.json()
                
                if "rates" in data_from and to_currency != "EUR":
                    # Get EUR to to_currency rate
                    url_to = f"https://api.exchangeratesapi.io/latest?base=EUR"
                    response_to = requests.get(url_to, timeout=10)
                    data_to = response_to.json()
                    
                    if "rates" in data_to:
                        rate_from_eur = data_from["rates"].get(from_currency)
                        rate_to_eur = data_to["rates"].get(to_currency)
                        
                        if rate_from_eur and rate_to_eur:
                            # Calculate cross rate: (1/rate_from_eur) * rate_to_eur
                            rate = (1 / rate_from_eur) * rate_to_eur
                            cache_key = f"{from_currency}_{to_currency}"
                            self.cache[cache_key] = (rate, datetime.now())
                            return rate
            
            raise Exception(f"Could not get rate from ECB API for {from_currency} to {to_currency}")
                
        except Exception as e:
            print(f"ECB API error: {e}")
            # If all APIs fail, raise an exception
            raise Exception(f"All currency APIs failed. Please check your EXCHANGERATE_API_KEY or internet connection.")
    
    def convert_amount(self, amount, from_currency, to_currency):
        """Convert amount from one currency to another"""
        if from_currency == to_currency:
            return amount
        
        rate = self.get_exchange_rate(from_currency, to_currency)
        return round(amount * rate, 2)
    
    def detect_currency(self, text):
        """Detect currency symbols and codes in text"""
        if not text:
            return "USD"
            
        text_upper = text.upper()
        
        # Check for specific patterns
        if "US$" in text or ("USD" in text_upper and "AUS$" not in text):
            return "USD"
        elif "MX$" in text or "MXN" in text_upper:
            return "MXN"
        elif "COL$" in text or "COP" in text_upper:
            return "COP"
        elif "€" in text or "EUR" in text_upper:
            return "EUR"
        elif "£" in text or "GBP" in text_upper:
            return "GBP"
        elif "$" in text:  # Generic $ symbol (default to USD)
            return "USD"
        
        # Check for currency words with context
        if "DOLLAR" in text_upper and "US" in text_upper:
            return "USD"
        elif "DOLLAR" in text_upper and "AUSTRALIAN" in text_upper:
            return "AUD"
        elif "DOLLAR" in text_upper and "CANADIAN" in text_upper:
            return "CAD"
        elif "EURO" in text_upper:
            return "EUR"
        elif "POUND" in text_upper or "STERLING" in text_upper:
            return "GBP"
        elif "PESO" in text_upper and "MEXICAN" in text_upper:
            return "MXN"
        elif "PESO" in text_upper and "COLOMBIAN" in text_upper:
            return "COP"
        elif "PESO" in text_upper:
            return "MXN"  # Default peso to MXN
            
        return "USD"  # Default currency
    
    def extract_and_convert_amounts(self, text, target_currency="USD", strict_mode=True):
        """
        Extract monetary amounts from text and convert to target currency
        
        Args:
            text: Text containing monetary amounts
            target_currency: Currency to convert to
            strict_mode: If True, only extract amounts with explicit currency symbols ($, €, etc.)
                        If False, extract any number that looks like money
        """
        import re
        
        print(f"   [Currency Extractor] strict_mode={strict_mode}, target={target_currency}")
        print(f"   [Currency Extractor] Text length: {len(text)} chars")
        print(f"   [Currency Extractor] Text sample: {text[:200]}...")
        
        if strict_mode:
            # STRICT MODE: Only extract amounts with explicit currency symbols
            patterns = [
                # Pattern 1: Symbol directly before amount (no space or with space): $1,234.56 or $ 1234.56
                r'([\$€£¥]|US\$|MX\$|COL\$|AUS\$|CAD\$)\s*([\d,]+\.?\d*)',
                
                # Pattern 2: Amount followed by currency CODE: 1,234.56 USD
                r'([\d,]+\.?\d*)\s+(USD|EUR|GBP|MXN|COP|CAD|AUD|JPY|CHF|CNY|INR|BRL|ZAR)\b',
                
                # Pattern 3: Amount with $ after (less common but valid): 1,234.56$
                r'([\d,]+\.?\d*)\s*\$(?!\d)',
                
                # Pattern 4: "Total: $X" or "Price: $X" patterns
                r'(?:total|price|amount|cost|balance|due|subtotal|discount|shipping|fee)[\s:]+\$\s*([\d,]+\.?\d*)',
            ]
        else:
            # LOOSE MODE: Extract any number that might be money
            patterns = [
                # Pattern for symbol before amount: $1,234.56, €1.234,56, £1,234
                r'([\$€£¥]|US\$|MX\$|COL\$|AUS\$|CAD\$)\s*([\d,]+(?:\.\d{2,})?(?:\.\d{3})*(?:,\d{2})?)',
                
                # Pattern for amount before symbol: 1,234.56 USD, 1.234,56 EUR
                r'([\d,]+(?:\.\d{2,})?(?:\.\d{3})*(?:,\d{2})?)\s*([A-Z]{2,3})',
                
                # Pattern for amount before symbol with $: 1,234.56 $
                r'([\d,]+(?:\.\d{2,})?(?:\.\d{3})*(?:,\d{2})?)\s*([\$€£¥])',
                
                # Pattern for spelled out currencies: 1,234.56 dollars, 1.234,56 euros
                r'([\d,]+(?:\.\d{2,})?(?:\.\d{3})*(?:,\d{2})?)\s*(dollars?|euros?|pounds?|pesos?)',
            ]
        
        conversions = []
        seen_amounts = set()  # Track amounts we've already processed
        
        for pattern in patterns:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    groups = match.groups()
                    
                    # Handle special pattern 4 (only captures amount)
                    if len(groups) == 1 and groups[0] and any(c.isdigit() for c in groups[0]):
                        amount_str = groups[0]
                        currency_indicator = "$"  # Default to $ for pattern 4
                    else:
                        # Determine which group is amount and which is currency
                        amount_str = None
                        currency_indicator = None
                        
                        for i, group in enumerate(groups):
                            if group and any(c.isdigit() for c in group):
                                # This looks like an amount
                                test_str = group.replace(',', '').replace('.', '')
                                if test_str.isdigit() or (group.count('.') <= 1 and group.replace(',', '').replace('.', '', 1).isdigit()):
                                    amount_str = group
                                    currency_indicator = groups[1] if i == 0 else groups[0]
                                    break
                    
                    if not amount_str or not currency_indicator:
                        continue
                    
                    # Clean amount string
                    amount_clean = amount_str.replace(',', '')
                    
                    # Handle European format (1.234,56 -> 1234.56)
                    if ',' in amount_str and '.' in amount_str:
                        # Check if . is thousand separator and , is decimal
                        if amount_str.index(',') > amount_str.rindex('.'):
                            # European format: 1.234,56
                            amount_clean = amount_str.replace('.', '').replace(',', '.')
                    
                    try:
                        amount = float(amount_clean)
                        
                        # Skip very small amounts (likely not money, maybe quantities)
                        if amount < 0.01:
                            continue
                        
                        # Skip if we've already processed this amount
                        amount_key = f"{amount:.2f}"
                        if amount_key in seen_amounts:
                            continue
                        
                        # In strict mode, verify currency symbol is present
                        if strict_mode:
                            has_currency_symbol = any(sym in currency_indicator for sym in ['$', '€', '£', '¥']) or \
                                                 any(code in currency_indicator.upper() for code in ['USD', 'EUR', 'GBP', 'MXN', 'COP', 'CAD', 'AUD'])
                            if not has_currency_symbol:
                                continue
                        
                        seen_amounts.add(amount_key)
                        
                        # Detect currency
                        from_currency = self.detect_currency(currency_indicator)
                        
                        print(f"   [Currency Extractor] Found: {amount} {from_currency} (from indicator: '{currency_indicator}')")
                        
                        # Convert amount
                        converted_amount = self.convert_amount(amount, from_currency, target_currency)
                        
                        # Get exchange rate
                        rate = self.get_exchange_rate(from_currency, target_currency) if from_currency != target_currency else 1.0
                        
                        conversions.append({
                            "original_amount": amount,
                            "original_currency": from_currency,
                            "converted_amount": converted_amount,
                            "target_currency": target_currency,
                            "rate": rate,
                            "original_text": match.group(0)
                        })
                        
                    except ValueError as ve:
                        print(f"ValueError converting amount {amount_str}: {ve}")
                        continue
                    except Exception as e:
                        print(f"Error processing amount {amount_str}: {e}")
                        continue
                        
            except Exception as e:
                print(f"Error in regex pattern {pattern}: {e}")
                continue
        
        print(f"   [Currency Extractor] Total conversions found: {len(conversions)}")
        return conversions
    
    # NEW METHODS FOR DESTINATION-BASED CONVERSION
    
    def get_currency_for_country(self, country):
        """Get currency code for a given country"""
        if not country:
            return "USD"
            
        # Country to currency mapping
        COUNTRY_CURRENCY_MAP = {
            # North America
            "United States": "USD", "USA": "USD", "US": "USD",
            "Mexico": "MXN", 
            "Canada": "CAD",
            
            # Europe
            "United Kingdom": "GBP", "UK": "GBP", "England": "GBP", "Scotland": "GBP", "Wales": "GBP",
            "Germany": "EUR", "Deutschland": "EUR",
            "France": "EUR", 
            "Italy": "EUR", "Italia": "EUR",
            "Spain": "EUR", "España": "EUR",
            "Russia": "RUB", "Russian Federation": "RUB", "Россия": "RUB",
            "Netherlands": "EUR", "Holland": "EUR",
            "Belgium": "EUR",
            "Portugal": "EUR",
            "Ireland": "EUR",
            "Switzerland": "CHF",
            "Sweden": "SEK",
            "Norway": "NOK",
            "Denmark": "DKK",
            "Poland": "PLN",
            "Czech Republic": "CZK",
            "Austria": "EUR",
            "Finland": "EUR",
            "Greece": "EUR",
            
            # Asia
            "Japan": "JPY", "日本": "JPY",
            "China": "CNY", "中国": "CNY",
            "India": "INR",
            "South Korea": "KRW", "Korea": "KRW", "대한민국": "KRW",
            "Singapore": "SGD",
            "Thailand": "THB",
            "Vietnam": "VND",
            "Philippines": "PHP",
            "Indonesia": "IDR",
            "Malaysia": "MYR",
            "Hong Kong": "HKD",
            "Taiwan": "TWD",
            
            # Oceania
            "Australia": "AUD",
            "New Zealand": "NZD",
            
            # South America
            "Brazil": "BRL", "Brasil": "BRL",
            "Argentina": "ARS",
            "Chile": "CLP",
            "Colombia": "COP",
            "Peru": "PEN",
            "Venezuela": "VES",
            
            # Africa
            "South Africa": "ZAR",
            "Egypt": "EGP",
            "Nigeria": "NGN",
            "Kenya": "KES",
            "Morocco": "MAD",
        }
        
        # Try exact match first
        currency = COUNTRY_CURRENCY_MAP.get(country)
        if currency:
            return currency
        
        # Try case-insensitive match
        for country_name, currency_code in COUNTRY_CURRENCY_MAP.items():
            if country_name.lower() == country.lower():
                return currency_code
        
        # Check if country contains key words
        country_lower = country.lower()
        if any(word in country_lower for word in ["russia", "russian", "россия"]):
            return "RUB"
        elif any(word in country_lower for word in ["france", "french"]):
            return "EUR"
        elif any(word in country_lower for word in ["germany", "german", "deutschland"]):
            return "EUR"
        elif any(word in country_lower for word in ["spain", "spanish", "españa"]):
            return "EUR"
        elif any(word in country_lower for word in ["italy", "italian", "italia"]):
            return "EUR"
        elif any(word in country_lower for word in ["japan", "japanese", "日本"]):
            return "JPY"
        elif any(word in country_lower for word in ["china", "chinese", "中国"]):
            return "CNY"
        elif any(word in country_lower for word in ["mexico", "mexican", "méxico"]):
            return "MXN"
        elif any(word in country_lower for word in ["uk", "united kingdom", "britain", "england"]):
            return "GBP"
        
        return "USD"  # Default to USD
    
    def get_country_from_address(self, address):
        """Extract country from shipping address string."""
        return self.extract_country_from_address(address)
    
    def extract_country_from_address(self, address):
        """Extract country from shipping address string."""
        if not address:
            return None
        
        # Country to currency mapping (just for reference)
        COUNTRY_LIST = {
            # North America
            "United States", "USA", "US", "United States of America",
            "Mexico", "México", "Mex",
            "Canada", "CAN",
            
            # Europe
            "United Kingdom", "UK", "U.K.", "Great Britain", "England", "Scotland", "Wales", 
            "Germany", "DE", "DEU", "Deutschland",
            "France", "FR", "FRA",
            "Italy", "IT", "ITA", "Italia",
            "Spain", "ES", "ESP", "España",
            "Russia", "RU", "RUS", "Russian Federation", "Россия",
            "Netherlands", "NL", "NLD",
            "Belgium", "BE", "BEL",
            "Portugal", "PT", "PRT",
            "Ireland", "IE", "IRL",
            "Switzerland", "CH", "CHE",
            "Sweden", "SE", "SWE",
            "Norway", "NO", "NOR",
            "Denmark", "DK", "DNK",
            "Poland", "PL", "POL",
            "Czech Republic", "CZ", "CZE",
            "Austria", "AT", "AUT",
            "Finland", "FI", "FIN",
            "Greece", "GR", "GRC",
            
            # Asia
            "Japan", "JP", "JPN", "日本",
            "China", "CN", "CHN", "中国",
            "India", "IN", "IND",
            "South Korea", "Korea", "KR", "KOR", "한국", "대한민국",
            "Singapore", "SG", "SGP",
            "Thailand", "TH", "THA",
            
            # Oceania
            "Australia", "AU", "AUS",
            "New Zealand", "NZ", "NZL",
            
            # South America
            "Brazil", "BR", "BRA", "Brasil",
            "Argentina", "AR", "ARG",
            "Chile", "CL", "CHL",
            "Colombia", "CO", "COL",
            "Peru", "PE", "PER",
            
            # Africa
            "South Africa", "ZA", "ZAF",
            "Egypt", "EG", "EGY",
        }
        
        # City/region to country mapping
        CITY_COUNTRY_MAP = {
            "Moscow": "Russia", "Saint Petersburg": "Russia", "St. Petersburg": "Russia",
            "London": "United Kingdom", "Manchester": "United Kingdom", "Birmingham": "United Kingdom",
            "Paris": "France", "Lyon": "France", "Marseille": "France",
            "Berlin": "Germany", "Munich": "Germany", "Hamburg": "Germany",
            "Madrid": "Spain", "Barcelona": "Spain", "Valencia": "Spain",
            "Rome": "Italy", "Milan": "Italy", "Naples": "Italy",
            "Tokyo": "Japan", "Osaka": "Japan", "Kyoto": "Japan",
            "Beijing": "China", "Shanghai": "China", "Guangzhou": "China",
            "New York": "United States", "Los Angeles": "United States", "Chicago": "United States",
            "Mexico City": "Mexico", "Guadalajara": "Mexico", "Monterrey": "Mexico",
            "Toronto": "Canada", "Vancouver": "Canada", "Montreal": "Canada",
            "Sydney": "Australia", "Melbourne": "Australia", "Brisbane": "Australia",
            "São Paulo": "Brazil", "Rio de Janeiro": "Brazil", "Brasília": "Brazil",
            "Mumbai": "India", "Delhi": "India", "Bangalore": "India",
            "Seoul": "South Korea", "Busan": "South Korea", "Incheon": "South Korea",
        }
        
        address_lower = address.strip().lower()
        address_original = address.strip()
        
        # Split by common separators
        parts = [part.strip() for part in address_original.split(',')]
        
        # Check from end to start (country is usually at the end)
        for i in range(len(parts)-1, -1, -1):
            part = parts[i]
            
            # Check if part is a known country
            for country in COUNTRY_LIST:
                if country.lower() == part.lower():
                    return country
        
        # If no country found, check if we can infer from city/region
        for part in parts:
            for city, country in CITY_COUNTRY_MAP.items():
                if city.lower() == part.lower():
                    return country
        
        # Try to find country keywords in the address
        for country in COUNTRY_LIST:
            if country.lower() in address_lower:
                return country
        
        return None
    
    def get_currency_for_address(self, address):
        """Get currency code for a shipping address."""
        country = self.extract_country_from_address(address)
        return self.get_currency_for_country(country)
    
    def convert_invoice_amounts(self, invoice_text, shipping_address):
        """
        Convert invoice amounts to destination country's currency.
        
        Args:
            invoice_text (str): Invoice text containing amounts
            shipping_address (str): Shipping address from invoice
        
        Returns:
            dict: Original and converted amounts with currency info
        """
        # Get destination currency
        dest_currency = self.get_currency_for_address(shipping_address)
        
        if dest_currency == "USD":
            return {
                "original_text": invoice_text,
                "converted_text": invoice_text,
                "dest_currency": "USD",
                "conversions": [],
                "note": "Amounts already in USD"
            }
        
        # Extract and convert amounts
        conversions = self.extract_and_convert_amounts(invoice_text, dest_currency, strict_mode=False)
        
        if not conversions:
            return {
                "original_text": invoice_text,
                "converted_text": invoice_text,
                "dest_currency": dest_currency,
                "conversions": [],
                "note": f"No currency amounts found to convert to {dest_currency}"
            }
        
        # Create converted text by replacing amounts
        converted_text = invoice_text
        for conv in reversed(conversions):  # Reverse to avoid position issues
            original_with_currency = f"{conv['original_amount']} {conv['original_currency']}"
            converted_with_currency = f"{conv['converted_amount']} {dest_currency}"
            
            # Try to replace the exact match first
            if conv['original_text'] in converted_text:
                replacement = f"{conv['original_text']} (approx. {converted_with_currency})"
                converted_text = converted_text.replace(conv['original_text'], replacement)
            elif original_with_currency in converted_text:
                replacement = f"{original_with_currency} (approx. {converted_with_currency})"
                converted_text = converted_text.replace(original_with_currency, replacement)
        
        return {
            "original_text": invoice_text,
            "converted_text": converted_text,
            "dest_currency": dest_currency,
            "conversions": conversions,
            "note": f"Converted from USD to {dest_currency}"
        }
    
    def enhance_answer_with_conversion(self, answer, shipping_address):
        """
        Enhance LLM answer with currency conversion based on shipping address.
        
        Args:
            answer (str): LLM-generated answer
            shipping_address (str): Shipping address from invoice
        
        Returns:
            str: Enhanced answer with currency conversion
        """
        dest_currency = self.get_currency_for_address(shipping_address)
        
        if dest_currency == "USD":
            return answer
        
        # Extract amounts from answer - use strict_mode=False to catch all amounts
        conversions = self.extract_and_convert_amounts(answer, dest_currency, strict_mode=False)
        
        if not conversions:
            return answer
        
        # Enhance answer with conversions
        enhanced_answer = answer
        
        for conv in reversed(conversions):
            original_with_currency = f"{conv['original_amount']} {conv['original_currency']}"
            converted_with_currency = f"{conv['converted_amount']} {dest_currency}"
            
            # Add conversion note after each amount
            if conv['original_text'] in enhanced_answer:
                replacement = f"{conv['original_text']} (approximately {converted_with_currency})"
                enhanced_answer = enhanced_answer.replace(conv['original_text'], replacement)
        
        # Add summary note
        rate = conversions[0]['rate'] if conversions else 1.0
        enhanced_answer += f"\n\n*Note: Converted from USD to {dest_currency} at approximate rate of 1 USD = {rate:.4f} {dest_currency}*"
        
        return enhanced_answer

# Singleton instance
currency_exchanger = CurrencyExchange()