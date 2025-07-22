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
    PRIMARY KEY (dance_id, student_id),
    FOREIGN KEY (dance_id) REFERENCES dances(id),
    FOREIGN KEY (student_id) REFERENCES students(id)
);
""")
c.execute("""
CREATE TABLE IF NOT EXISTS competitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    has_convention INTEGER NOT NULL CHECK (has_convention IN (0,1))
);
""")
c.execute("""
CREATE TABLE IF NOT EXISTS competition_students (
    competition_id INTEGER,
    student_id INTEGER,
    PRIMARY KEY (competition_id, student_id),
    FOREIGN KEY (competition_id) REFERENCES competitions(id),
    FOREIGN KEY (student_id) REFERENCES students(id)
);
""")
conn.commit()

# --- DATABASE FUNCTIONS ---
def add_student(first, last, dob):
    c.execute("INSERT INTO students (first_name, last_name, dob) VALUES (?, ?, ?)", (first, last, dob))
    conn.commit()

def get_all_students():
    return pd.read_sql("SELECT * FROM students ORDER BY last_name, first_name", conn)

def import_students_from_df(df):
    for _, row in df.iterrows():
        add_student(row['First Name'], row['Last Name'], row['DOB'])

def add_dance(name, dtype, student_ids):
    c.execute("INSERT INTO dances (name, type) VALUES (?, ?)", (name, dtype))
    dance_id = c.lastrowid
    for sid in student_ids:
        c.execute("INSERT OR IGNORE INTO dance_students (dance_id, student_id) VALUES (?, ?)", (dance_id, sid))
    conn.commit()

def update_dance_members(dance_id, student_ids):
    c.execute("DELETE FROM dance_students WHERE dance_id = ?", (dance_id,))
    for sid in student_ids:
        c.execute("INSERT INTO dance_students (dance_id, student_id) VALUES (?, ?)", (dance_id, sid))
    conn.commit()

def get_all_dances():
    return pd.read_sql("SELECT * FROM dances ORDER BY type, name", conn)

def get_students_for_dance(dance_id):
    return pd.read_sql("""
        SELECT s.* FROM students s
        JOIN dance_students ds ON s.id = ds.student_id
        WHERE ds.dance_id = ?
    """, conn, params=(dance_id,))

def get_dances_for_student(student_id):
    return pd.read_sql("""
        SELECT d.name, d.type FROM dances d
        JOIN dance_students ds ON d.id = ds.dance_id
        WHERE ds.student_id = ?
    """, conn, params=(student_id,))

def add_competition(name, has_convention, student_ids):
    c.execute("INSERT INTO competitions (name, has_convention) VALUES (?, ?)", (name, has_convention))
    comp_id = c.lastrowid
    for sid in student_ids:
        c.execute("INSERT OR IGNORE INTO competition_students (competition_id, student_id) VALUES (?, ?)", (comp_id, sid))
    conn.commit()

def update_competition_members(comp_id, student_ids):
    c.execute("DELETE FROM competition_students WHERE competition_id = ?", (comp_id,))
    for sid in student_ids:
        c.execute("INSERT INTO competition_students (competition_id, student_id) VALUES (?, ?)", (comp_id, sid))
    conn.commit()

def get_all_competitions():
    return pd.read_sql("SELECT * FROM competitions ORDER BY name", conn)

def get_competitions_for_student(student_id):
    return pd.read_sql("""
        SELECT c.name, c.has_convention FROM competitions c
        JOIN competition_students cs ON c.id = cs.competition_id
        WHERE cs.student_id = ?
    """, conn, params=(student_id,))

# --- UI SETUP ---
st.set_page_config(page_title="Dance Studio Manager", layout="wide")
menu = st.sidebar.selectbox("Navigate", ["📋 Students", "🕺 Dances", "🏆 Competitions", "🔍 Search"])
st.title("Dance Studio Manager")

# Preload data for selectors
students_df = get_all_students()
student_options = {f"{r['last_name']}, {r['first_name']}": r['id'] for _, r in students_df.iterrows()}

dance_df = get_all_dances()
dance_options = {f"{r['type']}: {r['name']}": r['id'] for _, r in dance_df.iterrows()}

compet_df = get_all_competitions()
compet_options = {r['name']: r['id'] for _, r in compet_df.iterrows()}

# --- STUDENTS PAGE ---
if menu == "📋 Students":
    st.header("Manage Students")
    with st.form("add_student_form"):
        f_name = st.text_input("First Name")
        l_name = st.text_input("Last Name")
        dob = st.date_input("Date of Birth", min_value=date(1900,1,1))
        if st.form_submit_button("Add Student"):
            add_student(f_name, l_name, dob.isoformat())
            st.experimental_rerun()

    st.subheader("All Students")
    selected = st.selectbox("Select Student", ["--"] + list(student_options.keys()))
    if selected != "--":
        sid = student_options[selected]
        student = students_df[students_df.id == sid].iloc[0]
        st.markdown(f"## {student['first_name']} {student['last_name']}")
        st.markdown(f"**DOB:** {student['dob']}")
        # Show related dances
        st.markdown("### Dances")
        sd = get_dances_for_student(sid)
        st.dataframe(sd if not sd.empty else pd.DataFrame([{"Info":"No dances assigned"}]))
        # Show related competitions
        st.markdown("### Competitions")
        sc = get_competitions_for_student(sid)
        sc['has_convention'] = sc['has_convention'].map({0:'No',1:'Yes'})
        st.dataframe(sc if not sc.empty else pd.DataFrame([{"Info":"No competitions assigned"}]))

# --- DANCES PAGE ---
elif menu == "🕺 Dances":
    st.header("Dances")
    tabs = st.tabs(["Create", "Edit"])
    # Create
    with tabs[0]:
        st.subheader("Create Dance by Type")
        for dtype in ["Solo","Duet","Trio","Group"]:
            with st.expander(dtype):
                name = st.text_input(f"{dtype} Name", key=f"name_{dtype}")
                selected = st.multiselect("Select Students", options=list(student_options.keys()), key=f"students_{dtype}")
                if st.button(f"Create {dtype}", key=f"create_{dtype}"):
                    add_dance(name, dtype, [student_options[s] for s in selected])
                    st.success(f"{dtype} '{name}' created.")
    # Edit
    with tabs[1]:
        st.subheader("Edit Dance Members")
        choice = st.selectbox("Select Dance", ["--"] + list(dance_options.keys()))
        if choice != "--":
            did = dance_options[choice]
            members = get_students_for_dance(did)
            current = [f"{r['last_name']}, {r['first_name']}" for _,r in members.iterrows()]
            selected = st.multiselect("Members", options=list(student_options.keys()), default=current)
            if st.button("Update Members", key="upd_dance"):
                update_dance_members(did, [student_options[s] for s in selected])
                st.success("Members updated.")

# --- COMPETITIONS PAGE ---
elif menu == "🏆 Competitions":
    st.header("Competitions")
    tabs = st.tabs(["Create", "Edit"])
    with tabs[0]:
        st.subheader("Create Competition")
        comp = st.text_input("Competition Name", key="comp_name")
        conv = st.checkbox("Includes Convention", key="comp_conv")
        sel = st.multiselect("Select Students", options=list(student_options.keys()), key="comp_students")
        if st.button("Create Competition", key="create_comp"):
            add_competition(comp, int(conv), [student_options[s] for s in sel])
            st.success(f"Competition '{comp}' created.")
    with tabs[1]:
        st.subheader("Edit Competition Members")
        choice = st.selectbox("Select Competition", ["--"] + list(compet_options.keys()), key="edit_comp_select")
        if choice != "--":
            cid = compet_options[choice]
            mem = pd.read_sql("SELECT s.first_name, s.last_name FROM students s JOIN competition_students cs ON s.id=cs.student_id WHERE cs.competition_id=?", conn, params=(cid,))
            current = [f"{r['last_name']}, {r['first_name']}" for _,r in mem.iterrows()]
            sel = st.multiselect("Members", options=list(student_options.keys()), default=current, key="edit_comp_members")
            if st.button("Update Competition", key="upd_comp"):
                update_competition_members(cid, [student_options[s] for s in sel])
                st.success("Competition updated.")

# --- SEARCH PAGE ---
elif menu == "🔍 Search":
    st.header("Search Students")
    term = st.text_input("Name Contains")
    if term:
        df = students_df[students_df.apply(lambda r: term.lower() in (r['first_name']+" "+r['last_name']).lower(), axis=1)]
        st.dataframe(df)
        for _, row in df.iterrows():
            st.markdown(f"**{row['first_name']} {row['last_name']}**")
            sd = get_dances_for_student(row['id'])
            st.markdown("Dances:")
            st.write(sd)
            sc = get_competitions_for_student(row['id'])
            st.markdown("Competitions:")
            st.write(sc)
