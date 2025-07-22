import streamlit as st
import sqlite3
import pandas as pd
import os
import io
from fpdf import FPDF

# --- DATABASE CONNECTION ---
# Note: For this script to run standalone, you might need to adjust the path.
# Assuming 'data/dance.db' is in a sibling directory to the app's directory.
try:
    BASE_DIR = os.path.dirname(__file__)
    DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data"))
    DB_PATH = os.path.join(DATA_DIR, "dance.db")
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
except NameError:
    # If __file__ is not defined (e.g., in some notebooks), use a relative path
    if not os.path.exists("data"):
        os.makedirs("data")
    DB_PATH = os.path.join("data", "dance.db")
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)

c = conn.cursor()

# --- Placeholder tables/modules if they don't exist ---
# This ensures the script can be run for demonstration purposes.
c.execute('''
CREATE TABLE IF NOT EXISTS catalog_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    name TEXT,
    price REAL
)''')
c.execute('''
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT,
    last_name TEXT
)''')

# Mock payment_plan module for demonstration
class PaymentPlanModule:
    def add_student_plan(self, student_id, other_info):
        # In a real app, this would insert into a 'plans' table
        print(f"Creating plan for student_id: {student_id}")
        return 1 # return a mock plan_id
    def add_plan_item(self, plan_id, name, price, category):
        # In a real app, this would insert into a 'plan_items' table
        print(f"Adding to plan {plan_id}: {name}, {price}, {category}")

payment_plan = PaymentPlanModule()
# --- End of Placeholders ---

# --- HELPER FUNCTIONS ---
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

def generate_pdf(student_name, df_summary, grand_total, total_down, remaining, months, installment):
    """Generates a PDF summary of the payment plan."""
    pdf = FPDF()
    pdf.add_page()
    
    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Payment Plan for {student_name}", 0, 1, "C")
    pdf.ln(10)

    # --- Items Table ---
    pdf.set_font("Helvetica", "B", 12)
    # Table Header
    pdf.cell(130, 10, "Item", 1, 0, "C")
    pdf.cell(60, 10, "Price", 1, 1, "C")
    
    # Isolate items from down payments for the table body
    items_df = df_summary[~df_summary['Category'].str.contains("Down Payment")]
    
    # Table Body
    for category in items_df['Category'].unique():
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(190, 8, category, "LR", 1) 
        
        pdf.set_font("Helvetica", "", 11)
        category_items = items_df[items_df['Category'] == category]
        for _, row in category_items.iterrows():
            pdf.cell(130, 8, f"  {row['Item']}", "LR", 0)
            pdf.cell(60, 8, f"${row['Price']:.2f}", "R", 1, "R")

    # A line to close the table before totals
    pdf.cell(190, 0, "", "T", 1)
    pdf.ln(10)

    # --- Summary Totals ---
    pdf.set_font("Helvetica", "B", 12)
    
    def add_total_line(label, value_str):
        pdf.cell(130, 8, label, 0, 0, "R")
        pdf.cell(60, 8, value_str, 0, 1, "R")

    add_total_line("Grand Total:", f"${grand_total:.2f}")
    add_total_line("Total Down Payments:", f"${total_down:.2f}")
    pdf.line(pdf.get_x() + 135, pdf.get_y(), pdf.get_x() + 190, pdf.get_y()) # Underline
    add_total_line("Remaining Balance:", f"${remaining:.2f}")
    pdf.ln(5)
    
    pdf.set_font("Helvetica", "B", 13)
    add_total_line(f"Monthly Installment ({months} mo):", f"${installment:.2f}")

    # Use an in-memory buffer to ensure correct bytes output
    buffer = io.BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()


# --- UI ---
st.set_page_config(page_title="Payment Plans", layout="wide")
st.title("Payment Plans 💳")

with st.expander("Manage Item Catalog", expanded=False):
    fixed_categories = [
        "Tuition", "Solo/Duo/Trio", "Groups", "Competitions & Conventions",
        "Choreography", "Costume Fees", "Administrative Fees", "Miscellaneous Fees"
    ]
    existing = get_catalog_categories()
    categories = fixed_categories + [cat for cat in existing if cat not in fixed_categories]

    st.subheader("Add Catalog Item")
    category = st.selectbox("Category", categories, key="add_cat")
    item_name = st.text_input("Item Name", key="add_name")
    item_price = st.number_input("Item Price", min_value=0.0, format="%.2f", key="add_price")
    if st.button("Add Catalog Item", key="btn_add_item"):
        if category and item_name:
            add_catalog_item(category, item_name, item_price)
            st.success(f"Added '{item_name}' under '{category}'")
            st.rerun()
    st.markdown("---")

    st.subheader("Edit / Delete Catalog Item")
    edit_cat = st.selectbox("Select Category to Edit", categories, key="edit_cat")
    if edit_cat:
        items_df = get_catalog_items(edit_cat)
        item_map = {f"{row['name']} (${row['price']:.2f})": row['id'] for _, row in items_df.iterrows()}
        sel_item_display = st.selectbox("Select Item", ["--"] + list(item_map.keys()), key="edit_item")
        if sel_item_display and sel_item_display != "--":
            eid = item_map[sel_item_display]
            cur = items_df[items_df.id == eid].iloc[0]
            new_name = st.text_input("New Item Name", value=cur['name'], key="edit_name")
            new_price = st.number_input("New Item Price", value=cur['price'], min_value=0.0, format="%.2f", key="edit_price")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Update Item", key="btn_update_item", use_container_width=True):
                    c.execute("UPDATE catalog_items SET name=?, price=? WHERE id=?", (new_name, new_price, eid))
                    conn.commit()
                    st.success(f"Updated '{cur['name']}' -> '{new_name}'")
                    st.rerun()
            with col2:
                if st.button("Delete Item", type="primary", key="btn_delete_item", use_container_width=True):
                    c.execute("DELETE FROM catalog_items WHERE id=?", (eid,))
                    conn.commit()
                    st.warning(f"Deleted '{cur['name']}'")
                    st.rerun()
    st.markdown("---")

    for cat in categories:
        df_cat = get_catalog_items(cat)
        if not df_cat.empty:
            st.write(f"**{cat}**")
            st.table(df_cat[['name', 'price']])

