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
for stmt in [
    """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    dob TEXT NOT NULL
);""",
    """
CREATE TABLE IF NOT EXISTS dances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL
);""",
    """
CREATE TABLE IF NOT EXISTS dance_students (
    dance_id INTEGER,
    student_id INTEGER,
    PRIMARY KEY (dance_id, student_id),
    FOREIGN KEY (dance_id) REFERENCES dances(id),
    FOREIGN KEY (student_id) REFERENCES students(id)
);""",
    """
CREATE TABLE IF NOT EXISTS competitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    has_convention INTEGER NOT NULL CHECK (has_convention IN (0,1))
);""",
    """
CREATE TABLE IF NOT EXISTS competition_students (
    competition_id INTEGER,
    student_id INTEGER,
    PRIMARY KEY (competition_id, student_id),
    FOREIGN KEY (competition_id) REFERENCES competitions(id),
    FOREIGN KEY (student_id) REFERENCES students(id)
);"""
]:
    c.execute(stmt)
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

def get_students_for_dance(did):
    return pd.read_sql(
        "SELECT s.first_name, s.last_name FROM students s JOIN dance_students ds ON s.id=ds.student_id WHERE ds.dance_id=?", conn, params=(did,))

def get_dances_for_student(sid):
    return pd.read_sql(
        "SELECT d.name, d.type FROM dances d JOIN dance_students ds ON d.id=ds.dance_id WHERE ds.student_id=?", conn, params=(sid,))

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

def get_students_for_competition(cid):
    return pd.read_sql(
        "SELECT s.first_name, s.last_name FROM students s JOIN competition_students cs ON s.id=cs.student_id WHERE cs.competition_id=?", conn, params=(cid,))

# --- STREAMLIT UI ---
st.set_page_config(page_title="Dance Studio Manager", layout="wide")
menu = st.sidebar.selectbox("Navigate", ["📋 Students", "🕺 Dances", "🏆 Competitions"])
st.title("Dance Studio Manager")

# --- STUDENTS PAGE ---
if menu == "📋 Students":
    with st.expander("Manage Students", expanded=False):
        # Add Student Form
        with st.form("add_student_form"):
            fn = st.text_input("First Name")
            ln = st.text_input("Last Name")
            dob = st.date_input("Date of Birth", min_value=date(1900,1,1))
            if st.form_submit_button("Add Student"):
                add_student(fn, ln, dob.isoformat())
                st.success(f"Added {fn} {ln}")
        # Edit Student Form
        students_df = get_all_students()
        student_map = {f"{r['last_name']}, {r['first_name']}": r['id'] for _,r in students_df.iterrows()}
        sel = st.selectbox("Select Student to Edit", ["--"] + list(student_map.keys()))
        if sel and sel != "--":
            sid = student_map[sel]
            stu = students_df[students_df.id==sid].iloc[0]
            with st.form("edit_student_form"):
                fn2 = st.text_input("First Name", value=stu['first_name'])
                ln2 = st.text_input("Last Name", value=stu['last_name'])
                dob2 = st.date_input("Date of Birth", value=pd.to_datetime(stu['dob']), min_value=date(1900,1,1))
                if st.form_submit_button("Update Student"):
                    update_student(sid, fn2, ln2, dob2.isoformat())
                    st.success(f"Updated {fn2} {ln2}")
    st.markdown("---")
    # Profile Viewer
    students_df = get_all_students()
    student_map = {f"{r['last_name']}, {r['first_name']}": r['id'] for _,r in students_df.iterrows()}
    sel2 = st.selectbox("View Student Profile", ["--"] + list(student_map.keys()))
    if sel2 and sel2 != "--":
        sid = student_map[sel2]
        stu = students_df[students_df.id==sid].iloc[0]
        st.subheader(f"{stu['first_name']} {stu['last_name']}")
        st.write(f"**DOB:** {stu['dob']}")
        st.write("**Dances:**")
        dd = get_dances_for_student(sid)
        st.write(dd if not dd.empty else "No dances.")
        st.write("**Competitions:**")
        cd = get_all_competitions()
        cc = pd.read_sql(
            "SELECT c.name, c.has_convention FROM competitions c JOIN competition_students cs ON c.id=cs.competition_id WHERE cs.student_id=?", conn, params=(sid,))
        cc['has_convention'] = cc['has_convention'].map({0:'No',1:'Yes'})
        st.write(cc if not cc.empty else "No competitions.")

