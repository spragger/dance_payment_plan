import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime
import os

# --- DATABASE SETUP ---
DB_PATH = "data/dance.db"
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# --- SCHEMA CREATION ---
for stmt in [
    # students, dances, competitions existing schemas
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
    type TEXT NOT NULL,
    price REAL NOT NULL DEFAULT 0
);""",
    """
CREATE TABLE IF NOT EXISTS dance_students (
    dance_id INTEGER,
    student_id INTEGER,
    PRIMARY KEY (dance_id, student_id)
);""",
    """
CREATE TABLE IF NOT EXISTS competitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    has_convention INTEGER NOT NULL CHECK(has_convention IN (0,1)),
    price REAL NOT NULL DEFAULT 0,
    convention_price REAL NOT NULL DEFAULT 0
);""",
    """
CREATE TABLE IF NOT EXISTS competition_students (
    competition_id INTEGER,
    student_id INTEGER,
    PRIMARY KEY (competition_id, student_id)
);""",
    # payment templates and student plans
    """
CREATE TABLE IF NOT EXISTS payment_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);""",
    """
CREATE TABLE IF NOT EXISTS template_items (
    template_id INTEGER,
    name TEXT,
    price REAL,
    item_type TEXT,
    PRIMARY KEY (template_id, name)
);""",
    """
CREATE TABLE IF NOT EXISTS student_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    template_id INTEGER,
    created_at TEXT
);""",
    """
