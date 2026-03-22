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

db = firestore.client() if firebase_admin._apps else None

# --- DATABASE LOGIC (Enhanced for Updates) ---
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
    """Handles writes and clears cache immediately."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    st.cache_data.clear() # Forces app to refresh data on next read

@st.cache_data(ttl=10) # Refresh data every 10 seconds automatically
def run_query(query):
    conn = get_db_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# Initialize DB on startup
init_db()

# --- CLOUD SYNC & DELETE logic ---
def cloud_delete(table_name, doc_id):
    """Removes records from Google Cloud immediately."""
    if db is not None:
        try:
            db.collection(table_name).document(str(doc_id)).delete()
        except: pass

# --- STYLING ---
st.markdown("""
    <style>
    .main { background: #f0f2f6; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #1f77b4; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 20px; border: none; background: #1f77b4; color: white; transition: 0.3s; }
    .stButton>button:hover { background: #145a8d; transform: scale(1.02); }
    [data-testid="stSidebar"] { background-color: #0e1117; color: white; }
    </style>
    """, unsafe_allow_html=True)

ALL_CLASSES = ["Kg 1", "Kg 1b", "Kg 2", "Nur 1", "Nur 2", "Pry 1", "Pry 2", "Pry 3", "Pry 4", "Pry 5", "JSS 1", "JSS 2", "JSS 3", "SSS 1", "SSS 2", "SSS 3"]

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("EduFinance Pro")
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

        st.markdown("---")
        col_left, col_right = st.columns([2, 1])

        with col_left:
            if not df_payments.empty:
                df_p_plot = df_payments.copy()
                df_p_plot['date'] = pd.to_datetime(df_p_plot['date']).dt.date
                trend = df_p_plot.groupby('date')['amount'].sum().reset_index()
                st.plotly_chart(px.line(trend, x='date', y='amount', title="Income Flow Over Time"), use_container_width=True)

        with col_right:
            st.plotly_chart(px.pie(names=['Collected', 'Pending'], values=[total_collected, total_debt], 
                             color_discrete_sequence=['#2ecc71', '#e74c3c'], hole=0.4), use_container_width=True)
    else:
        st.info("Welcome! Please register students in the 'Student Registry' to begin tracking finances.")

# --- REGISTRY ---
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
                    st.success(f"Successfully added {name} to {s_class}")
                    st.rerun()
                else:
                    st.error("Name is required.")

    with tab2:
        st.dataframe(run_query("SELECT * FROM students"), use_container_width=True)
        if st.button("Refresh List"): st.rerun()

    with tab3:
        st.warning("⚠️ High Privilege Actions: Requires Master Code")
        m_code = st.text_input("Enter Master Deletion Code", type="password")
        if m_code == "BOUESTI2026":
            del_mode = st.radio("Delete Selection", ["Single Student Record", "Wipe All Local Data"])
            if del_mode == "Single Student Record":
                df_del = run_query("SELECT id, name, class FROM students")
                if not df_del.empty:
                    df_del['display'] = df_del['name'] + " (" + df_del['class'] + ")"
                    target = st.selectbox("Select Student to Delete", df_del['display'])
                    if st.button("Confirm Delete from App & Cloud"):
                        sid = df_del[df_del['display'] == target]['id'].values[0]
                        save_data("DELETE FROM payments WHERE student_id = ?", (int(sid),))
                        save_data("DELETE FROM students WHERE id = ?", (int(sid),))
                        cloud_delete("students", sid)
                        st.success(f"Successfully removed {target}")
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
        
        date = st.date_input("Transaction Date", datetime.now())
        time_now = datetime.now().strftime("%H:%M:%S")
        full_timestamp = f"{date} {time_now}"
        
        if st.button("Confirm Payment"):
            save_data("INSERT INTO payments (student_id, amount, date) VALUES (?, ?, ?)", (student_dict[selected], amount, full_timestamp))
            st.balloons()
            st.success(f"Payment of ₦{amount:,.2f} recorded for {selected}")
            st.rerun()
    else:
        st.warning("No students found. Please register a student first.")

# --- DEBT LEDGER ---
elif "Debt Ledger" in choice:
    st.subheader("📜 Debt Collection & Reports")
    
    st.markdown("### 📊 Balances Overview")
    query = """
    SELECT s.name as 'Student Name', s.class as 'Class', s.total_fees as 'Total Fee', 
           SUM(IFNULL(p.amount, 0)) as 'Total Paid'
    FROM students s
    LEFT JOIN payments p ON s.id = p.student_id
    GROUP BY s.id
    """
    df_debt = run_query(query)
    df_debt['Balance Owed'] = df_debt['Total Fee'] - df_debt['Total Paid']
    
    if st.checkbox("Show Only Debtors", value=True):
        df_debt = df_debt[df_debt['Balance Owed'] > 0]
    
    st.dataframe(df_debt.style.format({"Total Fee": "₦{:,.2f}", "Total Paid": "₦{:,.2f}", "Balance Owed": "₦{:,.2f}"}), use_container_width=True)
    
    st.markdown("---")
    
    st.markdown("### 🕒 Detailed Payment History")
    st.write("This table continues to add rows for every payment made by any student until they are deleted.")
    
    history_query = """
    SELECT s.name as 'Student Name', s.class as 'Class', p.amount as 'Amount Paid', p.date as 'Payment Date/Time'
    FROM payments p
    JOIN students s ON p.student_id = s.id
    ORDER BY p.id DESC
    """
    df_history = run_query(history_query)
    
    if not df_history.empty:
        st.dataframe(df_history.style.format({"Amount Paid": "₦{:,.2f}"}), use_container_width=True)
        csv = df_history.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download History (CSV)", csv, "payment_history.csv", "text/csv")
    else:
        st.info("No payment history recorded yet.")
