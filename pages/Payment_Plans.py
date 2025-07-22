import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF

# --- DATABASE CONNECTION ---
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "dance.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# --- CATALOG FUNCTIONS ---
def get_catalog_categories():
    df = pd.read_sql("SELECT DISTINCT category FROM catalog_items ORDER BY category", conn)
    return df['category'].tolist()

def get_catalog_items(category):
    return pd.read_sql(
        "SELECT id, name, price FROM catalog_items WHERE category = ? ORDER BY name", conn, params=(category,)
    )

def add_catalog_item(category, name, price):
    c.execute("INSERT INTO catalog_items (category, name, price) VALUES (?, ?, ?)", (category, name, price))
    conn.commit()

# --- PAYMENT PLAN MODULE ---
import payment_plan

# --- UI ---
st.set_page_config(page_title="Payment Plans", layout="wide")
st.title("Payment Plans")

# Manage Catalog
with st.expander("Manage Item Catalog", expanded=False):
    fixed_categories = [
        "Tuition", "Solo/Duo/Trio", "Groups", "Competitions & Conventions",
        "Choreography", "Costume Fees", "Administrative Fees", "Miscellaneous Fees"
    ]
    existing = get_catalog_categories()
    categories = fixed_categories + [c for c in existing if c not in fixed_categories]
    category = st.selectbox("Category", categories)
    item_name = st.text_input("Item Name")
    item_price = st.number_input("Item Price", min_value=0.0, format="%.2f")
    if st.button("Add Catalog Item"):
        add_catalog_item(category, item_name, item_price)
        st.success(f"Added {item_name} in {category}")
    st.markdown("---")
    # Edit/Delete
    edit_cat = st.selectbox("Edit Category", categories)
    items_df = get_catalog_items(edit_cat)
    item_map = {row['name']: row['id'] for _, row in items_df.iterrows()}
    sel_item = st.selectbox("Select Item", ["--"] + list(item_map.keys()))
    if sel_item and sel_item != "--":
        eid = item_map[sel_item]
        cur = items_df[items_df.id==eid].iloc[0]
        new_name = st.text_input("Item Name", value=cur['name'])
        new_price = st.number_input("Item Price", value=cur['price'], min_value=0.0, format="%.2f")
        if st.button("Update Item"):
            c.execute("UPDATE catalog_items SET name=?, price=? WHERE id=?", (new_name, new_price, eid))
            conn.commit()
            st.success("Item updated.")
        if st.button("Delete Item"):
            c.execute("DELETE FROM catalog_items WHERE id=?", (eid,))
            conn.commit()
            st.success("Item deleted.")
    st.markdown("---")
    # Display
    for cat in categories:
        df_cat = get_catalog_items(cat)
        if not df_cat.empty:
            st.write(f"**{cat}**")
            st.table(df_cat[['name','price']])

# Select Student
st.subheader("Select Student")
students_df = pd.read_sql("SELECT id, first_name, last_name FROM students ORDER BY last_name", conn)
student_map = {f"{r.last_name}, {r.first_name}": r.id for r in students_df.itertuples()}
sel_student = st.selectbox("Student", ["--"] + list(student_map.keys()))

if sel_student and sel_student != "--":
    sid = student_map[sel_student]
    st.header(f"Build Plan for {sel_student}")
    with st.form("plan_form"):
        selections = {}
        subtotals = {}
        for cat in categories:
            df_items = get_catalog_items(cat)
            options = [f"{row['name']} (${row['price']:.2f})" for _, row in df_items.iterrows()]
            sel_opts = st.multiselect(f"Select {cat}", options)
            total = sum(float(opt.split('$')[1].strip(')')) for opt in sel_opts)
            st.write(f"{cat} Subtotal: ${total:.2f}")
            selections[cat] = sel_opts
            subtotals[cat] = total
        down1 = st.number_input("Down Payment 1", min_value=0.0, format="%.2f")
        down2 = st.number_input("Down Payment 2", min_value=0.0, format="%.2f")
        months = st.slider("Months", 6, 10, 6)
        submitted = st.form_submit_button("Finalize & PDF")
    if submitted:
        grand_total = sum(subtotals.values())
        total_down = down1 + down2
        remaining = grand_total - total_down
        installment = remaining / months if months else 0.0
        plan_id = payment_plan.add_student_plan(sid, None)
        for cat, opts in selections.items():
            for opt in opts:
                name = opt.split(' ($')[0]
                price = float(opt.split('$')[1].strip(')'))
                payment_plan.add_plan_item(plan_id, name, price, cat)
        payment_plan.add_plan_item(plan_id, "Down 1", down1, "Down Payment")
        payment_plan.add_plan_item(plan_id, "Down 2", down2, "Down Payment")
                # PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial','B',16)
        pdf.cell(0,10,f"Payment Plan for {sel_student}",ln=1)
        pdf.set_font('Arial','',12)
        pdf.cell(0,8,f"Date: {datetime.today().strftime('%Y-%m-%d')}",ln=1)
        pdf.ln(4)
        for cat,total in subtotals.items():
            pdf.cell(120,8,cat)
            pdf.cell(40,8,f"${total:.2f}",ln=1)
        pdf.ln(2)
        pdf.cell(120,8,"Total Down")
        pdf.cell(40,8,f"-${total_down:.2f}",ln=1)
        pdf.ln(2)
        pdf.set_font('Arial','B',12)
        pdf.cell(120,8,'Grand Total')
        pdf.cell(40,8,f"${grand_total:.2f}",ln=1)
        pdf.cell(120,8,'Remaining')
        pdf.cell(40,8,f"${remaining:.2f}",ln=1)
        pdf.cell(120,8,f"Installment ({months} mo)")
        pdf.cell(40,8,f"${installment:.2f}",ln=1)
        # Convert to bytes and download
        pdf_str = pdf.output(dest='S')
        data = pdf_str.encode('latin-1')
        st.success("Generated PDF")
        st.download_button(
            "Download PDF",
            data=data,
            file_name=f"Plan_{sel_student}.pdf",
            mime='application/pdf'
        )
else:
    st.info("Select a student to begin.")
    st.info("Select a student to begin.")
