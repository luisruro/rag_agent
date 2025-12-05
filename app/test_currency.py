# test_currency.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from currency_exchange import currency_exchanger

# Test currency detection and conversion
test_texts = [
    "The invoice amount is €1,250.00 for services rendered.",
    "Total due: $5,000 USD",
    "Payment of £2,500 is required.",
    "The loan is for MXN 50,000 pesos.",
    "Installment: 1,200 EUR per month."
]

print("Testing currency exchange functionality:\n")
print("=" * 50)

for text in test_texts:
    print(f"\nOriginal text: {text}")
    
    # Detect currency
    currency = currency_exchanger.detect_currency(text)
    print(f"Detected currency: {currency}")
    
    # Extract and convert amounts
    conversions = currency_exchanger.extract_and_convert_amounts(text, "USD")
    if conversions:
        for conv in conversions:
            print(f"  → {conv['original_amount']} {conv['original_currency']} = {conv['converted_amount']} USD")
    else:
        print("  → No amounts found")
    
    print("-" * 30)

# Test direct conversion
print("\n\nDirect conversion tests:")
print(f"100 EUR to USD: {currency_exchanger.convert_amount(100, 'EUR', 'USD')}")
print(f"100 GBP to USD: {currency_exchanger.convert_amount(100, 'GBP', 'USD')}")
print(f"1000 MXN to USD: {currency_exchanger.convert_amount(1000, 'MXN', 'USD')}")