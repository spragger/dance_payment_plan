import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

# PDF generation
from fpdf import FPDF

# --- DATABASE CONNECTION ---
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "dance.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# --- CATALOG TABLE SETUP ---
c.execute("""
CREATE TABLE IF NOT EXISTS catalog_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    price REAL NOT NULL
);
""")
conn.commit()

# --- CATALOG CRUD FUNCTIONS ---
def get_catalog_categories():
    df = pd.read_sql("SELECT DISTINCT category FROM catalog_items ORDER BY category", conn)
    return df['category'].tolist()

def get_catalog_items(category):
    return pd.read_sql(
        "SELECT id, name, price FROM catalog_items WHERE category = ? ORDER BY name", 
        conn, params=(category,)
    )

def add_catalog_item(category, name, price):
    c.execute(
        "INSERT INTO catalog_items (category, name, price) VALUES (?, ?, ?)",
        (category, name, price)
    )
    conn.commit()

# --- PAYMENT PLAN MODULE ---
import payment_plan

# --- UI ---
st.set_page_config(page_title="Payment Plans", layout="wide")
st.title("Payment Plans")

# --- Manage Catalog ---
with st.expander("Manage Item Catalog", expanded=False):
    st.subheader("Add Catalog Item")
    categories = get_catalog_categories()
    category = st.selectbox("Category", categories, key="new_cat")
    item_name = st.text_input("Item Name", key="new_item_name")
    item_price = st.number_input("Item Price", min_value=0.0, format="%.2f", key="new_item_price")
    if st.button("Add Catalog Item", key="btn_add_catalog_item"):
        cat = category
        if cat and item_name:
            add_catalog_item(cat, item_name, item_price)
            st.success(f"Added item '{item_name}' under '{cat}'")
    for cat in categories:
        df_cat = get_catalog_items(cat)
        if not df_cat.empty:
            st.write(f"**{cat}**")
            st.table(df_cat[['name', 'price']])

# --- Select Student ---
st.subheader("Select Student")
students_df = pd.read_sql("SELECT id, first_name, last_name FROM students ORDER BY last_name, first_name", conn)
student_map = {f"{r.last_name}, {r.first_name}": r.id for r in students_df.itertuples()}
sel_student = st.selectbox("Student", ["--"] + list(student_map.keys()), key="pp_student")

if sel_student and sel_student != "--":
    sid = student_map[sel_student]
    st.header(f"Build Payment Plan for {sel_student}")
    with st.form("payment_plan_form"):
        selections = {}
        subtotals = {}
        fixed_categories = [
            "Tuition", "Solo/Duo/Trio", "Groups", "Competitions & Conventions",
            "Choreography", "Costume Fees", "Administrative Fees", "Miscellaneous Fees"
        ]
        for cat in fixed_categories:
            df_items = get_catalog_items(cat)
            options = [f"{row['name']} (${row['price']:.2f})" for _, row in df_items.iterrows()]
            sel_opts = st.multiselect(f"Select {cat}", options, key=f"sel_{cat}")
            total = sum(float(opt.split('$')[1].strip(')')) for opt in sel_opts)
            st.write(f"{cat} Subtotal: ${total:.2f}")
            selections[cat] = sel_opts
            subtotals[cat] = total
        st.markdown("---")
        st.subheader("Down Payments")
        down1 = st.number_input("Down Payment 1", min_value=0.0, format="%.2f", key="pp_down1")
        down2 = st.number_input("Down Payment 2", min_value=0.0, format="%.2f", key="pp_down2")
        total_down = down1 + down2
        st.write(f"Total Down: ${total_down:.2f}")
        months = st.slider("Number of Months", 6, 10, 6, key="pp_months")
        st.markdown("---")
        submitted = st.form_submit_button("Save & Generate PDF")
    if submitted:
        grand_total = sum(subtotals.values())
        remaining = grand_total - total_down
        installment = remaining / months if months else 0.0
        # Persist
        plan_id = payment_plan.add_student_plan(sid, None)
        for cat, opts in selections.items():
            for opt in opts:
                name = opt.split(' ($')[0]
                price = float(opt.split('$')[1].strip(')'))
                payment_plan.add_plan_item(plan_id, name, price, cat)
        payment_plan.add_plan_item(plan_id, "Down Payment 1", down1, "Down Payment")
        payment_plan.add_plan_item(plan_id, "Down Payment 2", down2, "Down Payment")
        # PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, f"Payment Plan for {sel_student}", ln=1)
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 8, f"Date: {datetime.today().strftime('%Y-%m-%d')}", ln=1)
        pdf.ln(4)
        for cat, total in subtotals.items():
            pdf.cell(120, 8, cat, border=0)
            pdf.cell(40, 8, f"${total:.2f}", ln=1)
        pdf.ln(2)
        pdf.cell(120, 8, "Total Down Payments", border=0)
        pdf.cell(40, 8, f"-${total_down:.2f}", ln=1)
        pdf.ln(2)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(120, 8, 'Grand Total', border=0)
        pdf.cell(40, 8, f"${grand_total:.2f}", ln=1)
        pdf.cell(120, 8, 'Remaining Balance', border=0)
        pdf.cell(40, 8, f"${remaining:.2f}", ln=1)
        pdf.cell(120, 8, f"Installments ({months} mo)", border=0)
        pdf.cell(40, 8, f"${installment:.2f}", ln=1)
        pdf_bytes = pdf.output(dest='S').encode('latin1')
        st.success("Payment plan saved and PDF generated.")
        st.download_button(
            "Download PDF", data=pdf_bytes,
            file_name=f"PaymentPlan_{sel_student.replace(', ','_')}_{datetime.today().strftime('%Y%m%d')}.pdf",
            mime='application/pdf'
        )
else:
    st.info("Select a student to begin building a plan.")
