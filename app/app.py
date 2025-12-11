# app.py
import streamlit as st
from rag_system import query_rag_graph, get_retriever_info
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
import json
import datetime

load_dotenv()

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
            st.success(" Login success!")
            st.rerun()
        else:
            st.error(" User or password incorrect")

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

# Initialize email draft state
if "email_draft" not in st.session_state:
    st.session_state.email_draft = None
if "email_recipient" not in st.session_state:
    st.session_state.email_recipient = None
if "email_subject" not in st.session_state:
    st.session_state.email_subject = None
if "email_body" not in st.session_state:
    st.session_state.email_body = None
if "awaiting_email_confirmation" not in st.session_state:
    st.session_state.awaiting_email_confirmation = False
if "button_counter" not in st.session_state:
    st.session_state.button_counter = 0

def log_email_send(recipient, subject, status, error=None):
    """Log email sending attempts"""
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "recipient": recipient,
        "subject": subject,
        "status": status,
        "error": error
    }
    
    try:
        with open("email_send_log.json", "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        print(f"📝 Email log saved: {status} to {recipient}")
    except Exception as e:
        print(f"⚠️ Failed to save email log: {e}")

def send_email(recipient_email, subject, body):
    """Send email using SMTP with actual sending capability"""
    try:
        # Get email configuration from environment variables
        SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
        SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", 587))
        SENDER_EMAIL = os.getenv("EMAIL_FROM", "colombiastorecommerce@gmail.com")
        SENDER_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
        SENDER_NAME = os.getenv("EMAIL_SENDER_NAME", "Invoice Assistant")
        USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
        
        # Validate configuration
        if not SENDER_PASSWORD:
            log_email_send(recipient_email, subject, "FAILED", "Email password not configured")
            return False, " Email password not configured. Please check your .env file."
        
        if not recipient_email:
            log_email_send("Unknown", subject, "FAILED", "Recipient email required")
            return False, " Recipient email address is required."
        
        # Create the email message
        msg = MIMEMultipart()
        msg['From'] = f'{SENDER_NAME} <{SENDER_EMAIL}>'
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Attach the email body
        msg.attach(MIMEText(body, 'plain'))
        
        # Send the email
        if USE_TLS:
            # Use TLS (more secure)
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()  # Upgrade to secure connection
        else:
            # Use SSL (for port 465)
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        
        # Login and send
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        # Log the successful send
        print(f"✅ Email successfully sent to {recipient_email}")
        log_email_send(recipient_email, subject, "SUCCESS")
        
        return True, f"✅ Email successfully sent to {recipient_email}"
        
    except smtplib.SMTPAuthenticationError as e:
        error_msg = "❌ Email authentication failed. Please check your email and password."
        print(f"{error_msg}: {e}")
        log_email_send(recipient_email, subject, "FAILED", "Authentication error")
        return False, error_msg
    except smtplib.SMTPException as e:
        error_msg = f"❌ SMTP error occurred: {str(e)}"
        print(error_msg)
        log_email_send(recipient_email, subject, "FAILED", str(e))
        return False, error_msg
    except Exception as e:
        error_msg = f"❌ Failed to send email: {str(e)}"
        print(error_msg)
        log_email_send(recipient_email, subject, "FAILED", str(e))
        return False, error_msg

# Sidebar
with st.sidebar:
    st.header("📋 System Information")
    
    # logout button
    if st.button("🔓 Logout", type="primary", use_container_width=True, key="logout_btn"):
        st.session_state["authenticated"] = False
        st.session_state.messages = []
        st.session_state.email_draft = None
        st.session_state.awaiting_email_confirmation = False
        st.success("🔒 Sesión cerrada")
        st.rerun()
    
    # retriever information
    retriever_info = get_retriever_info()
    
    st.markdown("**🔗 Architecture:**")
    st.info("LangGraph Multi-Node RAG\n+ Pydantic Structured Extraction\n+ Financial Analysis Agent\n+ Email Generation")
    
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
    
    # Email status section
    st.divider()
    st.markdown("### 📧 Email Status")
    
    # Check if email logs exist
    try:
        if os.path.exists("email_send_log.json"):
            with open("email_send_log.json", "r") as f:
                lines = f.readlines()
                if lines:
                    last_log = json.loads(lines[-1])
                    if last_log["status"] == "SUCCESS":
                        st.success(f"✅ Last email sent: {last_log['timestamp'][:16]}")
                    else:
                        st.error(f"❌ Last email failed: {last_log['error']}")
    except:
        pass
    
    # Email section in sidebar
    if st.session_state.email_draft:
        st.markdown("### 📧 Email Ready to Send")
        st.info(f"**To:** {st.session_state.email_recipient}")
        st.info(f"**Subject:** {st.session_state.email_subject}")
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("📤 Send", type="primary", use_container_width=True, key="sidebar_send"):
                success, message = send_email(
                    st.session_state.email_recipient,
                    st.session_state.email_subject,
                    st.session_state.email_body
                )
                if success:
                    st.success("✅ " + message)
                    # Add email sent message to chat
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"✅ Email sent to {st.session_state.email_recipient} with subject: '{st.session_state.email_subject}'"
                    })
                    # Clear email draft
                    st.session_state.email_draft = None
                    st.session_state.email_recipient = None
                    st.session_state.email_subject = None
                    st.session_state.email_body = None
                    st.rerun()
                else:
                    st.error("❌ " + message)
        with col_s2:
            if st.button("🗑️ Discard", type="secondary", use_container_width=True, key="sidebar_discard"):
                st.session_state.email_draft = None
                st.session_state.email_recipient = None
                st.session_state.email_subject = None
                st.session_state.email_body = None
                st.rerun()
    
    st.divider()
    
    if st.button("🗑️ Clean Chat", type="secondary", use_container_width=True, key="clean_chat"):
        st.session_state.messages = []
        st.session_state.email_draft = None
        st.session_state.awaiting_email_confirmation = False
        st.rerun()

