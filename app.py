import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import os
import copy
import streamlit_authenticator as stauth

# --- USER AUTHENTICATION ---
# This is the main page and will handle the login for the entire app.
credentials = st.secrets['credentials'].to_dict()
cookie_config = st.secrets['cookie']
authenticator = stauth.Authenticate(
    credentials,
    cookie_config['name'],
    cookie_config['key'],
    cookie_config['expiry_days'],
)

authenticator.login()

if st.session_state["authentication_status"]:
    # --- All application code must go INSIDE this block ---
    authenticator.logout("Logout", "sidebar")
    st.sidebar.title(f"Welcome {st.session_state['name']}")

    # --- DATABASE SETUP (remains inside the authenticated block) ---
    BASE_DIR = os.path.dirname(__file__)
    DATA_DIR = os.path.join(BASE_DIR, "data")
    os.makedirs(DATA_DIR, exist_ok=True)
    import payment_plan # Ensure this module can be found
    DB_PATH = os.path.join(DATA_DIR, "dance.db")
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
        c.execute("INSERT INTO students (first_name, last_name, dob) VALUES (?, ?, ?)",
                  (first, last, dob))
        conn.commit()

    def update_student(sid, first, last, dob):
        c.execute("UPDATE students SET first_name=?, last_name=?, dob=? WHERE id=?",
                  (first, last, dob, sid))
        conn.commit()

    def delete_student(sid):
        c.execute("DELETE FROM dance_students WHERE student_id=?", (sid,))
        c.execute("DELETE FROM competition_students WHERE student_id=?", (sid,))
        c.execute("DELETE FROM students WHERE id=?", (sid,))
        conn.commit()

    def get_all_students():
        return pd.read_sql("SELECT * FROM students ORDER BY last_name, first_name", conn)

    # Dance functions
    def add_dance(name, dtype, student_ids):
        c.execute("INSERT INTO dances (name, type) VALUES (?, ?)", (name, dtype))
        did = c.lastrowid
        for sid in student_ids:
            c.execute("INSERT OR IGNORE INTO dance_students (dance_id, student_id) VALUES (?, ?)",
                      (did, sid))
        conn.commit()

    def update_dance(did, name, student_ids):
        c.execute("UPDATE dances SET name=? WHERE id=?", (name, did))
        c.execute("DELETE FROM dance_students WHERE dance_id=?", (did,))
        for sid in student_ids:
            c.execute("INSERT INTO dance_students (dance_id, student_id) VALUES (?, ?)",
                      (did, sid))
        conn.commit()

    def delete_dance(did):
        c.execute("DELETE FROM dance_students WHERE dance_id=?", (did,))
        c.execute("DELETE FROM dances WHERE id=?", (did,))
        conn.commit()

    def get_all_dances():
        return pd.read_sql("SELECT * FROM dances ORDER BY type, name", conn)

    def get_students_for_dance(did):
        return pd.read_sql(
            "SELECT s.first_name || ' ' || s.last_name AS name FROM students s"
            " JOIN dance_students ds ON s.id=ds.student_id"
            " WHERE ds.dance_id=?", conn, params=(did,)
        )

    def get_dances_for_student(sid):
        return pd.read_sql(
            "SELECT d.name AS name, d.type AS type FROM dances d"
            " JOIN dance_students ds ON d.id=ds.dance_id"
            " WHERE ds.student_id=?", conn, params=(sid,)
        )

    # Competition functions
    def add_competition(name, has_conv, student_ids):
        c.execute("INSERT INTO competitions (name, has_convention) VALUES (?, ?)",
                  (name, has_conv))
        cid = c.lastrowid
        for sid in student_ids:
            c.execute("INSERT OR IGNORE INTO competition_students (competition_id, student_id) VALUES (?, ?)",
                      (cid, sid))
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

    # Fetch students for a competition
    def get_students_for_competition(comp_id):
        return pd.read_sql(
            "SELECT s.first_name || ' ' || s.last_name AS name FROM students s"
            " JOIN competition_students cs ON s.id = cs.student_id"
            " WHERE cs.competition_id = ?",
            conn, params=(comp_id,)
        )

    def get_competitions_for_student(sid):
        return pd.read_sql(
            "SELECT c.name AS name FROM competitions c"
            " JOIN competition_students cs ON c.id = cs.competition_id"
            " WHERE cs.student_id = ?", conn, params=(sid,)
        )

    # UI Setup
    st.set_page_config(page_title="EDOT Company Manager", layout="wide")
    st.title("EDOT Company Manager")

    # Sidebar navigation
    menu = st.sidebar.radio(
        "Navigate",
        ["📋 Students", "🕺 Dances", "🏆 Competitions"],
        index=0,
    )
    # The message below is now somewhat redundant since the page menu only appears after login,
    # but it can be kept for clarity if you wish.
    # st.info("Use the Streamlit page menu (☰) to access Payment Plans.")

    # --- Students Page ---
    if menu == "📋 Students":
        students_df = get_all_students()
        student_map = {f"{r['last_name']}, {r['first_name']}": r['id'] for _, r in students_df.iterrows()}

        with st.expander("Import & Create/Edit Students", expanded=False):
            # Import Students from CSV
            st.subheader("Import Students from CSV")
            csv_file = st.file_uploader("Upload Students CSV", type=["csv"], key="students_csv")
            if csv_file:
                df_import = pd.read_csv(csv_file)
                st.dataframe(df_import)
                if st.button("Import Students", key="btn_import_students"):
                    for _, row in df_import.iterrows():
                        try:
                            add_student(row['first'], row['last'], row['dob'])
                        except Exception as e:
                            st.error(f"Failed to import row {row.to_dict()}: {e}")
                    st.success("Students imported from CSV.")
            # Add New Student
            st.subheader("Add New Student")
            fn = st.text_input("First Name", key="add_fn")
            ln = st.text_input("Last Name", key="add_ln")
            dob = st.date_input("Date of Birth", min_value=date(1900,1,1), key="add_dob")
            if st.button("Add Student", key="btn_add_student"):
                if fn and ln:
                    add_student(fn, ln, dob.isoformat())
                    st.success(f"Added {fn} {ln}")
                else:
                    st.error("Please enter both first and last name.")

        st.markdown("---")

        # Edit or Delete Student
        st.subheader("Edit / Delete Student")
        sel = st.selectbox("Select Student", ["--"] + list(student_map.keys()), key="edit_sel")
        if sel and sel != "--":
            sid = student_map[sel]
            stu = students_df[students_df.id == sid].iloc[0]
            with st.form("edit_student_form"):
                fn2 = st.text_input("First Name", value=stu['first_name'], key="edit_fn")
                ln2 = st.text_input("Last Name", value=stu['last_name'], key="edit_ln")
                dob2 = st.date_input("Date of Birth", value=pd.to_datetime(stu['dob']), min_value=date(1900,1,1), key="edit_dob")
                if st.form_submit_button("Update Student", key="btn_update_student"):
                    if fn2 and ln2:
                        update_student(sid, fn2, ln2, dob2.isoformat())
                        st.success(f"Updated {fn2} {ln2}")
                    else:
                        st.error("Please enter both first and last name.")
                if st.form_submit_button("Delete Student", key="btn_delete_student"):
                    delete_student(sid)
                    st.success(f"Deleted {sel}")

        st.markdown("---")

        # View Student Profile
        st.subheader("View Student Profile")
        sel_v = st.selectbox("Select Student to View", ["--"] + list(student_map.keys()), key="view_sel")
        if sel_v and sel_v != "--":
            sid = student_map[sel_v]
            stu = students_df[students_df.id == sid].iloc[0]
            st.markdown(f"### {stu['first_name']} {stu['last_name']}")
            st.write(f"**DOB:** {stu['dob']}")
            # Dances
            st.write("**Dances:**")
            df_d = get_dances_for_student(sid)
            if df_d.empty:
                st.write("No dances.")
            else:
                for name in df_d['name']:
                    st.write(f"- {name}")
            # Competitions
            st.write("**Competitions:**")
            df_c = get_competitions_for_student(sid)
            if df_c.empty:
                st.write("No competitions.")
            else:
                for name in df_c['name']:
                    st.write(f"- {name}")

    # --- Dances Page ---
    elif menu == "🕺 Dances":
        st.header("Dances")
        with st.expander("Import & Create/Edit Dances", expanded=False):
            # Import Dances from CSV
            st.subheader("Import Dances from CSV")
            dances_file = st.file_uploader("Upload Dances CSV", type=["csv"], key="dances_csv")
            if dances_file:
                df_import = pd.read_csv(dances_file)
                st.dataframe(df_import)
                if st.button("Import Dances", key="btn_import_dances"):
                    students_df = get_all_students()
                    student_map = {f"{r['last_name']}, {r['first_name']}": r['id'] for _, r in students_df.iterrows()}
                    for _, row in df_import.iterrows():
                        dtype = row.get('dancetype') or row.get('type')
                        name = row.get('dancename') or row.get('name')
                        ids = []
                        for col in df_import.columns:
                            if col not in ['dancetype','dancename','type','name'] and pd.notna(row[col]):
                                label = row[col]
                                if label in student_map:
                                    ids.append(student_map[label])
                                else:
                                    st.warning(f"Unknown student: {label}")
                        try:
                            add_dance(name, dtype, ids)
                        except Exception as e:
                            st.error(f"Error importing dance '{name}': {e}")
                    st.success("Dances imported from CSV.")
            # Create/Edit Dances
            dance_df = get_all_dances()
            students_df = get_all_students()
            student_map = {f"{r['last_name']}, {r['first_name']}": r['id'] for _, r in students_df.iterrows()}
            dance_types = ["Solo","Duet","Trio","Group"]
            cols = st.columns(2)
            # Create Dance
            with cols[0]:
                st.subheader("Create Dance")
                name = st.text_input("Name", key="dance_new_name")
                dtype = st.selectbox("Type", dance_types, key="dance_new_type")
                sel = st.multiselect("Students", list(student_map.keys()), key="dance_new_students")
                limits = {"Solo":1, "Duet":2, "Trio":3, "Group":None}
                max_sel = limits.get(dtype)
                if st.button("Add Dance", key="btn_add_dance"):
                    ids = [student_map[s] for s in sel]
                    if max_sel and len(ids) != max_sel:
                        st.error(f"{dtype} requires exactly {max_sel} student(s).")
                    else:
                        add_dance(name, dtype, ids)
                        st.success(f"Dance '{name}' created.")
            # Edit/Delete Dance
            with cols[1]:
                st.subheader("Edit / Delete Dance")
                options = {f"{r['type']}: {r['name']}": r['id'] for _, r in dance_df.iterrows()}
                choice = st.selectbox("Select Dance to Edit", ["--"] + list(options.keys()), key="dance_edit_sel")
                if choice and choice != "--":
                    did = options[choice]
                    current = dance_df[dance_df.id == did].iloc[0]
                    dtype = current['type']
                    new_name = st.text_input("Dance Name", value=current['name'], key="edit_dance_name")
                    df_members = get_students_for_dance(did)
                    labels = []
                    for nm in df_members['name']:
                        parts = nm.split(' ', 1)
                        if len(parts) == 2:
                            labels.append(f"{parts[1]}, {parts[0]}")
                    selm = st.multiselect("Members", list(student_map.keys()), default=labels, key="dance_edit_members")
                    limits = {"Solo":1, "Duet":2, "Trio":3, "Group":None}
                    max_sel = limits.get(dtype)
                    if st.button("Update Dance", key="btn_edit_dance"):
                        ids = [student_map[s] for s in selm]
                        if max_sel and len(ids) != max_sel:
                            st.error(f"{dtype} requires exactly {max_sel} student(s).")
                        else:
                            update_dance(did, new_name, ids)
                            st.success("Dance updated.")
                    if st.button("Delete Dance", key="btn_delete_dance"):
                        delete_dance(did)
                        st.success(f"Deleted dance '{current['name']}'")

        # Show lists in order
        all_d = get_all_dances()
        for dtype in ["Solo","Duet","Trio","Group"]:
            with st.expander(f"{dtype} List", expanded=False):
                subset = all_d[all_d.type == dtype].sort_values('name')
                if subset.empty:
                    st.write("No dances.")
                else:
                    for _, d in subset.iterrows():
                        did = d['id']
                        if dtype == 'Solo':
                            members = get_students_for_dance(did)
                            mem = members['name'].iloc[0] if not members.empty else 'Unassigned'
                            st.write(f"- {d['name']} – {mem}")
                        else:
                            st.write(f"- {d['name']}") # Simplified view for groups in main list

    # --- Competitions Page ---
    elif menu == "🏆 Competitions":
        st.header("Competitions")
        with st.expander("Create/Edit Competitions", expanded=False):
            compet_df = pd.read_sql("SELECT * FROM competitions ORDER BY name", conn)
            students_df = get_all_students()
            student_map = {f"{r['last_name']}, {r['first_name']}":r['id'] for _,r in students_df.iterrows()}
            cols = st.columns(2)
            # Create Competition
            with cols[0]:
                name = st.text_input("Name", key="new_comp")
                has_conv = st.checkbox("Includes Convention", key="new_conv")
                sel = st.multiselect("Students", list(student_map.keys()), key="new_comp_sel")
                if st.button("Add Competition", key="btn_new_comp"):
                    add_competition(name,int(has_conv),[student_map[s] for s in sel])
                    st.success(f"Competition '{name}' created.")
            # Edit/Delete Competition
            with cols[1]:
                compet_df_local = compet_df.copy()
                options = {r['name']:r['id'] for _,r in compet_df_local.iterrows()}
                choice = st.selectbox("Select Competition to Edit", ["--"]+list(options.keys()), key="edit_comp_sel")
                if choice and choice!="--":
                    cid = options[choice]
                    current = compet_df_local[compet_df_local.id==cid].iloc[0]
                    df_m = get_students_for_competition(cid)
                    labels = []
                    for nm in df_m['name']:
                        parts = nm.split(' ',1)
                        if len(parts)==2:
                            labels.append(f"{parts[1]}, {parts[0]}")
                    selc = st.multiselect("Members", list(student_map.keys()), default=labels, key="edit_comp_members")
                    if st.button("Update Competition", key="btn_edit_comp"):
                        # This line was missing the update of the name and has_conv
                        # I've left it as is from your script, but you may want to update it
                        update_competition(cid, current['name'], 0, [student_map[s] for s in selc])
                        st.success("Competition updated.")
                    if st.button("Delete Competition", key="btn_delete_comp"):
                        c.execute("DELETE FROM competition_students WHERE competition_id=?",(cid,))
                        c.execute("DELETE FROM competitions WHERE id=?",(cid,))
                        conn.commit()
                        st.success(f"Deleted competition '{current['name']}'")
        with st.expander("Competitions List", expanded=False):
            compet_df_list = pd.read_sql("SELECT * FROM competitions ORDER BY name", conn)
            if compet_df_list.empty:
                st.write("No competitions.")
            else:
                for _, c in compet_df_list.sort_values('name').iterrows():
                    st.write(f"- {c['name']}")


    # --- Payment Plans Page ---
    # This section is removed as it's now a separate page.

    else:
        st.info("Select a module from the sidebar.")


elif st.session_state["authentication_status"] is False:
    st.error("Username/password is incorrect")
    
elif st.session_state["authentication_status"] is None:
    st.warning("Please enter your username and password to access the EDOT Company Manager.")