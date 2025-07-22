import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import os

# --- DATABASE SETUP ---
DB_PATH = "data/dance.db"
os.makedirs("data", exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# --- SCHEMA CREATION ---
c.execute("""
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    dob TEXT NOT NULL
);
""")

c.execute("""
CREATE TABLE IF NOT EXISTS dances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL
);
""")

c.execute("""
CREATE TABLE IF NOT EXISTS dance_students (
    dance_id INTEGER,
    student_id INTEGER,
    FOREIGN KEY (dance_id) REFERENCES dances(id),
    FOREIGN KEY (student_id) REFERENCES students(id),
    PRIMARY KEY (dance_id, student_id)
);
""")

conn.commit()

# --- FUNCTIONS ---
def add_student(first, last, dob):
    c.execute("INSERT INTO students (first_name, last_name, dob) VALUES (?, ?, ?)", (first, last, dob))
    conn.commit()

def get_all_students():
    return pd.read_sql("SELECT * FROM students", conn)

def import_students_from_df(df):
    for _, row in df.iterrows():
        if pd.notnull(row['First Name']) and pd.notnull(row['Last Name']) and pd.notnull(row['DOB']):
            add_student(row['First Name'], row['Last Name'], row['DOB'])

def add_dance(name, dtype, student_ids):
    c.execute("INSERT INTO dances (name, type) VALUES (?, ?)", (name, dtype))
    dance_id = c.lastrowid
    for sid in student_ids:
        c.execute("INSERT INTO dance_students (dance_id, student_id) VALUES (?, ?)", (dance_id, sid))
    conn.commit()

def get_all_dances():
    return pd.read_sql("SELECT * FROM dances", conn)

def get_students_for_dance(dance_id):
    return pd.read_sql("""
        SELECT s.* FROM students s
        JOIN dance_students ds ON s.id = ds.student_id
        WHERE ds.dance_id = ?
    """, conn, params=(dance_id,))

# --- UI ---
st.set_page_config(page_title="Dance Studio Manager", layout="wide")
menu = st.sidebar.selectbox("Navigate", ["📋 Students", "🕺 Dances", "🔍 Search"])

st.title("Dance Studio Manager")

if menu == "📋 Students":
    st.header("Manage Students")
    with st.form("add_student_form"):
        f_name = st.text_input("First Name")
        l_name = st.text_input("Last Name")
        dob = st.date_input("Date of Birth", min_value=date(1900, 1, 1))
        submit = st.form_submit_button("Add Student")
        if submit:
            add_student(f_name, l_name, dob.isoformat())
            st.success(f"Added {f_name} {l_name}")

    st.subheader("Import Students from CSV")
    csv = st.file_uploader("Upload CSV", type="csv")
    if csv:
        df = pd.read_csv(csv)
        st.dataframe(df)
        if st.button("Import Students"):
            import_students_from_df(df)
            st.success("Import complete.")

    st.subheader("All Students")
    st.dataframe(get_all_students())

elif menu == "🕺 Dances":
    st.header("Create Dance")
    with st.form("create_dance_form"):
        name = st.text_input("Dance Name")
        dtype = st.selectbox("Dance Type", ["Solo", "Duet", "Trio", "Group"])
        student_df = get_all_students()
        options = student_df.set_index("id").apply(lambda r: f"{r['first_name']} {r['last_name']}", axis=1).to_dict()
        selected = st.multiselect("Select Dancers", options=options)
        submit_dance = st.form_submit_button("Create Dance")
        if submit_dance:
            add_dance(name, dtype, selected)
            st.success(f"Created dance: {name}")

    st.subheader("All Dances")
    all_dances = get_all_dances()
    st.dataframe(all_dances)
    if st.checkbox("Show students per dance"):
        for _, row in all_dances.iterrows():
            st.markdown(f"**{row['name']} ({row['type']})**")
            dancers = get_students_for_dance(row['id'])
            st.dataframe(dancers[["first_name", "last_name", "dob"]])

elif menu == "🔍 Search":
    st.header("Search")
    search_term = st.text_input("Search by student name")
    if search_term:
        students = get_all_students()
        matches = students[students.apply(lambda r: search_term.lower() in f"{r['first_name']} {r['last_name']}".lower(), axis=1)]
        st.dataframe(matches)
        for _, row in matches.iterrows():
            st.markdown(f"### {row['first_name']} {row['last_name']}")
            st.markdown(f"**DOB**: {row['dob']}")
            st.markdown("**Dances:**")
            st.dataframe(pd.read_sql("""
                SELECT d.name, d.type FROM dances d
                JOIN dance_students ds ON ds.dance_id = d.id
                WHERE ds.student_id = ?
            """, conn, params=(row['id'],)))