# --- DANCES PAGE ---
elif menu == "🕺 Dances":
    dance_df = get_all_dances()
    dance_types = ["Solo","Duet","Trio","Group"]
    students_df = get_all_students()
    student_map = {f"{r['last_name']}, {r['first_name']}": r['id'] for _,r in students_df.iterrows()}

    with st.expander("Create/Edit Dances", expanded=True):
        cols = st.columns(2)
        with cols[0]:
            for dtype in dance_types:
                with st.expander(f"Create {dtype}"):
                    name = st.text_input("Name", key=f"new_{dtype}")
                    sel = st.multiselect("Students", options=list(student_map.keys()), key=f"new_{dtype}_sel")
                    if st.button(f"Add {dtype}", key=f"btn_new_{dtype}"):
                        add_dance(name, dtype, [student_map[s] for s in sel])
                        st.success(f"{dtype} '{name}' created.")
        with cols[1]:
            with st.expander("Edit Dances"):
                options = {f"{r['type']}: {r['name']}":r['id'] for _,r in dance_df.iterrows()}
                choice = st.selectbox("Select Dance", ["--"]+list(options.keys()))
                if choice and choice != "--":
                    did = options[choice]
                    members = get_students_for_dance(did)
                    curr = [f"{r['last_name']}, {r['first_name']}" for _,r in members.iterrows()]
                    selm = st.multiselect("Members", options=list(student_map.keys()), default=curr)
                    if st.button("Update", key="upd_dance"):
                        update_dance_members(did, [student_map[s] for s in selm])
                        st.success("Updated.")
    # Lists by type
    for dtype in dance_types:
        sub = dance_df[dance_df.type==dtype].sort_values('name')
        with st.expander(f"{dtype} List", expanded=False):
            if sub.empty:
                st.write("No dances.")
            else:
                for _,d in sub.iterrows():
                    if dtype=='Solo':
                        st.write(d['name'])
                    else:
                        if st.button(d['name'], key=f"view_dance_{d['id']}"):
                            st.write(get_students_for_dance(d['id']))

# --- COMPETITIONS PAGE ---
elif menu == "🏆 Competitions":
    compet_df = get_all_competitions()
    students_df = get_all_students()
    student_map = {f"{r['last_name']}, {r['first_name']}": r['id'] for _,r in students_df.iterrows()}
    compet_map = {r['name']:r['id'] for _,r in compet_df.iterrows()}

    with st.expander("Create/Edit Competitions", expanded=True):
        cols = st.columns(2)
        with cols[0]:
            with st.expander("Create Competition"):
                name = st.text_input("Name", key="new_comp")
                conv = st.checkbox("Convention Included", key="new_comp_conv")
                sel = st.multiselect("Students", options=list(student_map.keys()), key="new_comp_sel")
                if st.button("Add Competition", key="btn_new_comp"):
                    add_competition(name, int(conv), [student_map[s] for s in sel])
                    st.success(f"Competition '{name}' added.")
        with cols[1]:
            with st.expander("Edit Competition"):
                choice = st.selectbox("Select Competition", ["--"]+list(compet_map.keys()), key="edit_comp")
                if choice and choice!="--":
                    cid = compet_map[choice]
                    mem = get_students_for_competition(cid)
                    curr = [f"{r['last_name']}, {r['first_name']}" for _,r in mem.iterrows()]
                    selc = st.multiselect("Members", options=list(student_map.keys()), default=curr)
                    if st.button("Update Competition", key="upd_comp"):
                        update_competition_members(cid, [student_map[s] for s in selc])
                        st.success("Updated.")
    with st.expander("Competitions List", expanded=False):
        if compet_df.empty:
            st.write("No competitions.")
        else:
            for _,c in compet_df.sort_values('name').iterrows():
                if st.button(c['name'], key=f"view_comp_{c['id']}"):
                    st.write(get_students_for_competition(c['id']))
