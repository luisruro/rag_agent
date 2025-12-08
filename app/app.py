# app.py
import streamlit as st
from rag_system import query_rag_graph, get_retriever_info

def login():
    if st.session_state.get("authenticated"):
        return True

    user = st.text_input("User")
    password = st.text_input("Password", type="password")

    USER = "admin"
    PASS = "1234"

    if st.button("Login"):
        if user == USER and password == PASS:
            st.session_state["authenticated"] = True
            st.success("🔓 Login success!")
            st.rerun()
        else:
            st.error("❌ User or password incorrect")

    return False

if not login():
    st.stop()

st.set_page_config(
    page_title="RAG System - Invot (LangGraph)",
    page_icon="📄",
    layout="wide"
)

st.title("📄 RAG System - Invot 🔗 LangGraph")
st.divider()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar
with st.sidebar:
    st.header("📋 System Information")
    
    # logout button
    if st.button("🔓 Logout", type="primary", use_container_width=True):
        st.session_state["authenticated"] = False
        st.success("🔒 Sesión cerrada")
        st.rerun()
    
    # retriever information
    retriever_info = get_retriever_info()
    
    st.markdown("**🔗 Architecture:**")
    st.info("LangGraph Multi-Node RAG\n+ Pydantic Structured Extraction\n+ Financial Analysis Agent")
    
    st.markdown("**🔍 Retriever:**")
    st.info(f"Type: {retriever_info['tipo']}\nDocuments: {retriever_info['documentos']}\nDiversity: {retriever_info['diversidad']}")
    
    st.markdown("**🤖 Models:**")
    st.info("Queries: GPT-4o-mini\nResponses: GPT-4o\nAnalysis: GPT-4o-mini")
    
    # Show agent info if available
    if "agents" in retriever_info:
        st.markdown("**🤝 Agents:**")
        agents_text = ""
        for agent_name, agent_desc in retriever_info["agents"].items():
            agents_text += f"• {agent_name}: {agent_desc}\n"
        st.info(agents_text)
    
    st.markdown("**📁 Repository:**")
    st.info("🔗 [Open repository in GitHub](https://github.com/luisruro/rag_agent.git)")
    
    st.divider()
    
    if st.button("🗑️ Clean Chat", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# Main layout with columns
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### 💬 Chat")
    
    # Show message history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Show if this was a financial analysis
            if message.get("is_financial_analysis"):
                st.success("📊 *Financial Analysis Generated*")

with col2:
    st.markdown("### 📄 Relevant Documents")
    
    # Show documents from the last query
    if st.session_state.messages:
        last_message = st.session_state.messages[-1]
        if last_message["role"] == "assistant":
            
            # Show financial analysis summary if available
            if "financial_data_summary" in last_message and last_message["financial_data_summary"]:
                st.markdown("#### 📈 Analysis Summary")
                summary = last_message["financial_data_summary"]
                st.info(
                    f"**Invoices Analyzed:** {summary.get('total_invoices', 0)}\n\n"
                    f"**Total Amount:** ${summary.get('total_amount_usd', 0):,.2f} USD\n\n"
                    f"**Average Invoice:** ${summary.get('average_amount_usd', 0):,.2f} USD\n\n"
                    f"**Unique Customers:** {summary.get('customer_count', 0)}"
                )
                st.divider()
            
            # Show currency conversions if available
            if "conversions" in last_message and last_message["conversions"]:
                st.markdown("#### 💱 Currency Conversions")
                conversions = last_message["conversions"]
                
                for conv in conversions:
                    st.info(
                        f"**{conv['original_amount']} {conv['original_currency']}** "
                        f"→ **{conv['converted_amount']} {conv['target_currency']}** "
                        f"(rate: {conv['rate']})"
                    )
                
                st.divider()
            
            # Show documents
            if "docs" in last_message:
                docs = last_message["docs"]
                
                if docs:
                    for doc in docs:
                        with st.expander(f"📄 Fragment {doc['fragment']}", expanded=False):
                            st.markdown(f"**Source:** {doc['source']}")
                            st.markdown(f"**Page:** {doc['page']}")
                            st.markdown("**Content:**")
                            st.text(doc['content'])

# User input
if prompt := st.chat_input("Type your request..."):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Generate response using LangGraph with currency conversion
    with st.spinner("🔗 Processing with LangGraph + Multi-Agent System..."):
        response, docs, conversions, financial_analysis = query_rag_graph(prompt)
        
        # Check if this was a financial analysis query
        is_financial_analysis = any(word in prompt.lower() for word in 
                                   ['analyze', 'analysis', 'trend', 'pattern', 'insight', 
                                    'summary', 'compare', 'statistic', 'report'])
        
        message_data = {
            "role": "assistant", 
            "content": response, 
            "docs": docs,
            "conversions": conversions,
            "is_financial_analysis": is_financial_analysis
        }
        
        # Add financial analysis data if available
        if financial_analysis:
            message_data["financial_analysis"] = financial_analysis
            # Extract summary data from analysis if possible
            if "total invoices" in response.lower() or "total amount" in response.lower():
                message_data["financial_data_summary"] = {
                    "note": "Financial analysis performed",
                    "analysis_available": True
                }
        
        st.session_state.messages.append(message_data)
    
    # Reload to show new messages
    st.rerun()

# Footer
st.divider()
st.markdown(
    "<div style='text-align: center; color: #666;'> LangGraph RAG + Pydantic Extraction + Financial Analysis Agent + Currency Conversion</div>", 
    unsafe_allow_html=True
)