# app/currency_exchange.py
import requests
import json
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

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
    
    def extract_and_convert_amounts(self, text, target_currency="USD"):
        """Extract monetary amounts from text and convert to target currency"""
        import re
        
        # Enhanced pattern to find amounts with various formats
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
        
        for pattern in patterns:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    # Determine which group is amount and which is currency
                    groups = match.groups()
                    
                    # Find the amount (the group that looks like a number)
                    amount_str = None
                    currency_indicator = None
                    
                    for i, group in enumerate(groups):
                        if group and any(c.isdigit() for c in group):
                            # Clean and test if it's a valid number
                            test_str = group.replace(',', '').replace('.', '')
                            if test_str.isdigit() or ('.' in group and group.replace(',', '').replace('.', '', 1).isdigit()):
                                amount_str = group
                                currency_indicator = groups[0] if i == 1 else groups[1]
                                break
                    
                    if not amount_str or not currency_indicator:
                        continue
                    
                    # Clean amount string (handle different decimal separators)
                    amount_clean = amount_str.replace(',', '')
                    
                    # Handle European format (1.234,56 -> 1234.56)
                    if '.' in amount_clean and ',' in amount_str:
                        # Check if . is thousand separator
                        parts = amount_str.split('.')
                        if len(parts[-1].replace(',', '')) == 2 and ',' in parts[-1]:
                            # European format: 1.234,56
                            amount_clean = amount_str.replace('.', '').replace(',', '.')
                        else:
                            # US format: 1,234.56
                            amount_clean = amount_str.replace(',', '')
                    
                    try:
                        amount = float(amount_clean)
                        
                        # Detect currency
                        from_currency = self.detect_currency(currency_indicator)
                        
                        # Convert amount
                        converted_amount = self.convert_amount(amount, from_currency, target_currency)
                        
                        # Get exchange rate
                        rate = self.get_exchange_rate(from_currency, target_currency) if from_currency != target_currency else 1.0
                        
                        conversions.append({
                            "original_amount": amount,
                            "original_currency": from_currency,
                            "converted_amount": converted_amount,
                            "target_currency": target_currency,
                            "rate": rate
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
        
        return conversions

# Singleton instance
currency_exchanger = CurrencyExchange()