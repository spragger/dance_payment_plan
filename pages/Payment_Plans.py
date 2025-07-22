import streamlit as st
import sqlite3
import pandas as pd
import os
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT


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
def show_print_button():
    """Adds a button with specific CSS to trigger the browser's print dialog."""
    print_button_html = """
    <style>
    /* CSS for the button itself (on screen) */
    @media screen {
        .print-button {
            background-color: #007bff;
            border: none;
            color: white;
            padding: 15px 32px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 20px 2px;
            cursor: pointer;
            border-radius: 8px;
        }
    }

    /* CSS for printing */
    @media print {
        /* Hide everything by default */
        body * {
            visibility: hidden;
        }

        /* Hide Streamlit's default header, sidebar, and toolbar */
        [data-testid="stHeader"], [data-testid="stSidebar"], .st-emotion-cache-1v0mbdj, .st-emotion-cache-1oe5cao {
            display: none !important;
        }

        /* Make only the main content area visible */
        .main .block-container, .main .block-container * {
            visibility: visible;
        }

        /* Position the main content at the top-left of the print page */
        .main .block-container {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
        }
    }
    </style>
    
    <button onclick="window.print()" class="print-button">
        🖨️ Print or Save as PDF
    </button>
    """
    st.components.v1.html(print_button_html, height=100)

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
    """Generates a PDF summary using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    styles = getSampleStyleSheet()

    # Add a centered title style
    styles.add(ParagraphStyle(name='Center', alignment=TA_CENTER))

    # Create the story (the flow of content)
    story = []

    # Title
    story.append(Paragraph(f"Payment Plan for {student_name}", styles['h1']))
    story.append(Spacer(1, 12))

    # --- Items Section ---
    items_df = df_summary[~df_summary['Category'].str.contains("Down Payment")]
    for category in items_df['Category'].unique():
        story.append(Paragraph(category, styles['h2']))
        
        table_data = [['Item', 'Price']]
        category_items = items_df[items_df['Category'] == category]
        for _, row in category_items.iterrows():
            # Format price as string
            price_str = f"${row['Price']:,.2f}"
            table_data.append([Paragraph(row['Item'], styles['BodyText']), price_str])
        
        # Create and style the table
        item_table = Table(table_data, colWidths=[350, 100])
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('ALIGN', (1,1), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.white),
            ('GRID', (0,0), (-1,-1), 1, colors.lightgrey)
        ]))
        story.append(item_table)
        story.append(Spacer(1, 12))

    # --- Summary Section ---
    story.append(Paragraph("Plan Summary", styles['h2']))
    summary_data = [
        ['Grand Total:', f'${grand_total:,.2f}'],
        ['Total Down Payments:', f'${total_down:,.2f}'],
        ['Remaining Balance:', f'${remaining:,.2f}'],
        [Paragraph(f'<b>Monthly Installment ({months} mo):</b>', styles['BodyText']), f'<b>${installment:,.2f}</b>'],
    ]
    summary_table = Table(summary_data, colWidths=[200, 100])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('FONTNAME', (0,3), (-1,3), 'Helvetica-Bold'), # Make last row bold
    ]))
    story.append(summary_table)

    # Build the PDF
    doc.build(story)
    
    # Get the value of the BytesIO buffer and return it
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

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
# 2. DISPLAY PRINT BUTTON IF A PLAN HAS BEEN FINALIZED
    if submitted or 'pdf_bytes' in st.session_state:
        # We can reuse the session state flag to know a plan is ready.
        show_print_button()

else:
    # Clear session state if no student is selected
    if 'pdf_bytes' in st.session_state:
        del st.session_state['pdf_bytes']
    if 'pdf_filename' in st.session_state:
        del st.session_state['pdf_filename']
    st.info("Select a student to begin.")