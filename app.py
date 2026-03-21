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

# --- FIREBASE INITIALIZATION (Cloud-Safe Version) ---
if not firebase_admin._apps:
    try:
        # 1. Try to load from Streamlit Cloud Secrets (for your Dad's link)
        if "firebase_json" in st.secrets:
            # We use the key name "firebase_json" which we will set in Step 2
            raw_json = st.secrets["firebase_json"]
            info = json.loads(raw_json)
            cred = credentials.Certificate(info)
            
        # 2. Try to load from local file (only works on your Laptop)
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            key_path = os.path.join(current_dir, "serviceAccountKey.json")
            cred = credentials.Certificate(key_path)
            
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        st.sidebar.success("☁️ Cloud Database Connected")
    except Exception as e:
        # If both methods fail, show the error in the sidebar
        st.sidebar.error(f"⚠️ Connection Failed: {e}")
        db = None
else:
    db = firestore.client()
    
# --- DATABASE LOGIC (Local SQLite) ---
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

# --- CLOUD SYNC LOGIC ---
def sync_to_firebase(table_name):
    if db is None:
        st.error("Cannot sync: Firebase connection is not active.")
        return
    
    df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    if df.empty:
        st.warning(f"No records in {table_name} to sync.")
        return

    with st.spinner(f"Syncing {len(df)} {table_name} records to Google Cloud..."):
        for index, row in df.iterrows():
            # Uses the SQLite ID as the Cloud Document ID to prevent duplicates
            db.collection(table_name).document(str(row['id'])).set(row.to_dict())
    st.success(f"✅ {table_name.capitalize()} synced successfully!")

# --- HIGH-END MODERN STYLING (Glassmorphism) ---
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

# --- GLOBAL SETTINGS ---
ALL_CLASSES = [
    "Kg 1", "Kg 1b", "Kg 2", "Nur 1", "Nur 2", 
    "Pry 1", "Pry 2", "Pry 3", "Pry 4", "Pry 5", 
    "JSS 1", "JSS 2", "JSS 3", "SSS 1", "SSS 2", "SSS 3"
]

# --- SIDEBAR NAVIGATION ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2830/2830284.png", width=100)
st.sidebar.title("EduFinance Pro")

# Cloud Sync Section
st.sidebar.markdown("### ☁️ Backup Tools")
if st.sidebar.button("Push Data to Google Cloud"):
    sync_to_firebase("students")
    sync_to_firebase("payments")

st.sidebar.markdown("---")
menu = ["📊 Executive Dashboard", "👤 Student Registry", "💸 Post Payment", "📜 Debt Ledger"]
choice = st.sidebar.radio("Main Menu", menu)

# --- DASHBOARD VIEW ---
if "Executive Dashboard" in choice:
    st.title("🏦 Financial Intelligence Dashboard")
    
    df_students = pd.read_sql("SELECT * FROM students", conn)
    df_payments = pd.read_sql("SELECT * FROM payments", conn)
    
    if not df_students.empty:
        total_expected = df_students['total_fees'].sum()
        total_collected = df_payments['amount'].sum()
        total_debt = total_expected - total_collected

        # Metrics Row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Revenue Target", f"₦{total_expected:,.2f}")
        m2.metric("Actual Income", f"₦{total_collected:,.2f}", f"{(total_collected/total_expected*100):.1f}%")
        m3.metric("Outstanding", f"₦{total_debt:,.2f}", delta_color="inverse")
        m4.metric("Student Count", len(df_students))

        st.markdown("---")

        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.subheader("Payment Trends")
            if not df_payments.empty:
                df_payments['date'] = pd.to_datetime(df_payments['date'])
                trend_data = df_payments.groupby('date')['amount'].sum().reset_index()
                fig = px.line(trend_data, x='date', y='amount', title="Income Flow Over Time")
                st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.subheader("Collection Status")
            fig_pie = px.pie(names=['Collected', 'Pending'], values=[total_collected, total_debt], 
                             color_discrete_sequence=['#2ecc71', '#e74c3c'], hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Welcome! Please register students in the 'Student Registry' to begin tracking finances.")

# --- STUDENT REGISTRY ---
elif "Student Registry" in choice:
    st.subheader("👥 Student Records Management")
    
    tab1, tab2 = st.tabs(["Add New Student", "View/Manage Students"])
    
    with tab1:
        with st.form("reg_form", clear_on_submit=True):
            name = st.text_input("Student Full Name")
            s_class = st.selectbox("Assign Class", ALL_CLASSES)
            fees = st.number_input("Termly Tuition Fee (₦)", min_value=0.0, step=500.0)
            if st.form_submit_button("Complete Registration"):
                if name:
                    conn.execute("INSERT INTO students (name, class, total_fees) VALUES (?, ?, ?)", (name, s_class, fees))
                    conn.commit()
                    st.success(f"Successfully added {name} to {s_class}")
                else:
                    st.error("Name is required.")

    with tab2:
        df_view = pd.read_sql("SELECT * FROM students", conn)
        st.dataframe(df_view, use_container_width=True)
        if st.button("Refresh List"):
            st.rerun()

# --- POST PAYMENT ---
elif "Post Payment" in choice:
    st.subheader("💰 Payment Processing")
    
    df_students = pd.read_sql("SELECT id, name, class FROM students", conn)
    if not df_students.empty:
        df_students['display'] = df_students['name'] + " (" + df_students['class'] + ")"
        student_dict = dict(zip(df_students['display'], df_students['id']))
        
        selected = st.selectbox("Select Student", df_students['display'])
        amount = st.number_input("Amount Received (₦)", min_value=0.0)
        date = st.date_input("Transaction Date", datetime.now())
        
        if st.button("Confirm Payment"):
            conn.execute("INSERT INTO payments (student_id, amount, date) VALUES (?, ?, ?)", 
                         (student_dict[selected], amount, str(date)))
            conn.commit()
            st.balloons()
            st.success(f"Payment of ₦{amount:,.2f} recorded for {selected}")
    else:
        st.warning("No students found. Please register a student first.")

# --- DEBT LEDGER ---
elif "Debt Ledger" in choice:
    st.subheader("📜 Debt Collection & Reports")
    
    query = """
    SELECT s.name as 'Student Name', s.class as 'Class', s.total_fees as 'Total Fee', 
           SUM(IFNULL(p.amount, 0)) as 'Total Paid'
    FROM students s
    LEFT JOIN payments p ON s.id = p.student_id
    GROUP BY s.id
    """
    df_debt = pd.read_sql(query, conn)
    df_debt['Balance Owed'] = df_debt['Total Fee'] - df_debt['Total Paid']
    
    # Filtering
    only_debtors = st.checkbox("Show Only Debtors", value=True)
    if only_debtors:
        df_debt = df_debt[df_debt['Balance Owed'] > 0]
    
    # Modern Table Display
    st.dataframe(df_debt.style.format({"Total Fee": "₦{:,.2f}", "Total Paid": "₦{:,.2f}", "Balance Owed": "₦{:,.2f}"})
                 .background_gradient(subset=['Balance Owed'], cmap='Reds'), use_container_width=True)

    # CSV Export
    csv = df_debt.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Debt Report (Excel/CSV)", csv, "debt_report.csv", "text/csv")
