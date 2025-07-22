import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF

# Shared DB path (same as main app)
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
DB_PATH = os.path.abspath(os.path.join(DATA_DIR, "dance.db"))
conn = sqlite3.connect(DB_PATH, check_same_thread=False)

import payment_plan

st.set_page_config(page_title="Payment Plans", layout="wide")
st.title("Payment Plans")

# --- Select Student ---
st.subheader("Select Student")
students = pd.read_sql(
    "SELECT id, first_name, last_name FROM students ORDER BY last_name, first_name", conn
)
student_map = {f"{row.last_name}, {row.first_name}": row.id for row in students.itertuples()}
sel_student = st.selectbox("Student", ["--"] + list(student_map.keys()))

if sel_student and sel_student != "--":
    sid = student_map[sel_student]
    # --- Payment Plan Form ---
    st.subheader("Build Payment Plan")
    with st.form("payment_plan_form"):
        # Subtotals
        tuition = st.number_input("Tuition Subtotal", min_value=0.0, format="%.2f")
        sdt = st.number_input("Solo/Duo/Trio Subtotal", min_value=0.0, format="%.2f")
        group = st.number_input("Group Subtotal", min_value=0.0, format="%.2f")
        comp = st.number_input("Competitions & Conventions Subtotal", min_value=0.0, format="%.2f")
        choreo = st.number_input("Choreography Subtotal", min_value=0.0, format="%.2f")
        costume = st.number_input("Costume Fees Subtotal", min_value=0.0, format="%.2f")
        admin = st.number_input("Administrative Fees Subtotal", min_value=0.0, format="%.2f")
        misc = st.number_input("Misc Fees Subtotal", min_value=0.0, format="%.2f")
        
        # Down payments
        st.markdown("---")
        st.subheader("Down Payments")
        down1 = st.number_input("Down Payment 1", min_value=0.0, format="%.2f")
        down2 = st.number_input("Down Payment 2", min_value=0.0, format="%.2f")
        
        # Frequency
        st.markdown("---")
        months = st.slider("Number of Months for Installments", 6, 10, 6)
        
        submit = st.form_submit_button("Finalize & Generate PDF")

    if submit:
        # Compute totals
        subtotals = {
            'Tuition': tuition,
            'Solo/Duo/Trio': sdt,
            'Groups': group,
            'Competitions & Conventions': comp,
            'Choreography': choreo,
            'Costume Fees': costume,
            'Administrative Fees': admin,
            'Miscellaneous Fees': misc,
        }
        grand_total = sum(subtotals.values())
        total_down = down1 + down2
        remaining = grand_total - total_down
        installment = remaining / months if months else 0.0

        # Persist into DB
        plan_id = payment_plan.add_student_plan(sid, None)
        for name, amt in subtotals.items():
            payment_plan.add_plan_item(plan_id, name, amt, name)
        payment_plan.add_plan_item(plan_id, 'Down Payment 1', down1, 'Down Payment')
        payment_plan.add_plan_item(plan_id, 'Down Payment 2', down2, 'Down Payment')

        # Generate PDF via FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, f"Payment Plan for {sel_student}", ln=1)
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 8, f"Date: {datetime.today().strftime('%Y-%m-%d')}", ln=1)
        pdf.ln(4)
        # List items
        for key, amt in subtotals.items():
            pdf.cell(120, 8, key, border=0)
            pdf.cell(40, 8, f"${amt:.2f}", ln=1, border=0)
        pdf.ln(2)
        pdf.cell(120, 8, 'Total Down Payments', border=0)
        pdf.cell(40, 8, f"-${total_down:.2f}", ln=1)
        pdf.ln(2)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(120, 8, 'Grand Total', border=0)
        pdf.cell(40, 8, f"${grand_total:.2f}", ln=1)
        pdf.cell(120, 8, 'Remaining Balance', border=0)
        pdf.cell(40, 8, f"${remaining:.2f}", ln=1)
        pdf.cell(120, 8, f"Installments ({months} months)", border=0)
        pdf.cell(40, 8, f"${installment:.2f}", ln=1)
        # Output PDF
        pdf_bytes = pdf.output(dest='S').encode('latin1')

        st.success("Payment plan saved and PDF generated.")
        st.download_button(
            "Download Payment Plan PDF", data=pdf_bytes,
            file_name=f"PaymentPlan_{sel_student.replace(', ','_')}_{datetime.today().strftime('%Y%m%d')}.pdf",
            mime='application/pdf'
        )

else:
    st.info("Select a student to begin.")
