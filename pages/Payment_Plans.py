import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
        # fpdf.output(dest='S') returns a string, so convert to bytes
        pdf_bytes = pdf.output(dest='S').encode('latin-1')
        st.success("Payment plan saved and PDF generated.")
        st.download_button(
            "Download PDF", data=pdf_bytes,
            file_name=f"PaymentPlan_{sel_student.replace(', ','_')}_{datetime.today().strftime('%Y%m%d')}.pdf",
            mime='application/pdf'
        )
elif menu: pass
    else:
        st.info("Select a student to begin building a plan.")
        st.info("Select a student to begin building a plan.")
