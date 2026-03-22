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
            raw_json = st.secrets["firebase_json"]
            info = json.loads(raw_json)
            cred = credentials.Certificate(info)
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            key_path = os.path.join(current_dir, "serviceAccountKey.json")
            cred = credentials.Certificate(key_path)
            
        firebase_admin.initialize_app(cred)
        st.sidebar.success("☁️ Cloud Database Connected")
    except Exception as e:
        st.sidebar.error(f"⚠️ Connection Failed: {e}")

# Securely get Firestore client
try:
    db = firestore.client()
except:
    db = None

# --- DATABASE LOGIC ---
def get_db_connection():
    return sqlite3.connect('school_finance.db', check_same_thread=False)

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS students 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, class TEXT, total_fees REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS payments 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, amount REAL, date TEXT, 
                  FOREIGN KEY(student_id) REFERENCES students(id))''')
    conn.commit()
    conn.close()

def save_data(query, params=()):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    st.cache_data.clear() 

@st.cache_data(ttl=10)
def run_query(query):
    conn = get_db_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df

init_db()

# --- CLOUD SYNC LOGIC ---
def sync_to_firebase(table_name):
    if db is None:
        st.error("Firebase connection is not active.")
        return
    df = run_query(f"SELECT * FROM {table_name}")
    if df.empty:
        st.warning(f"No data in {table_name} to sync.")
        return
        
    with st.spinner(f"Syncing {table_name} to Cloud..."):
        for index, row in df.iterrows():
            # Convert row to dict and ensure ID is a string
            data = row.to_dict()
            db.collection(table_name).document(str(row['id'])).set(data)
    st.success(f"✅ {table_name.capitalize()} synced!")

def cloud_delete(table_name, doc_id):
    if db is not None:
        try:
            db.collection(table_name).document(str(doc_id)).delete()
        except: pass

# --- STYLING ---
st.markdown("""
    <style>
    .main { background: #f0f2f6; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #1f77b4; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 20px; background: #1f77b4; color: white; }
    </style>
    """, unsafe_allow_html=True)

ALL_CLASSES = ["Kg 1", "Kg 1b", "Kg 2", "Nur 1", "Nur 2", "Pry 1", "Pry 2", "Pry 3", "Pry 4", "Pry 5", "JSS 1", "JSS 2", "JSS 3", "SSS 1", "SSS 2", "SSS 3"]

# --- SIDEBAR ---
st.sidebar.title("EduFinance Pro")
st.sidebar.markdown("### ☁️ Backup Tools")
# The sync only happens when this button is pressed
if st.sidebar.button("Push Data to Google Cloud"):
    sync_to_firebase("students")
    sync_to_firebase("payments")

st.sidebar.markdown("---")
menu = ["📊 Executive Dashboard", "👤 Student Registry", "💸 Post Payment", "📜 Debt Ledger"]
choice = st.sidebar.radio("Main Menu", menu)

# --- DASHBOARD ---
if "Executive Dashboard" in choice:
    st.title("🏦 Financial Intelligence Dashboard")
    df_students = run_query("SELECT * FROM students")
    df_payments = run_query("SELECT * FROM payments")
    
    if not df_students.empty:
        total_expected = df_students['total_fees'].sum()
        total_collected = df_payments['amount'].sum() if not df_payments.empty else 0
        total_debt = total_expected - total_collected

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Revenue Target", f"₦{total_expected:,.2f}")
        m2.metric("Actual Income", f"₦{total_collected:,.2f}", f"{(total_collected/total_expected*100):.1f}%" if total_expected > 0 else "0%")
        m3.metric("Outstanding", f"₦{total_debt:,.2f}", delta_color="inverse")
        m4.metric("Student Count", len(df_students))
    else:
        st.info("Please register students in the 'Student Registry' to begin.")

# --- STUDENT REGISTRY ---
elif "Student Registry" in choice:
    st.subheader("👥 Student Records Management")
    tab1, tab2, tab3 = st.tabs(["Add New Student", "View/Manage Students", "🛠️ Admin Tools"])
    
    with tab1:
        with st.form("reg_form", clear_on_submit=True):
            name = st.text_input("Student Full Name")
            s_class = st.selectbox("Assign Class", ALL_CLASSES)
            fees = st.number_input("Termly Tuition Fee (₦)", min_value=0.0, step=500.0)
            if st.form_submit_button("Complete Registration"):
                if name:
                    save_data("INSERT INTO students (name, class, total_fees) VALUES (?, ?, ?)", (name, s_class, fees))
                    st.success(f"Successfully added {name}")
                    st.rerun()

    with tab2:
        st.dataframe(run_query("SELECT * FROM students"), use_container_width=True)

    with tab3:
        m_code = st.text_input("Enter Master Deletion Code", type="password")
        if m_code == "BOUESTI2026":
            df_del = run_query("SELECT id, name, class FROM students")
            if not df_del.empty:
                df_del['display'] = df_del['name'] + " (" + df_del['class'] + ")"
                target = st.selectbox("Select Student to Delete", df_del['display'])
                if st.button("Confirm Delete"):
                    sid = df_del[df_del['display'] == target]['id'].values[0]
                    save_data("DELETE FROM payments WHERE student_id = ?", (int(sid),))
                    save_data("DELETE FROM students WHERE id = ?", (int(sid),))
                    cloud_delete("students", sid)
                    st.success(f"Removed {target}")
                    st.rerun()

# --- POST PAYMENT ---
elif "Post Payment" in choice:
    st.subheader("💰 Payment Processing")
    df_students = run_query("SELECT id, name, class FROM students")
    if not df_students.empty:
        df_students['display'] = df_students['name'] + " (" + df_students['class'] + ")"
        student_dict = dict(zip(df_students['display'], df_students['id']))
        selected = st.selectbox("Select Student", df_students['display'])
        amount = st.number_input("Amount Received (₦)", min_value=0.0)
        
        date = st.date_input("Date", datetime.now())
        full_timestamp = f"{date} {datetime.now().strftime('%H:%M:%S')}"
        
        if st.button("Confirm Payment"):
            save_data("INSERT INTO payments (student_id, amount, date) VALUES (?, ?, ?)", (student_dict[selected], amount, full_timestamp))
            st.balloons()
            st.rerun()
    else:
        st.warning("Register students first.")

# --- DEBT LEDGER ---
elif "Debt Ledger" in choice:
    st.subheader("📜 Debt Collection & Reports")
    
    st.markdown("### 📊 Balances Overview")
    df_debt = run_query("""
        SELECT s.name, s.class, s.total_fees, SUM(IFNULL(p.amount, 0)) as paid
        FROM students s LEFT JOIN payments p ON s.id = p.student_id
        GROUP BY s.id
    """)
    df_debt['Balance'] = df_debt['total_fees'] - df_debt['paid']
    st.dataframe(df_debt, use_container_width=True)
    
    st.markdown("---")
    st.markdown("### 🕒 Detailed Payment History")
    df_history = run_query("""
        SELECT s.name, s.class, p.amount, p.date 
        FROM payments p JOIN students s ON p.student_id = s.id
        ORDER BY p.id DESC
    """)
    st.dataframe(df_history, use_container_width=True)
