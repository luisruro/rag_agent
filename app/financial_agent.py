# app/financial_agent.py
import re
import json
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from collections import defaultdict
import statistics

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

class FinancialAnalysisAgent:
    def __init__(self, api_key: str = None):
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0.3,
            api_key=api_key
        )
        
        # Enhanced detection patterns
        self.analysis_patterns = [
            # Explicit analysis keywords
            r'analyze', r'analysis', r'analize', r'analise',
            r'trend', r'pattern', r'insight',
            r'summary', r'summarize', r'overview', r'report',
            r'compare', r'comparison', r'comparative',
            r'statistic', r'metric', r'stat',
            r'breakdown', r'distribution', r'frequency',
            r'average', r'mean', r'median', r'mode',
            r'highest', r'lowest', r'maximum', r'minimum',
            r'correlation', r'relationship',
            
            # Business strategy and recommendations
            r'what products should', r'which products should',
            r'recommend products', r'suggest products',
            r'product expansion', r'expand product',
            r'business should expand', r'business expansion',
            r'growth opportunities', r'opportunities for growth',
            r'improve business', r'improve sales',
            r'increase revenue', r'increase profit',
            r'best selling', r'top products',
            r'product recommendations', r'business recommendations',
            r'financial recommendations', r'financial suggestions',
            r'as a financial agent', r'financial advice',
            r'business advice', r'strategic advice',
            r'what would you recommend', r'what do you suggest',
            r'how can we improve', r'how to increase',
            
            # Insight and analysis phrases
            r'provide insights', r'give me insights',
            r'deep dive', r'detailed analysis',
            r'comprehensive analysis', r'thorough analysis',
            r'business analysis', r'financial analysis',
            r'market analysis', r'performance analysis',
            
            # Question patterns for recommendations
            r'what should.*business', r'what would.*suggest',
            r'how should.*proceed', r'where should.*focus',
            r'which areas.*improve', r'what opportunities',
        ]
        
        # Simple query patterns that should NOT trigger analysis
        self.simple_patterns = [
            r'get\s+.*\s+analysis',
            r'what\s+is\s+.*\s+analysis',
            r'analyze\s+invoice\s+#\d+',
            r'analysis\s+of\s+invoice\s+#\d+',
            r'get\s+.*\s+trends',
            r'find\s+.*\s+patterns',
            r'show\s+me\s+analysis',
        ]
        
        print(" Financial Analysis Agent initialized with enhanced detection")

    def detect_analysis_query(self, question: str) -> bool:
        """Detect if the user is asking for financial analysis or business recommendations"""
        question_lower = question.lower().strip()
        
        # Check for simple queries first (these should NOT trigger analysis)
        for pattern in self.simple_patterns:
            if re.search(pattern, question_lower, re.IGNORECASE):
                print(f"DEBUG: Simple query pattern detected: '{pattern}'")
                return False
        
        # Check for analysis patterns
        has_analysis_pattern = False
        for pattern in self.analysis_patterns:
            if re.search(pattern, question_lower, re.IGNORECASE):
                has_analysis_pattern = True
                break
        
        if not has_analysis_pattern:
            return False
        
        # Additional check for question words that indicate analysis
        analysis_question_patterns = [
            r'how\s+.*\s+performing',
            r'what\s+can\s+.*\s+tell',
            r'what\s+are\s+the\s+.*\s+trends',
            r'how\s+is\s+the\s+.*\s+trending',
            r'what\s+insights\s+.*\s+provide',
            r'what\s+recommendations\s+.*',
            r'how\s+could\s+.*\s+improve',
            r'what\s+should\s+.*\s+do',
        ]
        
        has_analysis_question = any(
            re.search(pattern, question_lower, re.IGNORECASE) 
            for pattern in analysis_question_patterns
        )
        
        # Also check for explicit business/financial advisor context
        has_financial_context = any(
            keyword in question_lower for keyword in [
                'financial agent', 'business advisor', 'as a financial',
                'financial suggestions', 'business suggestions',
                'make recommendations', 'provide recommendations',
                'give advice', 'offer suggestions'
            ]
        )
        
        is_analysis_query = has_analysis_pattern or has_analysis_question or has_financial_context
        
        print(f"DEBUG Financial Agent Detection:")
        print(f"  Question: '{question}'")
        print(f"  Has analysis pattern: {has_analysis_pattern}")
        print(f"  Has analysis question: {has_analysis_question}")
        print(f"  Has financial context: {has_financial_context}")
        print(f"  Is analysis query: {is_analysis_query}")
        
        return is_analysis_query

    def extract_invoice_data(self, context: str) -> List[Dict]:
        """Extract structured invoice data from context - IMPROVED VERSION"""
        invoices = []
        
        # Try to find invoice sections
        invoice_sections = re.findall(r'\[Fragment \d+\].*?(?=\[Fragment \d+\]|$)', context, re.DOTALL)
        
        for section in invoice_sections:
            invoice_data = {}
            
            # Extract invoice number
            inv_match = re.search(r'Invoice\s*[#:]?\s*(\d+)', section, re.IGNORECASE)
            if inv_match:
                invoice_data['invoice_number'] = inv_match.group(1)
            
            # Extract customer name
            cust_match = re.search(r'Customer[:\s]+([^\n]+)', section, re.IGNORECASE)
            if not cust_match:
                cust_match = re.search(r'👤 Customer:\s*([^\n]+)', section, re.IGNORECASE)
            
            if cust_match:
                invoice_data['customer'] = cust_match.group(1).strip().replace('👤', '').replace('Customer:', '').strip()
            
            # Extract total amount - IMPROVED PATTERNS
            amount_patterns = [
                r'Total\s*(?:Amount|Due)?[:\s\$]*([\d,]+\.?\d*)',
                r'💰 Financial Summary.*?Total Amount Payable[:\s\$]*([\d,]+\.?\d*)',
                r'Amount[:\s\$]*([\d,]+\.?\d*)',
                r'Total[:\s\$]*([\d,]+\.?\d*)',
                r'Balance Due[:\s\$]*([\d,]+\.?\d*)',
            ]
            
            invoice_data['total_amount'] = 0
            for pattern in amount_patterns:
                total_match = re.search(pattern, section, re.IGNORECASE | re.DOTALL)
                if total_match:
                    try:
                        amount = float(total_match.group(1).replace(',', ''))
                        invoice_data['total_amount'] = amount
                        break
                    except:
                        continue
            
            # Extract date
            date_match = re.search(r'Date[:\s]+([^\n]+)', section, re.IGNORECASE)
            if not date_match:
                date_match = re.search(r'Order Date[:\s]+([^\n]+)', section, re.IGNORECASE)
            if not date_match:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', section)
            
            if date_match:
                invoice_data['date'] = date_match.group(1).strip()
            
            # Extract products - IMPROVED PRODUCT EXTRACTION
            products = []
            
            # Pattern 1: Product lines with @ symbol
            product_lines = re.finditer(r'([A-Za-z0-9\s\-\.\/\&]+?)\s*[@]\s*\$?([\d,]+\.?\d*)', section)
            for match in product_lines:
                product_name = match.group(1).strip()
                try:
                    price = float(match.group(2).replace(',', ''))
                    if len(product_name) > 3:  # Filter out short/nonsense names
                        products.append({
                            'name': product_name,
                            'price': price
                        })
                except:
                    continue
            
            # Pattern 2: Product lines in itemized lists
            if not products:
                list_patterns = [
                    r'🛒 Items Ordered:(.*?)(?:\n\n|\$\s*[\d,]+\.?\d*)',
                    r'Products:(.*?)(?:\n\n|\$\s*[\d,]+\.?\d*)',
                    r'Items:(.*?)(?:\n\n|\$\s*[\d,]+\.?\d*)',
                ]
                
                for pattern in list_patterns:
                    items_match = re.search(pattern, section, re.IGNORECASE | re.DOTALL)
                    if items_match:
                        items_text = items_match.group(1)
                        # Extract product names from item list
                        item_lines = re.findall(r'([A-Z][^@\n]+?(?:Qty:|@|\$|\n|$))', items_text)
                        for item in item_lines:
                            product_name = item.strip()
                            if len(product_name) > 3 and not any(word in product_name.lower() for word in ['subtotal', 'discount', 'shipping', 'total']):
                                products.append({
                                    'name': product_name,
                                    'price': 0  # Unknown price
                                })
                        break
            
            # Pattern 3: Look for product mentions in general text
            if not products:
                # Common product keywords found in your responses
                product_keywords = [
                    'Apple Smart Phone', 'Memorex Router', 'Belkin Router',
                    'HP Wireless Fax', 'Office Star Executive Leather Armchair',
                    'Samsung Tablet', 'Dell Monitor', 'Logitech Mouse',
                    'Canon Printer', 'Brother Scanner'
                ]
                
                for keyword in product_keywords:
                    if keyword.lower() in section.lower():
                        products.append({
                            'name': keyword,
                            'price': 0
                        })
            
            # Pattern 4: Extract from bullet points or numbered lists
            if not products:
                bullet_items = re.findall(r'[•\-\*]\s*([^\.\n]+(?:Apple|Memorex|Belkin|HP|Office|Samsung|Dell|Logitech|Canon|Brother)[^\.\n]*)', section, re.IGNORECASE)
                for item in bullet_items:
                    product_name = item.strip()
                    if len(product_name) > 3:
                        products.append({
                            'name': product_name,
                            'price': 0
                        })
            
            if products:
                invoice_data['products'] = products
            
            # Only add invoice if we have meaningful data
            if any(key in invoice_data for key in ['invoice_number', 'customer', 'total_amount', 'products']):
                invoices.append(invoice_data)
        
        print(f"DEBUG: Extracted {len(invoices)} invoices with data")
        for i, inv in enumerate(invoices[:3]):  # Show first 3
            print(f"  Invoice {i+1}: {inv.get('customer', 'Unknown')} - {len(inv.get('products', []))} products")
            if inv.get('products'):
                for prod in inv.get('products', [])[:2]:  # Show first 2 products
                    print(f"    - {prod['name'][:50]}...")
        
        return invoices

    def extract_products_from_context(self, context: str) -> List[str]:
        """Direct extraction of product names from context - for when structured extraction fails"""
        products = []
    
        patterns = [
            # Bullet points with products
            r'[•\-\*]\s*([A-Z][^\.\n]+(?:Apple|Memorex|Belkin|HP|Office)[^\.\n]*)',
            # After "Items Ordered:" or similar
            r'Items Ordered[:\s]+(.*?)(?:\n\n|\$\s*[\d,]+\.?\d*)',
            # Product lines with prices
            r'([A-Z][^@]+?)\s*[@]\s*\$',
            # Common product patterns from your output
            r'(Apple Smart Phone[^,\n]*)',
            r'(Memorex Router[^,\n]*)',
            r'(Belkin Router[^,\n]*)',
            r'(HP Wireless Fax[^,\n]*)',
            r'(Office Star[^,\n]*)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, context, re.IGNORECASE | re.DOTALL)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                product_name = match.strip()
                if len(product_name) > 3 and product_name not in products:
                    products.append(product_name)
        
        if not products:
            lines = context.split('\n')
            for line in lines:
                line = line.strip()
                if (len(line) > 10 and 
                    not line.startswith('[') and 
                    not line.startswith('Invoice') and
                    not line.startswith('Customer') and
                    not line.startswith('Total') and
                    not line.startswith('Date') and
                    not line.startswith('💰') and
                    not line.startswith('📄') and
                    not line.startswith('👤') and
                    not line.startswith('🛒') and
                    'Apple' in line or 'Memorex' in line or 'Belkin' in line or 'HP' in line):
                    products.append(line)
        
        return list(set(products))  # Remove duplicates

    def analyze_trends(self, invoices: List[Dict]) -> Dict:
        """Analyze trends from invoice data"""
        analysis = {
            'total_invoices': len(invoices),
            'total_amount_usd': 0,
            'average_amount_usd': 0,
            'customer_count': 0,
            'product_analysis': defaultdict(int),
            'monthly_trends': defaultdict(float),
            'customer_analysis': defaultdict(float),
            'raw_products': []  # Store raw product names for debugging
        }
        
        if not invoices:
            return analysis
        
        amounts = []
        customers = set()
        
        for invoice in invoices:
            # Amount analysis
            amount = invoice.get('total_amount', 0)
            amounts.append(amount)
            analysis['total_amount_usd'] += amount
            
            # Customer analysis
            customer = invoice.get('customer', 'Unknown')
            customers.add(customer)
            analysis['customer_analysis'][customer] += amount
            
            # Product analysis - IMPROVED
            for product in invoice.get('products', []):
                product_name = product.get('name', 'Unknown').strip()
                analysis['raw_products'].append(product_name)  # Store for debugging
                
                # Clean up product name
                product_name = product_name.split('(')[0].split('-')[0].strip()
                
                # Group similar products
                if len(product_name) > 3:  # Filter out short/nonsense names
                    # Categorize by brand/product type
                    if 'apple' in product_name.lower() or 'iphone' in product_name.lower() or 'smart phone' in product_name.lower():
                        product_key = 'Apple Smart Phones'
                    elif 'memorex' in product_name.lower():
                        product_key = 'Memorex Routers'
                    elif 'belkin' in product_name.lower():
                        product_key = 'Belkin Routers'
                    elif 'hp' in product_name.lower() or 'fax' in product_name.lower():
                        product_key = 'HP Fax Machines'
                    elif 'office' in product_name.lower() or 'chair' in product_name.lower():
                        product_key = 'Office Furniture'
                    elif 'router' in product_name.lower():
                        product_key = 'Routers (Other)'
                    elif 'phone' in product_name.lower():
                        product_key = 'Phones (Other)'
                    else:
                        product_key = product_name[:50]  # Truncate long names
                    
                    analysis['product_analysis'][product_key] += 1
            
            # Monthly trends
            date_str = invoice.get('date', '')
            if date_str:
                try:
                    # Extract year-month
                    year_match = re.search(r'(\d{4})', date_str)
                    month_match = re.search(r'(\w+\s+\d{4}|\d{1,2}/\d{4})', date_str)
                    if year_match:
                        year = year_match.group(1)
                        if month_match:
                            month_key = month_match.group(1)
                        else:
                            month_key = f"Unknown/{year}"
                        analysis['monthly_trends'][month_key] += amount
                except:
                    pass
        
        if amounts:
            analysis['average_amount_usd'] = statistics.mean(amounts) if amounts else 0
            analysis['max_amount_usd'] = max(amounts) if amounts else 0
            analysis['min_amount_usd'] = min(amounts) if amounts else 0
        
        analysis['customer_count'] = len(customers)
        
        print(f"DEBUG: Analysis summary - {analysis['total_invoices']} invoices, {len(analysis['product_analysis'])} product types")
        print(f"DEBUG: Raw products found: {analysis['raw_products'][:5] if analysis['raw_products'] else 'None'}")
        
        return analysis

    def analyze_product_recommendations(self, analysis_data: Dict, question: str, context: str) -> str:
        """Generate product recommendations based on analysis - IMPROVED"""
        
        # First try structured analysis
        product_counts = analysis_data.get('product_analysis', {})
        raw_products = analysis_data.get('raw_products', [])
        
        # If no structured data, try direct extraction from context
        if not product_counts and not raw_products:
            print("DEBUG: No structured product data, extracting directly from context")
            direct_products = self.extract_products_from_context(context)
            if direct_products:
                for product in direct_products:
                    product_key = product[:50]
                    product_counts[product_key] = product_counts.get(product_key, 0) + 1
                raw_products = direct_products
        
        response = "## 📊 Product Analysis & Business Recommendations\n\n"
        
        if not product_counts and not raw_products:
            response += "**Insufficient product data to make specific recommendations.**\n\n"
            response += "*Note: The system found invoice data but could not extract specific product information.*\n\n"
            
            # Still provide general business advice
            response += "### General Business Recommendations:\n"
            response += "1. **Expand High-Demand Product Lines**: Focus on products with consistent sales\n"
            response += "2. **Diversify Product Portfolio**: Add complementary products to existing lines\n"
            response += "3. **Target High-Value Customers**: Identify customers with large or frequent purchases\n"
            response += "4. **Optimize International Shipping**: Streamline logistics for global customers\n"
            response += "5. **Implement Customer Loyalty Program**: Encourage repeat business\n"
            
            return response
        
        # We have product data - proceed with analysis
        response += "Based on the analysis of invoice data, here are my observations and recommendations:\n\n"
        
        # Show what products were found
        response += "### Products Identified in Invoices:\n"
        if raw_products:
            unique_products = list(set(raw_products))[:10]  # Show up to 10 unique products
            for product in unique_products:
                response += f"- **{product}**\n"
        elif product_counts:
            for product, count in list(product_counts.items())[:10]:
                response += f"- **{product}** (appears {count} time{'s' if count != 1 else ''})\n"
        
        # Sort products by frequency
        sorted_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_products:
            response += "\n### Top Performing Product Categories:\n"
            for product, count in sorted_products[:5]:
                percentage = (count / sum(product_counts.values())) * 100 if sum(product_counts.values()) > 0 else 0
                response += f"- **{product}**: {count} occurrences ({percentage:.1f}% of product mentions)\n"
        
        # Analyze product types for strategic recommendations
        tech_products = sum(count for product, count in product_counts.items() 
                          if any(keyword in product.lower() for keyword in ['apple', 'phone', 'router', 'fax', 'tablet', 'monitor']))
        furniture_products = sum(count for product, count in product_counts.items() 
                               if any(keyword in product.lower() for keyword in ['chair', 'furniture', 'desk', 'office']))
        
        response += "\n### Product Category Analysis:\n"
        total_mentions = sum(product_counts.values())
        if total_mentions > 0:
            response += f"- **Technology Products**: {tech_products} mentions ({(tech_products/total_mentions)*100:.1f}%)\n"
            response += f"- **Office Furniture**: {furniture_products} mentions ({(furniture_products/total_mentions)*100:.1f}%)\n"
            response += f"- **Other Products**: {total_mentions - tech_products - furniture_products} mentions\n"
        
        # Business recommendations
        response += "\n### Strategic Business Suggestions:\n"
        
        # Based on the products you mentioned in your output
        if any('apple' in str(product).lower() for product in product_counts.keys()):
            response += "1. **Expand Apple Product Line**: Consider adding more Apple accessories (cases, headphones, chargers)\n"
        
        if any('router' in str(product).lower() for product in product_counts.keys()):
            response += "2. **Bundle Networking Solutions**: Create packages with routers, extenders, and installation services\n"
        
        if any('fax' in str(product).lower() for product in product_counts.keys()):
            response += "3. **Modernize Communication Products**: Add VoIP systems and digital fax solutions\n"
        
        if any('chair' in str(product).lower() or 'furniture' in str(product).lower() for product in product_counts.keys()):
            response += "4. **Expand Ergonomic Office Solutions**: Add standing desks, monitor arms, and ergonomic accessories\n"
        
        # General recommendations
        response += "5. **Customer-Centric Product Development**: Analyze customer feedback for product improvements\n"
        response += "6. **Geographic Expansion Strategy**: Target regions where specific products are popular\n"
        response += "7. **Seasonal Product Planning**: Adjust inventory based on seasonal demand patterns\n"
        response += "8. **Competitive Pricing Analysis**: Regularly review pricing against competitors\n"
        
        # Add financial metrics if available
        if analysis_data.get('total_invoices', 0) > 0:
            response += f"\n### Supporting Data:\n"
            response += f"- **Invoices Analyzed**: {analysis_data.get('total_invoices', 0)}\n"
            response += f"- **Unique Customers**: {analysis_data.get('customer_count', 0)}\n"
            if analysis_data.get('total_amount_usd', 0) > 0:
                response += f"- **Total Revenue Analyzed**: ${analysis_data.get('total_amount_usd', 0):,.2f} USD\n"
        
        return response

    def analyze_financial_trends(self, analysis_data: Dict, question: str) -> str:
        """Generate financial trend analysis"""
        response = "## 📈 Financial Trends Analysis\n\n"
        
        response += f"**Invoices Analyzed:** {analysis_data.get('total_invoices', 0)}\n"
        response += f"**Total Revenue:** ${analysis_data.get('total_amount_usd', 0):,.2f} USD\n"
        response += f"**Average Invoice:** ${analysis_data.get('average_amount_usd', 0):,.2f} USD\n"
        response += f"**Unique Customers:** {analysis_data.get('customer_count', 0)}\n"
        
        if analysis_data.get('max_amount_usd'):
            response += f"**Highest Invoice:** ${analysis_data.get('max_amount_usd', 0):,.2f} USD\n"
            response += f"**Lowest Invoice:** ${analysis_data.get('min_amount_usd', 0):,.2f} USD\n"
        
        # Customer analysis
        customer_data = analysis_data.get('customer_analysis', {})
        if customer_data:
            response += "\n### Top Customers by Spending:\n"
            sorted_customers = sorted(customer_data.items(), key=lambda x: x[1], reverse=True)[:5]
            for customer, amount in sorted_customers:
                response += f"- **{customer}**: ${amount:,.2f} USD\n"
        
        # Monthly trends
        monthly_data = analysis_data.get('monthly_trends', {})
        if monthly_data and len(monthly_data) > 1:
            response += "\n### Monthly Revenue Trends:\n"
            sorted_months = sorted(monthly_data.items())
            for month, amount in sorted_months:
                response += f"- **{month}**: ${amount:,.2f} USD\n"
        
        # Product analysis
        product_data = analysis_data.get('product_analysis', {})
        if product_data:
            response += "\n### Product Categories Analysis:\n"
            sorted_products = sorted(product_data.items(), key=lambda x: x[1], reverse=True)[:5]
            for product, count in sorted_products:
                response += f"- **{product}**: {count} occurrence{'s' if count != 1 else ''}\n"
        
        return response

    def analyze_using_llm(self, question: str, context: str, analysis_type: str = "general") -> str:
        """Use LLM for complex analysis"""
        if analysis_type == "product_recommendation":
            prompt_template = """You are a financial analyst and business advisor. Analyze the following invoice data and provide specific, actionable product recommendations for business expansion.

CONTEXT DATA:
{context}

USER QUESTION: {question}

Based on the invoice data, provide:
1. Top performing products (with evidence from data)
2. Product categories showing growth potential
3. Specific recommendations for product expansion
4. Business strategies to increase revenue
5. Financial metrics to track

Focus on actionable insights backed by data from the invoices. If specific product data is limited, provide general business expansion strategies.

Format your response with clear sections and bullet points."""
        else:
            prompt_template = """You are a financial analyst. Analyze the following invoice data and provide insights based on the user's question.

CONTEXT DATA:
{context}

USER QUESTION: {question}

Provide a comprehensive financial analysis including:
1. Key financial metrics
2. Trends and patterns observed
3. Insights relevant to the question
4. Data-driven observations
5. Recommendations if appropriate

Format your response clearly with sections and bullet points."""

        prompt = PromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            response = chain.invoke({
                "context": context[:4000], 
                "question": question
            })
            return response
        except Exception as e:
            return f"Analysis generation failed: {str(e)}"

    def analyze(self, question: str, context: str) -> Tuple[str, Dict]:
        """Main analysis method - returns (analysis_text, data_summary)"""
        print(f"Financial Analysis Agent analyzing: '{question[:50]}...'")
        
        # Extract data from context
        invoices = self.extract_invoice_data(context)
        analysis_data = self.analyze_trends(invoices)
        
        print(f"DEBUG: Invoice extraction - Found {len(invoices)} invoices")
        print(f"DEBUG: Product analysis - {len(analysis_data.get('product_analysis', {}))} product types")
        
        # Determine analysis type based on question
        question_lower = question.lower()
        
        if any(keyword in question_lower for keyword in [
            'product', 'expand', 'recommend', 'suggest', 
            'business should', 'growth', 'opportunities',
            'focus on', 'which product', 'what product'
        ]):
            # Product/business recommendation analysis
            print("DEBUG: Using product recommendation analysis")
            analysis_text = self.analyze_product_recommendations(analysis_data, question, context)
            
            # Enhance with LLM if we have sufficient data
            if len(invoices) >= 2 or analysis_data.get('product_analysis'):
                try:
                    llm_analysis = self.analyze_using_llm(question, context, "product_recommendation")
                    if llm_analysis and not llm_analysis.startswith("Analysis generation failed"):
                        analysis_text += f"\n\n### 🤖 AI-Powered Strategic Insights:\n{llm_analysis}"
                except Exception as e:
                    print(f"DEBUG: LLM analysis failed: {e}")
        
        elif any(keyword in question_lower for keyword in ['trend', 'pattern', 'summary', 'overview', 'insight']):
            # General trend analysis
            print("DEBUG: Using financial trend analysis")
            analysis_text = self.analyze_financial_trends(analysis_data, question)
            
            # Enhance with LLM
            if len(invoices) >= 2:
                try:
                    llm_analysis = self.analyze_using_llm(question, context, "general")
                    if llm_analysis and not llm_analysis.startswith("Analysis generation failed"):
                        analysis_text += f"\n\n### 🤖 Additional Insights:\n{llm_analysis}"
                except Exception as e:
                    print(f"DEBUG: LLM analysis failed: {e}")
        
        else:
            # Generic analysis with LLM
            print("DEBUG: Using generic LLM analysis")
            analysis_text = self.analyze_using_llm(question, context, "general")
            if analysis_text.startswith("Analysis generation failed"):
                analysis_text = "##  Financial Analysis\n\nUnable to generate detailed analysis from the available data. Please try a more specific query or ensure there is sufficient invoice data in the context."
        
        return analysis_text, analysis_data

# Create singleton instance
financial_agent = FinancialAnalysisAgent()