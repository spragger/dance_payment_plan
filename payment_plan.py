import sqlite3
import pandas as pd
from datetime import datetime

# --- DATABASE CONNECTION ---
DB_PATH = "data/dance.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# --- SCHEMA FOR PAYMENT PLANS ---
c.execute("""
CREATE TABLE IF NOT EXISTS payment_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
""")
c.execute("""
CREATE TABLE IF NOT EXISTS template_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    item_type TEXT NOT NULL,
    FOREIGN KEY(template_id) REFERENCES payment_templates(id)
);
""")
c.execute("""
CREATE TABLE IF NOT EXISTS student_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    template_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(student_id) REFERENCES students(id),
    FOREIGN KEY(template_id) REFERENCES payment_templates(id)
);
""")
c.execute("""
CREATE TABLE IF NOT EXISTS plan_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    item_type TEXT NOT NULL,
    FOREIGN KEY(plan_id) REFERENCES student_plans(id)
);
""")
conn.commit()

# --- PAYMENT TEMPLATE FUNCTIONS ---
def get_templates():
    return pd.read_sql("SELECT * FROM payment_templates ORDER BY name", conn)

def add_template(name):
    c.execute("INSERT OR IGNORE INTO payment_templates(name) VALUES(?)", (name,))
    conn.commit()

def get_template_items(template_id):
    return pd.read_sql(
        "SELECT name, price, item_type FROM template_items WHERE template_id = ?", 
        conn, params=(template_id,)
    )

def add_template_item(template_id, name, price, item_type):
    c.execute(
        "INSERT INTO template_items(template_id, name, price, item_type) VALUES(?,?,?,?)", 
        (template_id, name, price, item_type)
    )
    conn.commit()

# --- STUDENT PLAN FUNCTIONS ---
def get_student_plans(student_id):
    return pd.read_sql(
        "SELECT * FROM student_plans WHERE student_id = ?", 
        conn, params=(student_id,)
    )

def add_student_plan(student_id, template_id):
    now = datetime.now().isoformat()
    c.execute(
        "INSERT INTO student_plans(student_id, template_id, created_at) VALUES(?,?,?)",
        (student_id, template_id, now)
    )
    plan_id = c.lastrowid
    conn.commit()
    return plan_id

def get_plan_items(plan_id):
    return pd.read_sql(
        "SELECT name, price, item_type FROM plan_items WHERE plan_id = ?", 
        conn, params=(plan_id,)
    )

def add_plan_item(plan_id, name, price, item_type):
    c.execute(
        "INSERT INTO plan_items(plan_id, name, price, item_type) VALUES(?,?,?,?)", 
        (plan_id, name, price, item_type)
    )
    conn.commit()
