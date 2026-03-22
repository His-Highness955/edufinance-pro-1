import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
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
        st.sidebar.success("☁️ Cloud Connected")
    except Exception as e:
        st.sidebar.error("⚠️ Cloud Offline")
        db = None
else:
    db = firestore.client()

# --- DATABASE LOGIC (Optimized for Speed) ---
@st.cache_resource
def init_db():
    conn = sqlite3.connect('school_finance.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS students 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, class TEXT, total_fees REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS payments 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, amount REAL, date TEXT)''')
    conn.commit()
    return conn

def save_data(query, params=()):
    with sqlite3.connect('school_finance.db') as temp_conn:
        temp_conn.execute(query, params)
        temp_conn.commit()
    st.cache_data.clear() # Clears read cache so UI updates immediately

conn = init_db()

@st.cache_data(ttl=600) # Cache data for 10 minutes unless cleared
def run_query(query):
    return pd.read_sql(query, conn)

# --- CLOUD SYNC ---
def sync_to_firebase(table_name):
    if db is None: return
    df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    for _, row in df.iterrows():
        db.collection(table_name).document(str(row['id'])).set(row.to_dict())
    st.success(f"✅ {table_name} Synced")

# --- STYLING ---
st.markdown("""
    <style>
    .main { background: #f0f2f6; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #1f77b4; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 12px; background: #1f77b4; color: white; }
    [data-testid="stSidebar"] { background-color: #0e1117; color: white; }
    </style>
    """, unsafe_allow_html=True)

ALL_CLASSES = ["Kg 1", "Kg 1b", "Kg 2", "Nur 1", "Nur 2", "Pry 1", "Pry 2", "Pry 3", "Pry 4", "Pry 5", "JSS 1", "JSS 2", "JSS 3", "SSS 1", "SSS 2", "SSS 3"]

# --- SIDEBAR ---
st.sidebar.title("EduFinance Pro")
if st.sidebar.button("Push to Cloud"):
    sync_to_firebase("students")
    sync_to_firebase("payments")

menu = ["📊 Executive Dashboard", "👤 Student Registry", "💸 Post Payment", "📜 Debt Ledger"]
choice = st.sidebar.radio("Main Menu", menu)

# --- DASHBOARD ---
if choice == "📊 Executive Dashboard":
    st.title("🏦 Financial Summary")
    df_s = run_query("SELECT total_fees FROM students")
    df_p = run_query("SELECT amount FROM payments")
    
    if not df_s.empty:
        target = df_s['total_fees'].sum()
        actual = df_p['amount'].sum() if not df_p.empty else 0
        debt = target - actual

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Target", f"₦{target:,.0f}")
        m2.metric("Income", f"₦{actual:,.0f}", f"{(actual/target*100):.1f}%")
        m3.metric("Debt", f"₦{debt:,.0f}", delta_color="inverse")
        m4.metric("Students", len(df_s))
    else:
        st.info("No data yet.")

# --- STUDENT REGISTRY (Using Fragment for Speed) ---
elif choice == "👤 Student Registry":
    st.subheader("👥 Student Records")
    
    @st.fragment
    def registration_form():
        with st.form("reg_form", clear_on_submit=True):
            name = st.text_input("Full Name")
            s_class = st.selectbox("Class", ALL_CLASSES)
            fees = st.number_input("Tuition (₦)", min_value=0.0, step=1000.0)
            if st.form_submit_button("Register"):
                if name:
                    save_data("INSERT INTO students (name, class, total_fees) VALUES (?, ?, ?)", (name, s_class, fees))
                    st.success(f"Added {name}")
                else: st.error("Name required")
    
    tab1, tab2 = st.tabs(["Add Student", "View List"])
    with tab1: registration_form()
    with tab2: st.dataframe(run_query("SELECT * FROM students"), use_container_width=True)

# --- POST PAYMENT ---
elif choice == "💸 Post Payment":
    st.subheader("💰 Record Payment")
    df_s = run_query("SELECT id, name, class FROM students")
    
    @st.fragment
    def payment_form(df):
        df['display'] = df['name'] + " (" + df['class'] + ")"
        lookup = dict(zip(df['display'], df['id']))
        selected = st.selectbox("Student", df['display'])
        amt = st.number_input("Amount (₦)", min_value=0.0)
        dt = st.date_input("Date", datetime.now())
        
        if st.button("Confirm Payment"):
            save_data("INSERT INTO payments (student_id, amount, date) VALUES (?, ?, ?)", (lookup[selected], amt, str(dt)))
            st.balloons()
            st.success("Payment Recorded")
            
    if not df_s.empty: payment_form(df_s)
    else: st.warning("Register students first.")

# --- DEBT LEDGER ---
elif choice == "📜 Debt Ledger":
    st.subheader("📑 Debt & Payment History")
    
    # Speed-optimized SQL Join
    query = """
    SELECT s.name as 'Student', s.class as 'Class', s.total_fees as 'Fee', 
           SUM(IFNULL(p.amount, 0)) as 'Paid',
           (s.total_fees - SUM(IFNULL(p.amount, 0))) as 'Balance',
           MAX(p.date) as 'Last Payment'
    FROM students s
    LEFT JOIN payments p ON s.id = p.student_id
    GROUP BY s.id
    """
    df_debt = run_query(query)
    
    if st.checkbox("Show Only Debtors", value=True):
        df_debt = df_debt[df_debt['Balance'] > 0]
    
    st.dataframe(df_debt.style.format({"Fee": "₦{:,.2f}", "Paid": "₦{:,.2f}", "Balance": "₦{:,.2f}"}), use_container_width=True)
    st.download_button("📥 Download CSV", df_debt.to_csv(index=False), "debt_report.csv")
