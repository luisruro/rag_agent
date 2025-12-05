from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

class ShipTo(BaseModel):
    postal_code: str = Field(description="Postal code of the shipping address")
    city: str = Field(description="City of the shipping address")
    state: str = Field(description="State or province of the shipping address")
    country: str = Field(description="Country of the shipping address")

class InvoiceItem(BaseModel):
    product_name: str = Field(description="Name of the product (e.g., Brother Copy Machine, Laser)")
    subcategory: str = Field(description="Subcategory of the product (e.g., Copiers)")
    category: str = Field(description="Category of the product (e.g., Technology)")
    product_id: str = Field(description="Unique identifier for the product (e.g., TEC-CO-3589)")
    quantity: int = Field(description="Quantity of the product ordered")
    unit_cost: float = Field(description="Cost per unit of the product")
    subtotal: float = Field(description="Subtotal amount for this item before discount and shipping")
    discount_percent: float = Field(description="Discount applied to this item (in percentage)")
    shipping_fee: float = Field(description="Shipping fee applied to this item")
    total_amount_payable: float = Field(description="Total amount payable for this item after discount and shipping")

class Invoice(BaseModel):
    invoice_id: str = Field(description="Unique identifier for the invoice")
    order_id: str = Field(description="Order ID associated with the invoice")
    order_date: date = Field(description="Date when the order was placed")
    ship_mode: str = Field(description="Shipping method (e.g., First Class, Standard)")
    bill_to: str = Field(description="Name of the customer billed")
    ship_to: ShipTo = Field(description="Shipping address details")
    items: List[InvoiceItem] = Field(description="List of items included in the invoice")
    notes: Optional[str] = Field(description="Additional notes or comments regarding the invoice")
    total_amount_payable: float = Field(description="Total amount payable for the invoice")
    currency: str = Field(description="Currency of the invoice amounts (e.g., USD, EUR, MXN)")
    
