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
    fixed_categories = [
        "Tuition", "Solo/Duo/Trio", "Groups", "Competitions & Conventions",
        "Choreography", "Costume Fees", "Administrative Fees", "Miscellaneous Fees"
    ]
    existing = get_catalog_categories()
    categories = fixed_categories + [cat for cat in existing if cat not in fixed_categories]

    # Add new item
    st.subheader("Add Catalog Item")
    category = st.selectbox("Category", categories, key="add_cat")
    item_name = st.text_input("Item Name", key="add_name")
    item_price = st.number_input("Item Price", min_value=0.0, format="%.2f", key="add_price")
    if st.button("Add Catalog Item", key="btn_add_item"):
        if category and item_name:
            add_catalog_item(category, item_name, item_price)
            st.success(f"Added '{item_name}' under '{category}'")
    st.markdown("---")

    # Edit or Delete existing item
    st.subheader("Edit / Delete Catalog Item")
    edit_cat = st.selectbox("Select Category to Edit", categories, key="edit_cat")
    items_df = get_catalog_items(edit_cat)
    item_map = {row['name']: row['id'] for _, row in items_df.iterrows()}
    sel_item = st.selectbox("Select Item", ["--"] + list(item_map.keys()), key="edit_item")
    if sel_item and sel_item != "--":
        eid = item_map[sel_item]
        cur = items_df[items_df.id == eid].iloc[0]
        new_name = st.text_input("New Item Name", value=cur['name'], key="edit_name")
        new_price = st.number_input("New Item Price", value=cur['price'], min_value=0.0, format="%.2f", key="edit_price")
        if st.button("Update Item", key="btn_update_item"):
            c.execute("UPDATE catalog_items SET name=?, price=? WHERE id=?", (new_name, new_price, eid))
            conn.commit()
            st.success(f"Updated '{sel_item}' -> '{new_name}'")
        if st.button("Delete Item", key="btn_delete_item"):
            c.execute("DELETE FROM catalog_items WHERE id=?", (eid,))
            conn.commit()
            st.success(f"Deleted '{sel_item}'")
    st.markdown("---")

    # Display catalog
    for cat in categories:
        df_cat = get_catalog_items(cat)
        if not df_cat.empty:
            st.write(f"**{cat}**")
            st.table(df_cat[['name', 'price']])

# --- Select Student ---
st.subheader("Select Student")
students_df = pd.read_sql("SELECT id, first_name, last_name FROM students ORDER BY last_name, first_name", conn)
student_map = {f"{r.last_name}, {r.first_name}": r.id for r in students_df.itertuples()}
sel_student = st.selectbox("Student", ["--"] + list(student_map.keys()), key="select_student")

if sel_student and sel_student != "--":
    sid = student_map[sel_student]
    st.header(f"Build Payment Plan for {sel_student}")
    with st.form("plan_form"):
        selections = {}
        subtotals = {}
        # Selection sections
        for cat in categories:
            df_items = get_catalog_items(cat)
            options = [f"{row['name']} (${row['price']:.2f})" for _, row in df_items.iterrows()]
            sel_opts = st.multiselect(f"Select {cat}", options, key=f"sel_{cat}")
            total = sum(float(opt.split('$')[1].strip(')')) for opt in sel_opts)
            st.write(f"{cat} Subtotal: ${total:.2f}")
            selections[cat] = sel_opts
            subtotals[cat] = total
        # Down payments and months
        st.markdown("---")
        down1 = st.number_input("Down Payment 1", min_value=0.0, format="%.2f", key="down1")
        down2 = st.number_input("Down Payment 2", min_value=0.0, format="%.2f", key="down2")
        months = st.slider("Number of Months", min_value=6, max_value=10, value=6, key="months")
        submitted = st.form_submit_button("Finalize & Generate PDF")

    if submitted:
        # Calculate totals
        grand_total = sum(subtotals.values())
        total_down = down1 + down2
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
                # Generate PDF using ReportLab
        from io import BytesIO
        from reportlab.pdfgen import canvas
        buffer = BytesIO()
        p = canvas.Canvas(buffer)
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, 800, f"Payment Plan for {sel_student}")
        p.setFont("Helvetica", 12)
        p.drawString(50, 780, f"Date: {datetime.today().strftime('%Y-%m-%d')}")
        y = 760
        for cat, total in subtotals.items():
            p.drawString(50, y, f"{cat}:")
            p.drawRightString(550, y, f"${total:.2f}")
            y -= 20
        y -= 10
        p.drawString(50, y, "Total Down Payments:")
        p.drawRightString(550, y, f"-${total_down:.2f}")
        y -= 20
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, "Grand Total:")
        p.drawRightString(550, y, f"${grand_total:.2f}")
        y -= 20
        p.drawString(50, y, "Remaining Balance:")
        p.drawRightString(550, y, f"${remaining:.2f}")
        y -= 20
        p.drawString(50, y, f"Installment ({months} mo):")
        p.drawRightString(550, y, f"${installment:.2f}")
        p.showPage()
        p.save()
        buffer.seek(0)
        pdf_bytes = buffer.read()
        st.success("Generated PDF")
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=f"PaymentPlan_{sel_student.replace(', ','_')}_{datetime.today().strftime('%Y%m%d')}.pdf",
            mime='application/pdf'
        )(
            "Download PDF",
            data=data,
            file_name=f"PaymentPlan_{sel_student.replace(', ','_')}_{datetime.today().strftime('%Y%m%d')}.pdf",
            mime='application/pdf'
        )
else:
    st.info("Select a student to begin.")
    st.info("Select a student to begin.")
