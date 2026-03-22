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
        if "firebase_json" in st.secrets:
            # For Streamlit Cloud Deployment
            raw_json = st.secrets["firebase_json"]
            info = json.loads(raw_json)
            cred = credentials.Certificate(info)
        else:
            # For Local Testing (Make sure your JSON file is in the folder)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            key_path = os.path.join(current_dir, "serviceAccountKey.json")
            cred = credentials.Certificate(key_path)
            
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        st.sidebar.success("☁️ Connected to Google Cloud")
    except Exception as e:
        st.sidebar.error(f"⚠️ Cloud Connection Failed: {e}")
        db = None
else:
    db = firestore.client()

# --- CLOUD DATA ENGINE ---
def get_all_data(collection_name):
    """Fetches real-time data from Google Cloud Firestore."""
    if db is None: return pd.DataFrame()
    docs = db.collection(collection_name).stream()
    data = []
    for doc in docs:
        item = doc.to_dict()
        item['id'] = doc.id  # Keep track of the document ID for deletions
        data.append(item)
    return pd.DataFrame(data)

def save_to_cloud(collection_name, data):
    """Saves a new record directly to the Cloud."""
    if db is not None:
        db.collection(collection_name).add(data)
        st.cache_data.clear()
        return True
    return False

def delete_from_cloud(collection_name, doc_id):
    """Permanently removes a record from the Cloud."""
    if db is not None:
        db.collection(collection_name).document(doc_id).delete()
        st.cache_data.clear()
        return True
    return False

# --- MODERN STYLING ---
st.markdown("""
    <style>
    .main { background: #f8f9fa; }
    div[data-testid="stMetricValue"] { font-size: 2rem; color: #1f77b4; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3em; background: #1f77b4; color: white; }
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
    students_df = get_all_data("students")
    payments_df = get_all_data("payments")

    if not students_df.empty:
        total_expected = students_df['total_fees'].sum()
        total_collected = payments_df['amount'].sum() if not payments_df.empty else 0
        total_debt = total_expected - total_collected

        m1, m2, m3 = st.columns(3)
        m1.metric("Revenue Target", f"₦{total_expected:,.2f}")
        m2.metric("Actual Income", f"₦{total_collected:,.2f}")
        m3.metric("Outstanding", f"₦{total_debt:,.2f}", delta_color="inverse")
        
        st.info("Cloud Sync Active: Metrics reflect all devices.")
    else:
        st.info("Welcome. Start by registering students in the Registry.")

# --- 2. STUDENT REGISTRY ---
elif choice == "👤 Student Registry":
    st.subheader("👥 Student Records")
    tab1, tab2, tab3 = st.tabs(["Add New Student", "View All Students", "🛠️ Admin Tools"])

    with tab1:
        with st.form("reg_form", clear_on_submit=True):
            name = st.text_input("Student Full Name")
            s_class = st.selectbox("Assign Class", ALL_CLASSES)
            fees = st.number_input("Termly Tuition (₦)", min_value=0.0, step=500.0)
            if st.form_submit_button("Register to Cloud"):
                if name:
                    new_student = {"name": name, "class": s_class, "total_fees": fees}
                    if save_to_cloud("students", new_student):
                        st.success(f"Registered {name} successfully!")
                else: st.error("Name is required.")

    with tab2:
        st.dataframe(get_all_data("students"), use_container_width=True)

    with tab3:
        st.warning("Admin Access Required")
        code = st.text_input("Master Code", type="password")
        if code == "BOUESTI2026":
            st.write("Select a student to remove from Cloud database:")
            df_del = get_all_data("students")
            if not df_del.empty:
                target_name = st.selectbox("Select Student", df_del['name'])
                target_id = df_del[df_del['name'] == target_name]['id'].values[0]
                if st.button("🚨 PERMANENT DELETE"):
                    if delete_from_cloud("students", target_id):
                        st.success("Record Deleted.")
                        st.rerun()

# --- 3. POST PAYMENT ---
elif choice == "💸 Post Payment":
    st.subheader("💰 Record Payment")
    students_df = get_all_data("students")
    
    if not students_df.empty:
        # Create list for dropdown
        names = students_df['name'].tolist()
        selected_student = st.selectbox("Select Student", names)
        
        # Get the ID of selected student for mapping
        sid = students_df[students_df['name'] == selected_student]['id'].values[0]
        
        amount = st.number_input("Amount Paid (₦)", min_value=0.0)
        p_date = st.date_input("Date", datetime.now())

        if st.button("Confirm Payment"):
            payment_data = {
                "student_name": selected_student,
                "student_id": sid,
                "amount": amount,
                "date": str(p_date)
            }
            if save_to_cloud("payments", payment_data):
                st.balloons()
                st.success("Payment saved to Cloud!")
    else:
        st.warning("Register students before posting payments.")

# --- 4. DEBT LEDGER ---
elif choice == "📜 Debt Ledger":
    st.subheader("📑 Outstanding Balances")
    s_df = get_all_data("students")
    p_df = get_all_data("payments")

    if not s_df.empty:
        # Calculate totals per student
        report = []
        for _, s in s_df.iterrows():
            # Filter payments for this student
            total_paid = 0
            if not p_df.empty:
                total_paid = p_df[p_df['student_id'] == s['id']]['amount'].sum()
            
            balance = s['total_fees'] - total_paid
            report.append({
                "Student": s['name'],
                "Class": s['class'],
                "Total Fee": s['total_fees'],
                "Paid": total_paid,
                "Balance": balance
            })
        
        final_report = pd.DataFrame(report)
        if st.checkbox("Show Only Debtors", value=True):
            final_report = final_report[final_report['Balance'] > 0]
        
        st.table(final_report)
        st.download_button("📥 Download Report", final_report.to_csv(index=False), "debtors.csv")
