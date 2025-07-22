# app.py
import streamlit as st

st.set_page_config(page_title="Dance Studio Manager", layout="wide")

# Sidebar navigation
menu = st.sidebar.selectbox(
    "Navigate",
    ["📋 Students", "🕺 Dances", "🎟️ Events", "💰 Payment Plans", "🔍 Search"]
)

st.title("Dance Studio Manager")

# Page: Students
if menu == "📋 Students":
    st.header("Manage Students")
    st.subheader("Add a New Student")
    with st.form("add_student_form"):
        first_name = st.text_input("First Name")
        last_name = st.text_input("Last Name")
        dob = st.date_input("Date of Birth")
        submitted = st.form_submit_button("Add Student")
        if submitted:
            st.success(f"Added {first_name} {last_name}")

    st.subheader("Import Students from CSV")
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded_file:
        st.write("Preview:")
        st.dataframe(uploaded_file)

    st.subheader("All Students")
    st.info("List will show here once database is connected.")

# Page: Dances
elif menu == "🕺 Dances":
    st.header("Create and Assign Dances")
    st.info("Dance creation form goes here.")

# Page: Events
elif menu == "🎟️ Events":
    st.header("Manage Events")
    st.info("Add competitions, conventions, and classes here.")

# Page: Payment Plans
elif menu == "💰 Payment Plans":
    st.header("Generate Payment Plans")
    st.info("Payment calculator UI goes here.")

# Page: Search
elif menu == "🔍 Search":
    st.header("Search Students or Dances")
    st.info("Search and view summary details here.")
