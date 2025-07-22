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

def update_student(sid, first, last, dob):
    c.execute("UPDATE students SET first_name=?, last_name=?, dob=? WHERE id=?", (first, last, dob, sid))
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

def update_dance_members(did, student_ids):
    c.execute("DELETE FROM dance_students WHERE dance_id=?", (did,))
    for sid in student_ids:
        c.execute("INSERT INTO dance_students (dance_id, student_id) VALUES (?, ?)", (did, sid))
    conn.commit()

def get_all_dances():
    return pd.read_sql("SELECT * FROM dances ORDER BY type, name", conn)

def get_dances_for_student(sid):
    return pd.read_sql(
        "SELECT d.name, d.type FROM dances d JOIN dance_students ds ON d.id=ds.dance_id WHERE ds.student_id=?", conn, params=(sid,))

def get_students_for_dance(did):
    return pd.read_sql(
        "SELECT s.first_name, s.last_name FROM students s JOIN dance_students ds ON s.id=ds.student_id WHERE ds.dance_id=?", conn, params=(did,))

def add_competition(name, has_conv, student_ids):
    c.execute("INSERT INTO competitions (name, has_convention) VALUES (?, ?)", (name, has_conv))
    cid = c.lastrowid
    for sid in student_ids:
        c.execute("INSERT OR IGNORE INTO competition_students (competition_id, student_id) VALUES (?, ?)", (cid, sid))
    conn.commit()

def update_competition_members(cid, student_ids):
    c.execute("DELETE FROM competition_students WHERE competition_id=?", (cid,))
    for sid in student_ids:
        c.execute("INSERT INTO competition_students (competition_id, student_id) VALUES (?, ?)", (cid, sid))
    conn.commit()

def get_all_competitions():
    return pd.read_sql("SELECT * FROM competitions ORDER BY name", conn)

def get_competitions_for_student(sid):
    return pd.read_sql(
        "SELECT c.name, c.has_convention FROM competitions c JOIN competition_students cs ON c.id=cs.competition_id WHERE cs.student_id=?", conn, params=(sid,))

def get_students_for_competition(cid):
    return pd.read_sql(
        "SELECT s.first_name, s.last_name FROM students s JOIN competition_students cs ON s.id=cs.student_id WHERE cs.competition_id=?", conn, params=(cid,))

# --- UI SETUP ---
st.set_page_config(page_title="Dance Studio Manager", layout="wide")
menu = st.sidebar.selectbox("Navigate", ["📋 Students", "🕺 Dances", "🏆 Competitions"])
st.title("Dance Studio Manager")

# Preload data
students_df = get_all_students()
student_map = {f"{r['last_name']}, {r['first_name']}": r['id'] for _,r in students_df.iterrows()}
dance_df = get_all_dances()
dance_types = ["Solo","Duet","Trio","Group"]
compet_df = get_all_competitions()
compet_map = {r['name']:r['id'] for _,r in compet_df.iterrows()}

# --- STUDENTS PAGE ---
if menu == "📋 Students":
    with st.expander("Manage Students", expanded=True):
        # Add student
        with st.form("add_student_form"):
            fn = st.text_input("First Name")
            ln = st.text_input("Last Name")
            dob = st.date_input("Date of Birth", min_value=date(1900,1,1))
            if st.form_submit_button("Add Student"):
                add_student(fn, ln, dob.isoformat())
                st.experimental_rerun()
        # Edit student
        sel = st.selectbox("Select Student to Edit", ["--"]+list(student_map.keys()), key="edit_student_sel")
        if sel != "--":
            sid = student_map[sel]
            stu = students_df[students_df.id==sid].iloc[0]
            with st.form("edit_student_form"):
                fn2 = st.text_input("First Name", value=stu['first_name'])
                ln2 = st.text_input("Last Name", value=stu['last_name'])
                dob2 = st.date_input("Date of Birth", value=pd.to_datetime(stu['dob']), min_value=date(1900,1,1))
                if st.form_submit_button("Update Student"):
                    update_student(sid, fn2, ln2, dob2.isoformat())
                    st.experimental_rerun()
    st.markdown("---")
    # Profile view
    sel2 = st.selectbox("View Student Profile", ["--"]+list(student_map.keys()), key="view_student")
    if sel2 != "--":
        sid = student_map[sel2]
        stu = students_df[students_df.id==sid].iloc[0]
        st.subheader(f"{stu['first_name']} {stu['last_name']}")
        st.write(f"**DOB:** {stu['dob']}")
        # Dances and competitions
        st.write("**Dances:**")
        dd = get_dances_for_student(sid)
        st.write(dd if not dd.empty else "No dances.")
        st.write("**Competitions:**")
        cd = get_competitions_for_student(sid)
        cd['has_convention'] = cd['has_convention'].map({0:'No',1:'Yes'})
        st.write(cd if not cd.empty else "No competitions.")