# --- Select Student and Build Plan ---
st.subheader("Select Student")
students_df = pd.read_sql("SELECT id, first_name, last_name FROM students ORDER BY last_name, first_name", conn)
if students_df.empty:
    st.info("No students in the database. Adding a demo student.")
    c.execute("INSERT INTO students (first_name, last_name) VALUES (?, ?)", ("Jane", "Doe"))
    conn.commit()
    st.rerun()
    
student_map = {f"{r.last_name}, {r.first_name}": r.id for r in students_df.itertuples()}
sel_student = st.selectbox("Student", ["--"] + list(student_map.keys()), key="select_student")

if sel_student and sel_student != "--":
    sid = student_map[sel_student]
    st.header(f"Build Payment Plan for {sel_student}")

    with st.form("plan_form"):
        selections = {}
        subtotals = {}
        for cat in categories:
            df_items = get_catalog_items(cat)
            if not df_items.empty:
                options = [f"{row['name']} (${row['price']:.2f})" for _, row in df_items.iterrows()]
                sel_opts = st.multiselect(f"Select {cat}", options, key=f"sel_{cat}")
                total = sum(float(opt.split('$')[1].strip(')')) for opt in sel_opts)
                if total > 0:
                    st.write(f"*{cat} Subtotal: ${total:.2f}*")
                selections[cat] = sel_opts
                subtotals[cat] = total
        
        st.markdown("---")
        down1 = st.number_input("Down Payment 1", min_value=0.0, format="%.2f", key="down1")
        down2 = st.number_input("Down Payment 2", min_value=0.0, format="%.2f", key="down2")
        months = st.slider("Number of Months", min_value=1, max_value=12, value=10, key="months")
        
        submitted = st.form_submit_button("Finalize Plan")

    if submitted:
        grand_total = sum(subtotals.values())
        total_down = down1 + down2
        remaining = grand_total - total_down
        installment = remaining / months if months > 0 else 0.0
        
        plan_id = payment_plan.add_student_plan(sid, None)
        for cat, opts in selections.items():
            for opt in opts:
                name = opt.split(' ($')[0]
                price = float(opt.split('$')[1].strip(')'))
                payment_plan.add_plan_item(plan_id, name, price, cat)
        payment_plan.add_plan_item(plan_id, "Down Payment 1", down1, "Down Payment")
        payment_plan.add_plan_item(plan_id, "Down Payment 2", down2, "Down Payment")
        
        df_summary = pd.DataFrame([
            {"Category": cat, "Item": opt.split(' ($')[0], "Price": float(opt.split('$')[1].strip(')'))}
            for cat, opts in selections.items() for opt in opts
        ] + [
            {"Category": "Down Payment", "Item": "Down Payment 1", "Price": down1},
            {"Category": "Down Payment", "Item": "Down Payment 2", "Price": down2}
        ])
        df_summary = df_summary[df_summary['Price'] > 0]
        
        # 1. GENERATE PDF AND SAVE TO SESSION STATE
        st.session_state['pdf_bytes'] = generate_pdf(
            student_name=sel_student,
            df_summary=df_summary,
            grand_total=grand_total,
            total_down=total_down,
            remaining=remaining,
            months=months,
            installment=installment
        )
        st.session_state['pdf_filename'] = f"Payment_Plan_{sel_student.replace(', ', '_').replace(' ', '_')}.pdf"
        
        # Display summary on the page
        st.success("Payment plan saved. You can now download the PDF.")
        st.subheader("Plan Summary")
        st.dataframe(df_summary)
        st.markdown(f"**Grand Total:** ${grand_total:.2f}")
        st.markdown(f"**Total Down Payments:** ${total_down:.2f}")
        st.markdown(f"**Remaining Balance:** ${remaining:.2f}")
        st.markdown(f"**Installment ({months} mo):** ${installment:.2f}")

    # 2. DISPLAY DOWNLOAD BUTTON IF PDF EXISTS IN SESSION STATE
    if 'pdf_bytes' in st.session_state:
        st.download_button(
            label="Download Plan as PDF 📄",
            data=st.session_state['pdf_bytes'],
            file_name=st.session_state['pdf_filename'],
            mime="application/pdf"
        )
else:
    # Clear session state if no student is selected
    if 'pdf_bytes' in st.session_state:
        del st.session_state['pdf_bytes']
    if 'pdf_filename' in st.session_state:
        del st.session_state['pdf_filename']
    st.info("Select a student to begin.")