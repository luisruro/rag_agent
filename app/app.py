import streamlit as st
from rag_system import query_rag_graph, get_retriever_info

# --- LOGIN SYSTEM ---
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

# Not authenticated, stop the app
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
    st.info("LangGraph Multi-Node RAG\n+ Pydantic Structured Extraction")
    
    st.markdown("**🔍 Retriever:**")
    st.info(f"Type: {retriever_info['tipo']}\nDocuments: {retriever_info['documentos']}\nDiversity: {retriever_info['diversidad']}")
    
    st.markdown("**🤖 Models:**")
    st.info("Queries: GPT-4o-mini\nResponses: GPT-4o")
    
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

with col2:
    st.markdown("### 📄 Relevant Documents")
    
    # Show documents from the last query
    if st.session_state.messages:
        last_message = st.session_state.messages[-1]
        if last_message["role"] == "assistant":
            
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
    with st.spinner("🔗 Processing with LangGraph + Currency Conversion..."):
        response, docs, conversions = query_rag_graph(prompt)
        st.session_state.messages.append({
            "role": "assistant", 
            "content": response, 
            "docs": docs,
            "conversions": conversions
        })
    
    # Reload to show new messages
    st.rerun()

# Footer
st.divider()
st.markdown(
    "<div style='text-align: center; color: #666;'>🔗 LangGraph RAG + 📊 Pydantic Extraction + 💱 Currency Conversion</div>", 
    unsafe_allow_html=True
)