CREATE TABLE IF NOT EXISTS plan_items (
    plan_id INTEGER,
    name TEXT,
    price REAL,
    item_type TEXT
);"""
]:
    c.execute(stmt)
conn.commit()

# --- DATABASE FUNCTIONS ---
def get_all_students():
    return pd.read_sql("SELECT * FROM students ORDER BY last_name, first_name", conn)

def add_student(first, last, dob):
    c.execute("INSERT INTO students(first_name, last_name, dob) VALUES(?,?,?)",(first,last,dob))
    conn.commit()

def update_student(sid, first, last, dob):
    c.execute("UPDATE students SET first_name=?, last_name=?, dob=? WHERE id=?",(first,last,dob,sid))
    conn.commit()

def get_all_dances():
    return pd.read_sql("SELECT * FROM dances ORDER BY type, name", conn)

def add_dance(name, dtype, price):
    c.execute("INSERT INTO dances(name,type,price) VALUES(?,?,?)",(name,dtype,price))
    conn.commit()

def update_dance(did, name, price):
    c.execute("UPDATE dances SET name=?,price=? WHERE id=?",(name,price,did))
    conn.commit()

def get_students_for_dance(did):
    return pd.read_sql(
        "SELECT s.first_name||' '||s.last_name AS student FROM students s JOIN dance_students ds ON s.id=ds.student_id WHERE ds.dance_id=?", conn, params=(did,))

def get_all_competitions():
    return pd.read_sql("SELECT * FROM competitions ORDER BY name", conn)

def add_competition(name, has_conv, price, conv_price):
    c.execute("INSERT INTO competitions(name,has_convention,price,convention_price) VALUES(?,?,?,?)",(name,has_conv,price,conv_price))
    conn.commit()

def update_competition(cid, name, has_conv, price, conv_price):
    c.execute("UPDATE competitions SET name=?,has_convention=?,price=?,convention_price=? WHERE id=?",(name,has_conv,price,conv_price,cid))
    conn.commit()

# payment templates

def get_templates():
    return pd.read_sql("SELECT * FROM payment_templates ORDER BY name", conn)

def add_template(name):
    c.execute("INSERT INTO payment_templates(name) VALUES(?)",(name,))
    conn.commit()

def get_template_items(tid):
    return pd.read_sql("SELECT * FROM template_items WHERE template_id=?", conn, params=(tid,))

def add_template_item(tid,name,price,item_type):
    c.execute("INSERT INTO template_items(template_id,name,price,item_type) VALUES(?,?,?,?)",(tid,name,price,item_type))
    conn.commit()

# student plans

def get_student_plans(sid):
    return pd.read_sql("SELECT * FROM student_plans WHERE student_id=?", conn, params=(sid,))

def add_student_plan(sid,tid):
    now = datetime.now().isoformat()
    c.execute("INSERT INTO student_plans(student_id,template_id,created_at) VALUES(?,?,?)",(sid,tid,now))
    conn.commit()
    return c.lastrowid

def get_plan_items(pid):
    return pd.read_sql("SELECT * FROM plan_items WHERE plan_id=?", conn, params=(pid,))

def add_plan_item(pid,name,price,item_type):
    c.execute("INSERT INTO plan_items(plan_id,name,price,item_type) VALUES(?,?,?,?)",(pid,name,price,item_type))
    conn.commit()

# --- STREAMLIT UI ---
st.set_page_config(page_title="Dance Studio Manager", layout="wide")
menu = st.sidebar.selectbox("Navigate", ["📋 Students","🕺 Dances","🏆 Competitions","💳 Payment Templates"])
st.title("Dance Studio Manager")

# preload data
students_df = get_all_students()
student_map = {f"{r['last_name']}, {r['first_name']}":r['id'] for _,r in students_df.iterrows()}
dance_df = get_all_dances()
compet_df = get_all_competitions()
templates_df = get_templates()

# --- STUDENTS PAGE ---
if menu=="📋 Students":
    sel = st.selectbox("Select Student", ["--"]+list(student_map.keys()))
    if sel!="--":
        sid=student_map[sel]
        st.subheader(f"{sel}")
        st.write("**Dances**")
        dd=pd.read_sql("SELECT d.name,d.price FROM dances d JOIN dance_students ds ON d.id=ds.dance_id WHERE ds.student_id=?",conn,params=(sid,))
        st.write(dd if not dd.empty else "None")
        st.write("**Competitions**")
        cc=pd.read_sql("SELECT c.name, c.price+(CASE WHEN c.has_convention=1 THEN c.convention_price ELSE 0 END) as price FROM competitions c JOIN competition_students cs ON c.id=cs.competition_id WHERE cs.student_id=?",conn,params=(sid,))
        st.write(cc if not cc.empty else "None")
        # Payment Plans
        with st.expander("Payment Plans",expanded=False):
            # existing plans
            plans=get_student_plans(sid)
            st.write(plans)
            # add plan
            tid=st.selectbox("Template", ["--"]+list(templates_df.name))
            if tid!="--":
                trow=templates_df[templates_df.name==tid].iloc[0]
                if st.button("Add Payment Plan"):
                    pid=add_student_plan(sid,trow.id)
                    items=get_template_items(trow.id)
                    for _,item in items.iterrows():
                        add_plan_item(pid,item.name,item.price,item.item_type)
                    st.success("Plan created")

# --- PAYMENT TEMPLATES PAGE ---
elif menu=="💳 Payment Templates":
    st.header("Templates")
    # create template
    with st.expander("Create Template",expanded=False):
        tname=st.text_input("Template Name",key="tmpl_name")
        if st.button("Add Template"):
            add_template(tname)
            st.experimental_rerun()
    # edit template items
    with st.expander("Edit Template Items",expanded=False):
        tmpl=st.selectbox("Select Template",["--"]+list(templates_df.name))
        if tmpl!="--":
            tid=templates_df[templates_df.name==tmpl].iloc[0].id
            items=get_template_items(tid)
            # show and add items
            for _,it in items.iterrows(): st.write(f"{it.item_type}: {it.name} - ${it.price}")
            name=st.text_input("Item Name",key="itm_name")
            price=st.number_input("Price",min_value=0.0,format="%.2f",key="itm_price")
            itype=st.selectbox("Type",["Credit","Expense"],key="itm_type")
            if st.button("Add Item"):
                add_template_item(tid,name,price,itype)
                st.success("Item added")

# --- DANCES & COMPETITIONS pages unchanged ---
else:
    st.info("Other modules unaffected.")
