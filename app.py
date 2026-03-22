import streamlit as st
import pandas as pd
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import json

# --- PAGE CONFIG ---
st.set_page_config(page_title="EduFinance Pro", layout="wide", page_icon="🏦")

# --- FIREBASE SETUP ---
if not firebase_admin._apps:
    try:
        # This looks for the 'firebase_json' you will paste into Streamlit Secrets
        if "firebase_json" in st.secrets:
            info = json.loads(st.secrets["firebase_json"])
            cred = credentials.Certificate(info)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
        else:
            st.error("Missing Firebase Credentials in Secrets!")
            db = None
    except Exception as e:
        st.error(f"Cloud Connection Error: {e}")
        db = None
else:
    db = firestore.client()

# --- DATABASE HELPERS ---
def get_data(collection):
    if db is None: return pd.DataFrame()
    docs = db.collection(collection).get()
    data = [doc.to_dict() | {"id": doc.id} for doc in docs]
    return pd.DataFrame(data)

def save_data(collection, data):
    if db is not None:
        db.collection(collection).add(data)
        st.cache_data.clear()
        return True
    return False

# --- UI STYLING ---
st.markdown("""
    <style>
    .main { background: #f9f9f9; }
    div[data-testid="stMetricValue"] { color: #1f77b4; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 15px; background: #1f77b4; color: white; height: 3em; }
    </style>
    """, unsafe_allow_html=True)

# --- NAVIGATION ---
st.sidebar.title("🏦 EduFinance Pro")
menu = ["📊 Dashboard", "👤 Registry", "💸 Payments", "📜 Debt Ledger"]
choice = st.sidebar.radio("Menu", menu)

ALL_CLASSES = ["Kg 1", "Kg 2", "Nur 1", "Nur 2", "Pry 1", "Pry 2", "Pry 3", "Pry 4", "Pry 5", "JSS 1", "JSS 2", "JSS 3", "SSS 1", "SSS 2", "SSS 3"]

# --- 1. DASHBOARD ---
if choice == "📊 Dashboard":
    st.title("Financial Overview")
    s_df = get_data("students")
    p_df = get_data("payments")
    
    if not s_df.empty:
        total_exp = s_df['total_fees'].sum()
        total_col = p_df['amount'].sum() if not p_df.empty else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Expected Revenue", f"₦{total_exp:,.2f}")
        c2.metric("Total Collected", f"₦{total_col:,.2f}")
        c3.metric("Outstanding Debt", f"₦{(total_exp - total_col):,.2f}", delta_color="inverse")
    else:
        st.info("Start by registering students.")

# --- 2. REGISTRY ---
elif choice == "👤 Registry":
    st.subheader("Student Enrollment")
    with st.form("reg", clear_on_submit=True):
        name = st.text_input("Full Name")
        s_class = st.selectbox("Class", ALL_CLASSES)
        fees = st.number_input("Termly Fee (₦)", min_value=0.0)
        if st.form_submit_button("Register Student"):
            if name and save_data("students", {"name": name, "class": s_class, "total_fees": fees}):
                st.success(f"{name} registered!")
                st.rerun()

# --- 3. PAYMENTS ---
elif choice == "💸 Payments":
    st.subheader("Post a Payment")
    s_df = get_data("students")
    if not s_df.empty:
        selected = st.selectbox("Select Student", s_df['name'].tolist())
        sid = s_df[s_df['name'] == selected]['id'].values[0]
        amt = st.number_input("Amount (₦)", min_value=0.0)
        dt = st.date_input("Date", datetime.now())
        
        if st.button("Submit Payment"):
            p_data = {"sid": sid, "name": selected, "amount": amt, "date": str(dt), "time": datetime.now().strftime("%H:%M:%S")}
            if save_data("payments", p_data):
                st.balloons()
                st.success("Payment Recorded!")
                st.rerun()

# --- 4. DEBT LEDGER ---
elif choice == "📜 Debt Ledger":
    st.subheader("Collection Report")
    s_df = get_data("students")
    p_df = get_data("payments")

    if not s_df.empty:
        report = []
        for _, s in s_df.iterrows():
            # Filter payments for this specific student
            student_payments = p_df[p_df['sid'] == s['id']] if not p_df.empty else pd.DataFrame()
            paid = student_payments['amount'].sum() if not student_payments.empty else 0
            
            # Get the exact Date and Time of the last payment
            last_pay = "No Record"
            if not student_payments.empty:
                last_row = student_payments.sort_values(by=['date', 'time']).iloc[-1]
                last_pay = f"{last_row['date']} at {last_row['time']}"

            report.append({
                "Student Name": s['name'],
                "Class": s['class'],
                "Total Fee": s['total_fees'],
                "Paid": paid,
                "Balance": s['total_fees'] - paid,
                "Last Payment Info": last_pay
            })
        
        final_df = pd.DataFrame(report)
        st.table(final_df.style.format({"Total Fee": "₦{:,.2f}", "Paid": "₦{:,.2f}", "Balance": "₦{:,.2f}"}))