# --- DANCES PAGE ---
elif menu == "🕺 Dances":
    with st.expander("Create/Edit Dances", expanded=True):
        cols = st.columns(2)
        with cols[0]:
            st.subheader("Create Dance")
            for dtype in dance_types:
                name = st.text_input(f"{dtype} Name", key=f"new_{dtype}")
                sel = st.multiselect(f"Select {dtype} Students", options=list(student_map.keys()), key=f"new_{dtype}_sel")
                if st.button(f"Create {dtype}", key=f"btn_new_{dtype}"):
                    add_dance(name, dtype, [student_map[s] for s in sel])
                    st.success(f"{dtype} '{name}' created.")
        with cols[1]:
            st.subheader("Edit Dance Members")
            choice = st.selectbox("Select Dance to Edit", ["--"]+list({f"{r['type']}: {r['name']}":r['id'] for _,r in dance_df.iterrows()}.keys()), key="edit_dance_sel")
            if choice != "--":
                did = {f"{r['type']}: {r['name']}":r['id'] for _,r in dance_df.iterrows()}[choice]
                members = get_students_for_dance(did)
                curr = [f"{r['last_name']}, {r['first_name']}" for _,r in members.iterrows()]
                selm = st.multiselect("Members", options=list(student_map.keys()), default=curr, key="edit_dance_mem")
                if st.button("Update Members", key="btn_edit_dance"):
                    update_dance_members(did, [student_map[s] for s in selm])
                    st.success("Dance updated.")
    for dtype in dance_types:
        dances = dance_df[dance_df.type==dtype].sort_values('name')
        with st.expander(dtype + " List", expanded=False):
            if dances.empty:
                st.write("No dances.")
            else:
                for _,d in dances.iterrows():
                    label = d['name']
                    if dtype != 'Solo':
                        if st.button(label, key=f"view_dance_{d['id']}"):
                            mem = get_students_for_dance(d['id'])
                            st.write(mem)
                    else:
                        st.write(label)

# --- COMPETITIONS PAGE ---
elif menu == "🏆 Competitions":
    with st.expander("Create/Edit Competitions", expanded=True):
        colc = st.columns(2)
        with colc[0]:
            st.subheader("Create Competition")
            name = st.text_input("Name", key="new_comp")
            conv = st.checkbox("Includes Convention", key="new_comp_conv")
            selc = st.multiselect("Select Students", options=list(student_map.keys()), key="new_comp_sel")
            if st.button("Create Competition", key="btn_new_comp"):
                add_competition(name, int(conv), [student_map[s] for s in selc])
                st.success(f"Competition '{name}' created.")
        with colc[1]:
            st.subheader("Edit Competition Members")
            choice = st.selectbox("Select Competition to Edit", ["--"]+list(compet_map.keys()), key="edit_comp_sel")
            if choice != "--":
                cid = compet_map[choice]
                mem = get_students_for_competition(cid)
                currc = [f"{r['last_name']}, {r['first_name']}" for _,r in mem.iterrows()]
                selc2 = st.multiselect("Members", options=list(student_map.keys()), default=currc, key="edit_comp_members")
                if st.button("Update Competition", key="btn_edit_comp"):
                    update_competition_members(cid, [student_map[s] for s in selc2])
                    st.success("Competition updated.")
    comps = compet_df.sort_values('name')
    with st.expander("Competitions List", expanded=False):
        if comps.empty:
            st.write("No competitions.")
        else:
            for _,c in comps.iterrows():
                if st.button(c['name'], key=f"view_comp_{c['id']}"):
                    studs = get_students_for_competition(c['id'])
                    st.write(studs)
