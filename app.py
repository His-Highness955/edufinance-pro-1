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
        db = firestore.client()
        st.sidebar.success("☁️ Cloud Database Connected")
    except Exception as e:
        st.sidebar.error(f"⚠️ Connection Failed: {e}")
        db = None
else:
    db = firestore.client()

# --- DATABASE LOGIC (Cached for Speed) ---
@st.cache_resource
def init_db():
    conn = sqlite3.connect('school_finance.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS students 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, class TEXT, total_fees REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS payments 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, amount REAL, date TEXT, 
                  FOREIGN KEY(student_id) REFERENCES students(id))''')
    conn.commit()
    return conn

conn = init_db()

@st.cache_data
def run_query(query):
    return pd.read_sql(query, conn)

# --- CLOUD SYNC & DELETE LOGIC ---
def sync_to_firebase(table_name):
    if db is None:
        st.error("Firebase connection is not active.")
        return
    df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    with st.spinner(f"Syncing {table_name}..."):
        for index, row in df.iterrows():
            db.collection(table_name).document(str(row['id'])).set(row.to_dict())
    st.success(f"✅ {table_name.capitalize()} synced!")

def cloud_delete(table_name, doc_id):
    if db is not None:
        try:
            db.collection(table_name).document(str(doc_id)).delete()
        except: pass

# --- MODERN STYLING ---
st.markdown("""
    <style>
    .main { background: #f0f2f6; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #1f77b4; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 20px; border: none; background: #1f77b4; color: white; transition: 0.3s; }
    .stButton>button:hover { background: #145a8d; transform: scale(1.02); }
    [data-testid="stSidebar"] { background-color: #0e1117; color: white; }
    .css-1r6slb0 { border-radius: 15px; border: 1px solid #ddd; padding: 15px; background: white; }
    </style>
    """, unsafe_allow_html=True)

ALL_CLASSES = ["Kg 1", "Kg 1b", "Kg 2", "Nur 1", "Nur 2", "Pry 1", "Pry 2", "Pry 3", "Pry 4", "Pry 5", "JSS 1", "JSS 2", "JSS 3", "SSS 1", "SSS 2", "SSS 3"]

# --- SIDEBAR ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2830/2830284.png", width=100)
st.sidebar.title("EduFinance Pro")
if st.sidebar.button("Push Data to Google Cloud"):
    sync_to_firebase("students")
    sync_to_firebase("payments")

st.sidebar.markdown("---")
menu = ["📊 Executive Dashboard", "👤 Student Registry", "💸 Post Payment", "📜 Debt Ledger"]
choice = st.sidebar.radio("Main Menu", menu)

# --- DASHBOARD VIEW ---
if "Executive Dashboard" in choice:
    st.title("🏦 Financial Intelligence Dashboard")
    df_students = run_query("SELECT * FROM students")
    df_payments = run_query("SELECT * FROM payments")
    if not df_students.empty:
        total_expected = df_students['total_fees'].sum()
        total_collected = df_payments['amount'].sum()
        total_debt = total_expected - total_collected
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Revenue Target", f"₦{total_expected:,.2f}")
        m2.metric("Actual Income", f"₦{total_collected:,.2f}", f"{(total_collected/total_expected*100):.1f}%")
        m3.metric("Outstanding", f"₦{total_debt:,.2f}", delta_color="inverse")
        m4.metric("Student Count", len(df_students))
        st.markdown("---")
        col_left, col_right = st.columns([2, 1])
        with col_left:
            if not df_payments.empty:
                df_payments['date'] = pd.to_datetime(df_payments['date'])
                trend = df_payments.groupby('date')['amount'].sum().reset_index()
                st.plotly_chart(px.line(trend, x='date', y='amount', title="Income Flow"), use_container_width=True)
        with col_right:
            st.plotly_chart(px.pie(names=['Collected', 'Pending'], values=[total_collected, total_debt], hole=0.4), use_container_width=True)
    else:
        st.info("No students registered yet.")

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
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO students (name, class, total_fees) VALUES (?, ?, ?)", (name, s_class, fees))
                    conn.commit()
                    st.cache_data.clear()
                    st.success(f"Added {name}!")
                else: st.error("Name is required.")
    with tab2:
        st.dataframe(run_query("SELECT * FROM students"), use_container_width=True)
        if st.button("Refresh List"): st.rerun()
    with tab3:
        st.warning("⚠️ Requires Master Code")
        m_code = st.text_input("Enter Master Deletion Code", type="password")
        if m_code == "BOUESTI2026":
            del_mode = st.radio("Delete Mode", ["Single Student", "Wipe All Local"])
            if del_mode == "Single Student":
                df_del = run_query("SELECT id, name, class FROM students")
                if not df_del.empty:
                    df_del['display'] = df_del['name'] + " (" + df_del['class'] + ")"
                    target = st.selectbox("Target", df_del['display'])
                    if st.button("Confirm Delete"):
                        sid = df_del[df_del['display'] == target]['id'].values[0]
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM payments WHERE student_id = ?", (int(sid),))
                        cursor.execute("DELETE FROM students WHERE id = ?", (int(sid),))
                        conn.commit()
                        cloud_delete("students", sid)
                        st.cache_data.clear()
                        st.success(f"Removed {target}")
            elif del_mode == "Wipe All Local":
                if st.button("🚨 WIPE LOCAL DATABASE"):
                    cursor = conn.cursor(); cursor.execute("DELETE FROM students"); cursor.execute("DELETE FROM payments")
                    conn.commit(); st.cache_data.clear(); st.success("Cleared.")

# --- POST PAYMENT ---
elif "Post Payment" in choice:
    st.subheader("💰 Payment Processing")
    df_students = run_query("SELECT id, name, class FROM students")
    if not df_students.empty:
        df_students['display'] = df_students['name'] + " (" + df_students['class'] + ")"
        student_dict = dict(zip(df_students['display'], df_students['id']))
        selected = st.selectbox("Select Student", df_students['display'])
        amount = st.number_input("Amount (₦)", min_value=0.0)
        date = st.date_input("Date", datetime.now())
        if st.button("Confirm Payment"):
            cursor = conn.cursor()
            cursor.execute("INSERT INTO payments (student_id, amount, date) VALUES (?, ?, ?)", (student_dict[selected], amount, str(date)))
            conn.commit(); st.cache_data.clear(); st.balloons(); st.success("Payment Recorded!")
    else: st.warning("No students found.")

# --- DEBT LEDGER ---
elif "Debt Ledger" in choice:
    st.subheader("📜 Debt Collection & Reports")
    query = "SELECT s.name, s.class, s.total_fees as fee, SUM(IFNULL(p.amount, 0)) as paid FROM students s LEFT JOIN payments p ON s.id = p.student_id GROUP BY s.id"
    df_debt = run_query(query)
    df_debt['Balance'] = df_debt['fee'] - df_debt['paid']
    if st.checkbox("Show Only Debtors", value=True):
        df_debt = df_debt[df_debt['Balance'] > 0]
    st.dataframe(df_debt.style.format({"fee": "₦{:,.2f}", "paid": "₦{:,.2f}", "Balance": "₦{:,.2f}"}), use_container_width=True)
    st.download_button("📥 Download CSV", df_debt.to_csv(index=False).encode('utf-8'), "debt_report.csv", "text/csv")
