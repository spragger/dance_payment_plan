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
);
""",
    """
CREATE TABLE IF NOT EXISTS dances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL
);
""",
    """
CREATE TABLE IF NOT EXISTS dance_students (
    dance_id INTEGER,
    student_id INTEGER,
    PRIMARY KEY (dance_id, student_id)
);
""",
    """
CREATE TABLE IF NOT EXISTS competitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    has_convention INTEGER NOT NULL CHECK (has_convention IN (0,1))
);
""",
    """
CREATE TABLE IF NOT EXISTS competition_students (
    competition_id INTEGER,
    student_id INTEGER,
    PRIMARY KEY (competition_id, student_id)
);
"""
]:
    c.execute(stmt)
conn.commit()

# --- DATABASE FUNCTIONS ---
def add_student(first, last, dob):
    c.execute(
        "INSERT INTO students (first_name, last_name, dob) VALUES (?, ?, ?)",
        (first, last, dob),
    )
    conn.commit()

def update_student(sid, first, last, dob):
    c.execute(
        "UPDATE students SET first_name=?, last_name=?, dob=? WHERE id=?",
        (first, last, dob, sid),
    )
    conn.commit()

# Fetch all students
def get_all_students():
    return pd.read_sql(
        "SELECT * FROM students ORDER BY last_name, first_name", conn
    )

# Dance functions

def add_dance(name, dtype, student_ids):
    c.execute("INSERT INTO dances (name, type) VALUES (?, ?)", (name, dtype))
    dance_id = c.lastrowid
    for sid in student_ids:
        c.execute(
            "INSERT OR IGNORE INTO dance_students (dance_id, student_id) VALUES (?, ?)",
            (dance_id, sid),
        )
    conn.commit()

def update_dance(did, name, student_ids):
    c.execute("UPDATE dances SET name=? WHERE id=?", (name, did))
    c.execute("DELETE FROM dance_students WHERE dance_id=?", (did,))
    for sid in student_ids:
        c.execute(
            "INSERT INTO dance_students (dance_id, student_id) VALUES (?, ?)",
            (did, sid),
        )
    conn.commit()

def get_all_dances():
    return pd.read_sql(
        "SELECT * FROM dances ORDER BY type, name", conn
    )

def get_students_for_dance(dance_id):
    return pd.read_sql(
        "SELECT s.first_name || ' ' || s.last_name AS name FROM students s"
        " JOIN dance_students ds ON s.id = ds.student_id"
        " WHERE ds.dance_id = ?", conn, params=(dance_id,)
    )

def get_dances_for_student(student_id):
    return pd.read_sql(
        "SELECT d.name AS name, d.type AS type FROM dances d"
        " JOIN dance_students ds ON d.id = ds.dance_id"
        " WHERE ds.student_id = ?", conn, params=(student_id,)
    )

# Competition functions

def add_competition(name, has_conv, student_ids):
    c.execute(
        "INSERT INTO competitions (name, has_convention) VALUES (?, ?)",
        (name, has_conv),
    )
    comp_id = c.lastrowid
    for sid in student_ids:
        c.execute(
            "INSERT OR IGNORE INTO competition_students (competition_id, student_id) VALUES (?, ?)",
            (comp_id, sid),
        )
    conn.commit()

def update_competition(cid, name, has_conv, student_ids):
    c.execute(
        "UPDATE competitions SET name=?, has_convention=? WHERE id=?",
        (name, has_conv, cid),
    )
    c.execute("DELETE FROM competition_students WHERE competition_id=?", (cid,))
    for sid in student_ids:
        c.execute(
            "INSERT INTO competition_students (competition_id, student_id) VALUES (?, ?)",
            (cid, sid),
        )
    conn.commit()

def get_all_competitions():
    return pd.read_sql(
        "SELECT * FROM competitions ORDER BY name", conn
    )

def get_students_for_competition(comp_id):
    return pd.read_sql(
        "SELECT s.first_name || ' ' || s.last_name AS name FROM students s"
        " JOIN competition_students cs ON s.id = cs.student_id"
        " WHERE cs.competition_id = ?", conn, params=(comp_id,)
    )

def get_competitions_for_student(student_id):
    return pd.read_sql(
        "SELECT c.name AS name FROM competitions c"
        " JOIN competition_students cs ON c.id = cs.competition_id"
        " WHERE cs.student_id = ?", conn, params=(student_id,)
    )

# --- UI ---
st.set_page_config(page_title="Dance Studio Manager", layout="wide")
menu = st.sidebar.selectbox(
    "Navigate", ["📋 Students", "🕺 Dances", "🏆 Competitions"]
)
st.title("Dance Studio Manager")

# Students Page
if menu == "📋 Students":
    # Load current students
    students_df = get_all_students()
    student_map = {f"{r['last_name']}, {r['first_name']}": r['id'] for _, r in students_df.iterrows()}

    # Add New Student
    st.subheader("Add New Student")
    with st.form("add_student_form"):
        fn = st.text_input("First Name")
        ln = st.text_input("Last Name")
        dob = st.date_input("Date of Birth", min_value=date(1900,1,1))
        submitted_add = st.form_submit_button("Add Student")
    if submitted_add:
        if fn and ln:
            add_student(fn, ln, dob.isoformat())
            st.success(f"Added {fn} {ln}")
            # Refresh data by rerunning the app automatically on next interaction
        else:
            st.error("Please enter both first and last name.")

    st.markdown("---")

    # Edit Existing Student
    st.subheader("Edit Existing Student")
    sel_edit = st.selectbox("Select Student to Edit", ["--"] + list(student_map.keys()))
    if sel_edit and sel_edit != "--":
        sid = student_map[sel_edit]
        stu = students_df[students_df.id == sid].iloc[0]
        with st.form("edit_student_form"):
            fn2 = st.text_input("First Name", value=stu['first_name'])
            ln2 = st.text_input("Last Name", value=stu['last_name'])
            dob2 = st.date_input("Date of Birth", value=pd.to_datetime(stu['dob']), min_value=date(1900,1,1))
            submitted_edit = st.form_submit_button("Update Student")
        if submitted_edit:
            if fn2 and ln2:
                update_student(sid, fn2, ln2, dob2.isoformat())
                st.success(f"Updated {fn2} {ln2}")
                # Changes will reflect on next rerun
            else:
                st.error("Please enter both first and last name.")

    st.markdown("---")

    # View Student Profile
    st.subheader("View Student Profile")
    sel_view = st.selectbox("Select Student", ["--"] + list(student_map.keys()))
    if sel_view and sel_view != "--":
        sid = student_map[sel_view]
        stu = students_df[students_df.id == sid].iloc[0]
        st.markdown(f"### {stu['first_name']} {stu['last_name']}")
        st.write(f"**DOB:** {stu['dob']}")
        # Dances
        st.write("**Dances:**")
        df_d = get_dances_for_student(sid)
        if df_d.empty:
            st.write("No dances.")
        else:
            for dance in df_d['name'].tolist():
                st.write(f"- {dance}")
        # Competitions
        st.write("**Competitions:**")
        df_c = get_competitions_for_student(sid)
        if df_c.empty:
            st.write("No competitions.")
        else:
            for comp in df_c['name'].tolist():
                st.write(f"- {comp}")

# Dances Page
elif menu == "🕺 Dances":
    st.header("Dances")
    # Create/Edit section
    with st.expander("Create/Edit Dances", expanded=False):
        dance_df = get_all_dances()
        students_df = get_all_students()
        student_map = {f"{r['last_name']}, {r['first_name']}": r['id'] for _, r in students_df.iterrows()}
        dance_types = ["Solo", "Duet", "Trio", "Group"]
        cols = st.columns(2)
                # Create
        with cols[0]:
            st.subheader("Create Dance")
            name = st.text_input("Name", key="dance_new_name")
            dtype = st.selectbox("Type", dance_types, key="dance_new_type")
            sel = st.multiselect("Students", list(student_map.keys()), key="dance_new_students")
            # Enforce selection limits
            limits = {"Solo": 1, "Duet": 2, "Trio": 3, "Group": None}
            max_sel = limits.get(dtype)
            if st.button("Add Dance", key="btn_add_dance"):
                selected_ids = [student_map[s] for s in sel]
                if max_sel is not None and len(selected_ids) != max_sel:
                    st.error(f"{dtype} requires exactly {max_sel} student(s).")
                else:
                    add_dance(name, dtype, selected_ids)
                    st.success(f"Dance '{name}' created.")
        # Edit
        with cols[1]:
            st.subheader("Edit Dance")
            options = {f"{r['type']}: {r['name']}": r['id'] for _, r in dance_df.iterrows()}
            choice = st.selectbox("Select Dance", ["--"] + list(options.keys()), key="dance_edit_sel")
            if choice and choice != "--":
                did = options[choice]
                current = dance_df[dance_df.id == did].iloc[0]
                dtype = current['type']
                # Editable name field
                new_name = st.text_input("Dance Name", value=current['name'], key="edit_dance_name")
                # Prepare default labels (Last, First) from stored First Last names
                df_members = get_students_for_dance(did)
                labels = []
                for nm in df_members['name'].tolist():
                    parts = nm.split(' ', 1)
                    if len(parts) == 2:
                        labels.append(f"{parts[1]}, {parts[0]}")
                # Member selection
                selm = st.multiselect("Members", options=list(student_map.keys()), default=labels, key="dance_edit_members")
                # Enforce selection limits
                limits = {"Solo": 1, "Duet": 2, "Trio": 3, "Group": None}
                max_sel = limits.get(dtype)
                if st.button("Update Dance", key="btn_edit_dance"):
                    sel_ids = [student_map[s] for s in selm]
                    if max_sel is not None and len(sel_ids) != max_sel:
                        st.error(f"{dtype} requires exactly {max_sel} student(s).")
                    else:
                        update_dance(did, new_name, sel_ids)
                        st.success("Dance updated.")

    # Display lists in order
    dance_df = get_all_dances()
    for dtype in ["Solo", "Duet", "Trio", "Group"]:
        with st.expander(f"{dtype} List", expanded=False):
            sub = dance_df[dance_df.type == dtype].sort_values('name')
            if sub.empty:
                st.write("No dances.")
            else:
                for _, d in sub.iterrows():
                    did = d['id']
                    if dtype == 'Solo':
                        members = get_students_for_dance(did)
                        member = members['name'].iloc[0] if not members.empty else 'Unassigned'
                        st.write(f"- {d['name']} – {member}")
                    else:
                        # click to show members
                        if st.button(d['name'], key=f"view_dance_{did}"):
                            members = get_students_for_dance(did)['name'].tolist()
                            if not members:
                                st.write("No members.")
                            else:
                                if dtype == 'Group':
                                    for i, m in enumerate(members, start=1):
                                        st.write(f"{i}. {m}")
                                else:
                                    for m in members:
                                        st.write(f"- {m}")

# Competitions Page
elif menu == "🏆 Competitions":
    with st.expander("Create/Edit Competitions", expanded=False):
        compet_df = get_all_competitions()
        students_df = get_all_students()
        student_map = {f"{r['last_name']}, {r['first_name']}": r['id'] for _, r in students_df.iterrows()}
        cols = st.columns(2)
        # Create
        with cols[0]:
            st.subheader("Create Competition")
            name = st.text_input("Name", key="new_comp")
            has_conv = st.checkbox("Includes Convention", key="new_conv")
            sel = st.multiselect("Students", list(student_map.keys()), key="new_comp_sel")
            if st.button("Add Competition", key="btn_new_comp"):
                add_competition(name, int(has_conv), [student_map[s] for s in sel])
                st.success(f"Competition '{name}' created.")
        # Edit
        with cols[1]:
            st.subheader("Edit Competition")
            options = {r['name']: r['id'] for _, r in compet_df.iterrows()}
            choice = st.selectbox("Select Competition", ["--"] + list(options.keys()), key="edit_comp_sel")
            if choice and choice != "--":
                cid = options[choice]
                df_members = get_students_for_competition(cid)
                curr = df_members['name'].tolist()
                selc = st.multiselect("Members", list(student_map.keys()), default=curr, key="edit_comp_members")
                if st.button("Update Competition", key="btn_edit_comp"):
                    update_competition(cid, choice, 0, [student_map[s] for s in selc])
                    st.success("Competition updated.")
    # List
    compet_df = get_all_competitions()
    with st.expander("Competitions List", expanded=False):
        if compet_df.empty:
            st.write("No competitions.")
        else:
            for _, c in compet_df.sort_values('name').iterrows():
                if st.button(c['name'], key=f"view_comp_{c['id']}"):
                    st.write(get_students_for_competition(c['id']))
