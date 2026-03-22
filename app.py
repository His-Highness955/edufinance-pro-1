import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="EduFinance Premium", layout="wide", page_icon="🏦")

# --- FIREBASE CLOUD INITIALIZATION ---
if not firebase_admin._apps:
    try:
        # Priority 1: Streamlit Cloud Secrets
        if "firebase_json" in st.secrets:
            info = json.loads(st.secrets["firebase_json"])
            cred = credentials.Certificate(info)
        # Priority 2: Local JSON file for testing
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            key_path = os.path.join(current_dir, "serviceAccountKey.json")
            cred = credentials.Certificate(key_path)
            
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        st.sidebar.success("☁️ Google Cloud Active")
    except Exception as e:
        st.sidebar.error("⚠️ Connection Offline")
        db = None
else:
    db = firestore.client()

# --- STABILIZED CLOUD ENGINE ---
def get_all_data(collection_name):
    """Fetches data using .get() instead of .stream() to prevent gRPC hangs."""
    if db is None: return pd.DataFrame()
    try:
        # We fetch the snapshot once to avoid the 'iterator' error you saw
        docs = db.collection(collection_name).get(timeout=10)
        data = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            data.append(item)
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.sidebar.warning(f"📡 Sync Delay: {e}")
        return pd.DataFrame()

def save_to_cloud(collection_name, data):
    """Saves data and clears cache to force an immediate update."""
    if db is not None:
        try:
            db.collection(collection_name).add(data)
            st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"Save Failed: {e}")
    return False

# --- MODERN STYLING ---
st.markdown("""
    <style>
    .main { background: #f8f9fa; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #1f77b4; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3em; background: #1f77b4; color: white; border: none; }
    .stButton>button:hover { background: #145a8d; }
    [data-testid="stSidebar"] { background-color: #0e1117; }
    </style>
    """, unsafe_allow_html=True)

ALL_CLASSES = ["Kg 1", "Kg 2", "Nur 1", "Nur 2", "Pry 1", "Pry 2", "Pry 3", "Pry 4", "Pry 5", "JSS 1", "JSS 2", "JSS 3", "SSS 1", "SSS 2", "SSS 3"]

# --- SIDEBAR ---
st.sidebar.title("EduFinance Pro")
menu = ["📊 Executive Dashboard", "👤 Student Registry", "💸 Post Payment", "📜 Debt Ledger"]
choice = st.sidebar.radio("Main Menu", menu)

# --- 1. EXECUTIVE DASHBOARD ---
if choice == "📊 Executive Dashboard":
    st.title("🏦 Financial Intelligence")
    s_df = get_all_data("students")
    p_df = get_all_data("payments")

    if not s_df.empty:
        total_expected = s_df['total_fees'].sum()
        total_collected = p_df['amount'].sum() if not p_df.empty else 0
        total_debt = total_expected - total_collected

        m1, m2, m3 = st.columns(3)
        m1.metric("Revenue Target", f"₦{total_expected:,.2f}")
        m2.metric("Actual Income", f"₦{total_collected:,.2f}")
        m3.metric("Outstanding", f"₦{total_debt:,.2f}", delta_color="inverse")
    else:
        st.info("No records found in the Cloud. Please go to the Registry to add students.")

# --- 2. STUDENT REGISTRY ---
elif choice == "👤 Student Registry":
    st.subheader("👥 Student Records")
    tab1, tab2 = st.tabs(["Add New Student", "View All Students"])

    with tab1:
        with st.form("reg_form", clear_on_submit=True):
            name = st.text_input("Student Full Name")
            s_class = st.selectbox("Assign Class", ALL_CLASSES)
            fees = st.number_input("Termly Tuition (₦)", min_value=0.0, step=500.0)
            if st.form_submit_button("Register to Cloud"):
                if name:
                    if save_to_cloud("students", {"name": name, "class": s_class, "total_fees": fees}):
                        st.success(f"Registered {name}!")
                        st.rerun()
                else: st.error("Name is required.")

    with tab2:
        view_df = get_all_data("students")
        if not view_df.empty:
            st.dataframe(view_df[['name', 'class', 'total_fees']], use_container_width=True)
        else: st.write("No students registered.")

# --- 3. POST PAYMENT ---
elif choice == "💸 Post Payment":
    st.subheader("💰 Record Payment")
    s_df = get_all_data("students")
    
    if not s_df.empty:
        names = s_df['name'].tolist()
        selected_student = st.selectbox("Select Student", names)
        sid = s_df[s_df['name'] == selected_student]['id'].values[0]
        
        amount = st.number_input("Amount Paid (₦)", min_value=0.0)
        p_date = st.date_input("Date", datetime.now())

        if st.button("Confirm Payment"):
            p_data = {"student_name": selected_student, "student_id": sid, "amount": amount, "date": str(p_date)}
            if save_to_cloud("payments", p_data):
                st.balloons()
                st.success("Payment Saved!")
                st.rerun()
    else: st.warning("Register students first.")

# --- 4. DEBT LEDGER ---
elif choice == "📜 Debt Ledger":
    st.subheader("📑 Outstanding Balances")
    s_df = get_all_data("students")
    p_df = get_all_data("payments")

    if not s_df.empty:
        report = []
        for _, s in s_df.iterrows():
            paid = p_df[p_df['student_id'] == s['id']]['amount'].sum() if not p_df.empty else 0
            balance = s['total_fees'] - paid
            report.append({"Student": s['name'], "Class": s['class'], "Fee": s['total_fees'], "Paid": paid, "Balance": balance})
        
        final_df = pd.DataFrame(report)
        if st.checkbox("Show Only Debtors", value=True):
            final_df = final_df[final_df['Balance'] > 0]
        
        st.table(final_df.style.format({"Fee": "₦{:,.2f}", "Paid": "₦{:,.2f}", "Balance": "₦{:,.2f}"}))
        st.download_button("📥 Download Report", final_df.to_csv(index=False), "debtors.csv")