# Main layout with columns
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### 💬 Chat")
    
    # Show message history
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Show if this was a financial analysis
            if message.get("is_financial_analysis"):
                st.success("📊 *Financial Analysis Generated*")
            
            # Show if this was an email draft
            if message.get("is_email_draft"):
                # Check email status
                if message.get("email_sent"):
                    st.success(f"✅ **Email Sent** to {message.get('email_recipient', 'customer')}")
                elif message.get("email_discarded"):
                    st.info("🗑️ **Email Discarded**")
                else:
                    st.info("📧 *Email draft generated*")
                
                # Check if message contains email preview and extract confirmation prompt
                if "Would you like to send this email?" in message["content"] and not message.get("email_action_taken"):
                    # Extract email details
                    lines = message["content"].split('\n')
                    recipient = "Unknown"
                    recipient_email = "colombiastorecommerce@gmail.com"
                    subject = "No Subject"
                    email_body = ""
                    
                    # Parse email details from the message
                    for line in lines:
                        if "**To:**" in line:
                            # Extract both name and email
                            recipient_info = line.replace("**To:**", "").strip()
                            # Extract email from parentheses
                            email_match = re.search(r'\(([^)]+@[^)]+)\)', recipient_info)
                            if email_match:
                                recipient_email = email_match.group(1)
                            recipient = recipient_info
                        elif "**Subject:**" in line:
                            subject = line.replace("**Subject:**", "").strip()
                    
                    # Extract email body
                    start_extracting = False
                    for line in lines:
                        if line.strip() and not line.startswith("**") and not line.startswith("*Would you like"):
                            if "Subject:" in line or start_extracting:
                                start_extracting = True
                                if not line.startswith("Subject:"):
                                    email_body += line + "\n"
                    
                    # Create action buttons
                    col_a, col_b = st.columns(2)
                    with col_a:
                        send_key = f"send_{idx}_{st.session_state.button_counter}"
                        if st.button("📤 Send Now", key=send_key, type="primary"):
                            st.session_state.button_counter += 1
                            
                            # Actually send the email
                            with st.spinner(f"Sending email to {recipient_email}..."):
                                success, result_msg = send_email(
                                    recipient_email=recipient_email,
                                    subject=subject,
                                    body=email_body.strip()
                                )
                            
                            # Update message status
                            st.session_state.messages[idx]["email_sent"] = success
                            st.session_state.messages[idx]["email_action_taken"] = True
                            st.session_state.messages[idx]["email_recipient"] = recipient_email
                            
                            # Add result message
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": result_msg
                            })
                            
                            st.rerun()
                    
                    with col_b:
                        discard_key = f"discard_{idx}_{st.session_state.button_counter}"
                        if st.button("🗑️ Discard", key=discard_key, type="secondary"):
                            st.session_state.button_counter += 1
                            st.session_state.messages[idx]["email_discarded"] = True
                            st.session_state.messages[idx]["email_action_taken"] = True
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": "🗑️ Email draft discarded"
                            })
                            st.rerun()

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
                if isinstance(summary, dict):
                    info_text = ""
                    if summary.get('total_invoices'):
                        info_text += f"**Invoices Analyzed:** {summary.get('total_invoices')}\n\n"
                    if summary.get('total_amount_usd'):
                        info_text += f"**Total Amount:** ${summary.get('total_amount_usd'):,.2f} USD\n\n"
                    if summary.get('average_amount_usd'):
                        info_text += f"**Average Invoice:** ${summary.get('average_amount_usd'):,.2f} USD\n\n"
                    if summary.get('customer_count'):
                        info_text += f"**Unique Customers:** {summary.get('customer_count')}"
                    
                    if info_text:
                        st.info(info_text)
                        st.divider()
            
            # Show currency conversions if available
            if "conversions" in last_message and last_message["conversions"]:
                st.markdown("#### 💱 Currency Conversions")
                conversions = last_message["conversions"]
                
                for conv in conversions:
                    st.info(
                        f"**{conv.get('original_amount', 'N/A')} {conv.get('original_currency', 'USD')}** "
                        f"→ **{conv.get('converted_amount', 'N/A')} {conv.get('target_currency', 'USD')}** "
                        f"(rate: {conv.get('rate', 'N/A')})"
                    )
                
                st.divider()
            
            # Show documents
            if "docs" in last_message:
                docs = last_message["docs"]
                
                if docs:
                    for doc in docs:
                        with st.expander(f"📄 Fragment {doc.get('fragment', 'N/A')}", expanded=False):
                            st.markdown(f"**Source:** {doc.get('source', 'Not specified')}")
                            st.markdown(f"**Page:** {doc.get('page', 'Not specified')}")
                            st.markdown("**Content:**")
                            st.text(doc.get('content', 'No content'))

