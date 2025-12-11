from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

class ShipTo(BaseModel):
    postal_code: Optional[str] = Field(description="Postal code of the shipping address")
    city: Optional[str] = Field(description="City of the shipping address")
    state: Optional[str] = Field(description="State or province of the shipping address")
    country: Optional[str] = Field(description="Country of the shipping address")

class CurrencyConversion(BaseModel):
    """Currency conversion information for a monetary amount"""
    original_amount: float = Field(description="Amount in original currency (USD)")
    original_currency: str = Field(default="USD", description="Original currency code")
    converted_amount: Optional[float] = Field(description="Amount converted to local currency")
    local_currency: Optional[str] = Field(description="Local currency based on shipping country")
    exchange_rate: Optional[float] = Field(description="Exchange rate used for conversion")

class InvoiceItem(BaseModel):
    product_name: Optional[str] = Field(description="Name of the product (e.g., Brother Copy Machine, Laser)")
    subcategory: Optional[str] = Field(description="Subcategory of the product (e.g., Copiers)")
    category: Optional[str] = Field(description="Category of the product (e.g., Technology)")
    product_id: Optional[str] = Field(description="Unique identifier for the product (e.g., TEC-CO-3589)")
    quantity: Optional[int] = Field(description="Quantity of the product ordered")
    unit_cost: Optional[float] = Field(description="Cost per unit of the product")
    subtotal: Optional[float] = Field(description="Subtotal amount for this item before discount and shipping")
    discount_percent: Optional[float] = Field(description="Discount applied to this item (in percentage)")
    shipping_fee: Optional[float] = Field(description="Shipping fee applied to this item")
    total_amount_payable: Optional[float] = Field(description="Total amount payable for this item after discount and shipping")

class Invoice(BaseModel):
    """Complete invoice information with currency conversion support"""
    invoice_id: Optional[str] = Field(description="Unique identifier for the invoice")
    order_id: Optional[str] = Field(description="Order ID associated with the invoice")
    order_date: Optional[date] = Field(description="Date when the order was placed")
    ship_mode: Optional[str] = Field(description="Shipping method (e.g., First Class, Standard)")
    bill_to: Optional[str] = Field(description="Name of the customer billed")
    ship_to: Optional[ShipTo] = Field(description="Shipping address details")
    items: Optional[List[InvoiceItem]] = Field(description="List of items included in the invoice")
    notes: Optional[str] = Field(description="Additional notes or comments regarding the invoice")
    
    # Financial fields with conversion support
    subtotal: Optional[CurrencyConversion] = Field(description="Invoice subtotal with currency conversion")
    discount: Optional[CurrencyConversion] = Field(description="Total discount applied with currency conversion")
    shipping: Optional[CurrencyConversion] = Field(description="Total shipping cost with currency conversion")
    balance_due: Optional[CurrencyConversion] = Field(description="Balance due with currency conversion")
    total_amount_payable: Optional[CurrencyConversion] = Field(description="Total amount payable with currency conversion")
    
    # Metadata
    currency: str = Field(default="USD", description="Base currency of the invoice (typically USD)")
    local_currency: Optional[str] = Field(description="Local currency based on shipping address")