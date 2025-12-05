import streamlit as st
from rag_system import query_rag, get_retriever_info

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
    page_title="RAG system - Invot",
    page_icon="📄",
    layout="wide"
)

st.title("📄 RAG system - Invot")
st.divider()

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    if st.button("🔓 Logout", type="primary", use_container_width=True):
        st.session_state["authenticated"] = False
        st.success("🔒 Sesión cerrada")
        st.rerun()
    
    retriever_info = get_retriever_info()
    
    st.markdown("**🔍 Retriever:**")
    st.info(f"Tipo: {retriever_info['tipo']}")
    
    st.markdown("**🤖 Models:**")
    st.info("Queries: GPT-4o-mini\nResponses: GPT-4o")
    
    st.markdown("**💱 Currency:**")
    st.info("Auto-conversion to USD enabled")
    
    st.markdown("**📁 Repository:**")
    st.info("🔗 [Open repository in GitHub](https://github.com/luisruro/rag_agent.git)")
    
    st.divider()
    
    if st.button("🗑️ Clean Chat", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### 💬 Chat")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

with col2:
    st.markdown("### 📄 Relevant Documents")
    
    if st.session_state.messages:
        last_message = st.session_state.messages[-1]
        if last_message["role"] == "assistant" and "docs" in last_message:
            docs = last_message["docs"]
            currency_conversions = last_message.get("currency_conversions", [])
            
            if currency_conversions:
                st.markdown("#### 💱 Currency Conversions")
                for conv in currency_conversions:
                    st.info(
                        f"**{conv['original_amount']} {conv['original_currency']}** "
                        f"= **{conv['converted_amount']} USD** "
                        f"(rate: {conv['rate']})"
                    )
                st.divider()
            
            if docs:
                for doc in docs:
                    with st.expander(f"📄 Fragment {doc['fragment']}", expanded=False):
                        st.markdown(f"**Source:** {doc['source']}")
                        st.markdown(f"**Page:** {doc['page']}")
                        st.markdown("**Content:**")
                        st.text(doc['content'])

if prompt := st.chat_input("Type your request..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.spinner("🔍 analyzing data..."):
        response, docs, currency_conversions = query_rag(prompt)
        
        # 1. Deduplication: Use the converted amount for a robust key.
        unique_conversions = {}
        for conv in currency_conversions:
            # Normalize the converted amount for comparison to avoid floating point issues
            # We use the converted amount (which is normalized to float) and the original currency.
            try:
                converted_amount_str = f"{float(conv['converted_amount']):.2f}"
            except ValueError:
                converted_amount_str = conv['converted_amount']

            key = f"{converted_amount_str}_{conv['original_currency']}"
            
            # Store the conversion using the robust key
            unique_conversions[key] = conv
        
        deduped_conversions = list(unique_conversions.values())

        # 2. Filtering: Remove self-conversions (e.g., 525.69 USD = 525.69 USD)
        # This checks if the original currency is USD AND the amounts are identical (rate=1.0)
        filtered_conversions = [
            conv for conv in deduped_conversions 
            if conv.get('original_currency') != 'USD' or 
               (conv.get('converted_amount') != conv.get('original_amount'))
        ]
        
        st.session_state.messages.append({
            "role": "assistant", 
            "content": response, 
            "docs": docs,
            "currency_conversions": filtered_conversions
        })
    
    st.rerun()

st.divider()
st.markdown(
    "<div style='text-align: center; color: #666;'>📈 Invoice assistant with MMR Retriever & Currency Conversion</div>", 
    unsafe_allow_html=True
)