# User input
if prompt := st.chat_input("Type your request..."):
    # Check if we're awaiting email confirmation
    if st.session_state.awaiting_email_confirmation:
        if prompt.lower() in ['yes', 'y', 'send']:
            # Send the email
            if st.session_state.email_draft:
                success, message = send_email(
                    st.session_state.email_recipient,
                    st.session_state.email_subject,
                    st.session_state.email_body
                )
                if success:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"✅ Email sent to {st.session_state.email_recipient}"
                    })
                else:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"❌ {message}"
                    })
            else:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "❌ No email draft available to send"
                })
        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": "🗑️ Email discarded"
            })
        
        # Reset email state
        st.session_state.awaiting_email_confirmation = False
        st.session_state.email_draft = None
        st.session_state.email_recipient = None
        st.session_state.email_subject = None
        st.session_state.email_body = None
        
        st.rerun()
    
    # Normal query processing
    else:
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Generate response using LangGraph with all features
        with st.spinner("🔗 Processing with LangGraph + Multi-Agent System..."):
            response, docs, conversions, financial_analysis = query_rag_graph(prompt)
            
            # Check query type
            is_financial_analysis = any(word in prompt.lower() for word in 
                                      ['analyze', 'analysis', 'trend', 'pattern', 'insight', 
                                       'summary', 'compare', 'statistic', 'report', 'recommend'])
            
            is_email_request = any(word in prompt.lower() for word in 
                                 ['email', 'send email', 'write email', 'compose email', 'draft email'])
            
            message_data = {
                "role": "assistant", 
                "content": response, 
                "docs": docs,
                "conversions": conversions,
                "is_financial_analysis": is_financial_analysis,
                "is_email_draft": is_email_request
            }
            
            # Add financial analysis data if available
            if financial_analysis and financial_analysis != "Financial analysis agent not available":
                message_data["financial_analysis"] = financial_analysis
            
            # Check if response contains email draft
            if "📧 Email Prepared:" in response or "Email Prepared:" in response:
                # Try to extract email details from response
                lines = response.split('\n')
                recipient_email = None
                subject = None
                email_body_start = None
                
                for i, line in enumerate(lines):
                    if "**To:**" in line:
                        # Extract email from line like "**To:** Name (email@example.com)"
                        match = re.search(r'\(([^)]+@[^)]+)\)', line)
                        if match:
                            recipient_email = match.group(1)
                    if "**Subject:**" in line:
                        subject = line.replace("**Subject:**", "").strip()
                    if line.strip() and not line.startswith("**") and email_body_start is None:
                        # Find start of email content
                        for j in range(i, len(lines)):
                            if lines[j].strip() and not lines[j].startswith("*Would you like"):
                                email_body_start = j
                                break
                
                # Store email draft in session state
                if email_body_start is not None:
                    email_body = '\n'.join(lines[email_body_start:])
                    # Remove the confirmation prompt at the end
                    if "*Would you like to send this email?" in email_body:
                        email_body = email_body.split("*Would you like to send this email?")[0].strip()
                    
                    st.session_state.email_draft = response
                    st.session_state.email_recipient = recipient_email or "colombiastorecommerce@gmail.com"
                    st.session_state.email_subject = subject or "Invoice Information"
                    st.session_state.email_body = email_body
            
            st.session_state.messages.append(message_data)
        
        st.rerun()

# Footer
st.divider()
st.markdown(
    "<div style='text-align: center; color: #666;'> LangGraph RAG + Pydantic Extraction + Financial Analysis Agent + Currency Conversion + Email Generation</div>", 
    unsafe_allow_html=True
)