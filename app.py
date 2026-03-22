import streamlit as st
import pandas as pd
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="EduFinance Premium", layout="wide", page_icon="🏦")

# --- FIREBASE INITIALIZATION ---
if not firebase_admin._apps:
    try:
        if "firebase_json" in st.secrets:
            info = json.loads(st.secrets["firebase_json"])
            cred = credentials.Certificate(info)
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            key_path = os.path.join(current_dir, "serviceAccountKey.json")
            cred = credentials.Certificate(key_path)
            
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        st.sidebar.success("☁️ Cloud Database Connected")
    except Exception as e:
        st.sidebar.error(f"⚠️ Connection Failed: {e}")
        db = None
else:
    db = firestore.client()

# --- CLOUD DATA ENGINE (Replaces SQLite) ---
def get_cloud_data(collection):
    """Fetches all documents from a Firebase collection."""
    if db is None: return pd.DataFrame()
    try:
        docs = db.collection(collection).get()
        data = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            data.append(item)
        return pd.DataFrame(data) if data else pd.DataFrame()
    except:
        return pd.DataFrame()

def save_to_cloud(collection, data):
    """Saves data directly to Google Cloud."""
    if db is not None:
        db.collection(collection).add(data)
        st.cache_data.clear()
        return True
    return False

# --- MODERN STYLING ---
st.markdown("""
    <style>
    .main { background: #f0f2f6; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #1f77b4; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 20px; background: #1f77b4; color: white; border: none; }
    [data-testid="stSidebar"] { background-color: #0e1117; color: white; }
    </style>
    """, unsafe_allow_html=True)

ALL_CLASSES = ["Kg 1", "Kg 1b", "Kg 2", "Nur 1", "Nur 2", "Pry 1", "Pry 2", "Pry 3", "Pry 4", "Pry 5", "JSS 1", "JSS 2", "JSS 3", "SSS 1", "SSS 2", "SSS 3"]

# --- SIDEBAR ---
st.sidebar.title("EduFinance Pro")
menu = ["📊 Dashboard", "👤 Registry", "💸 Payments", "📜 Debt Ledger"]
choice = st.sidebar.radio("Main Menu", menu)

# --- 1. DASHBOARD ---
if choice == "📊 Dashboard":
    st.title("🏦 Financial Dashboard")
    s_df = get_cloud_data("students")
    p_df = get_cloud_data("payments")

    if not s_df.empty:
        total_exp = s_df['total_fees'].sum()
        total_col = p_df['amount'].sum() if not p_df.empty else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Revenue Target", f"₦{total_exp:,.2f}")
        m2.metric("Actual Income", f"₦{total_col:,.2f}")
        m3.metric("Outstanding", f"₦{(total_exp - total_col):,.2f}", delta_color="inverse")
    else:
        st.info("No students found in the cloud.")

# --- 2. REGISTRY ---
elif choice == "👤 Registry":
    st.subheader("👥 Student Registry")
    tab1, tab2 = st.tabs(["Add Student", "View All"])
    
    with tab1:
        with st.form("reg", clear_on_submit=True):
            name = st.text_input("Full Name")
            s_class = st.selectbox("Class", ALL_CLASSES)
            fees = st.number_input("Tuition (₦)", min_value=0.0)
            if st.form_submit_button("Save to Cloud"):
                if name:
                    if save_to_cloud("students", {"name": name, "class": s_class, "total_fees": fees}):
                        st.success(f"Registered {name}!")
                        st.rerun()
                else: st.error("Name required")

    with tab2:
        st.dataframe(get_cloud_data("students"), use_container_width=True)

# --- 3. PAYMENTS ---
elif choice == "💸 Payments":
    st.subheader("💰 Record Payment")
    s_df = get_cloud_data("students")
    if not s_df.empty:
        selected = st.selectbox("Select Student", s_df['name'].tolist())
        sid = s_df[s_df['name'] == selected]['id'].values[0]
        amt = st.number_input("Amount (₦)", min_value=0.0)
        dt = st.date_input("Date", datetime.now())
        
        if st.button("Confirm Payment"):
            p_data = {"student_id": sid, "name": selected, "amount": amt, "date": str(dt)}
            if save_to_cloud("payments", p_data):
                st.balloons()
                st.success("Payment Saved!")
                st.rerun()
    else: st.warning("Register students first.")

# --- 4. DEBT LEDGER ---
elif choice == "📜 Debt Ledger":
    st.subheader("📜 Debt Report")
    s_df = get_cloud_data("students")
    p_df = get_cloud_data("payments")

    if not s_df.empty:
        report = []
        for _, s in s_df.iterrows():
            paid = p_df[p_df['student_id'] == s['id']]['amount'].sum() if not p_df.empty else 0
            last_date = p_df[p_df['student_id'] == s['id']]['date'].max() if not p_df.empty else "No Payments"
            report.append({
                "Student": s['name'], "Class": s['class'], 
                "Fee": s['total_fees'], "Paid": paid, 
                "Balance": s['total_fees'] - paid,
                "Last Payment": last_date
            })
        
        final_df = pd.DataFrame(report)
        st.dataframe(final_df.style.format({"Fee": "₦{:,.2f}", "Paid": "₦{:,.2f}", "Balance": "₦{:,.2f}"}))
