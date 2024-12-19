from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "yoursecretkey"  # replace with a secure key in production

DATABASE = 'app.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # Enable dictionary-like row access
        g._database = db
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS company (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT UNIQUE,
                        password TEXT,
                        company_name TEXT
                      )''')
        db.execute('''CREATE TABLE IF NOT EXISTS company_tables (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER,
                        table_name TEXT,
                        FOREIGN KEY(company_id) REFERENCES company(id)
                      )''')
        db.commit()

@app.route('/', methods=['GET'])
def index():
    if 'user_id' in session:
        db = get_db()
        tables = db.execute("SELECT table_name FROM company_tables WHERE company_id = ?", (session['user_id'],)).fetchall()
        return render_template('index.html', 
                               logged_in=True, 
                               company_name=session.get('company_name'), 
                               tables=[t['table_name'] for t in tables])
    else:
        return render_template('index.html', logged_in=False)

@app.route('/signup', methods=['POST'])
def signup():
    email = request.form.get('signup_email')
    password = request.form.get('signup_password')
    company_name = request.form.get('signup_company_name')

    if not email or not password or not company_name:
        return redirect(url_for('index'))

    db = get_db()
    try:
        db.execute("INSERT INTO company (email, password, company_name) VALUES (?, ?, ?)", 
                   (email, password, company_name))
        db.commit()
    except sqlite3.IntegrityError:
        return redirect(url_for('index'))

    user = db.execute("SELECT id, company_name FROM company WHERE email = ?", (email,)).fetchone()
    if user:
        session['user_id'] = user['id']
        session['company_name'] = user['company_name']

    return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('login_email')
    password = request.form.get('login_password')

    db = get_db()
    user = db.execute("SELECT id, password, company_name FROM company WHERE email = ?", (email,)).fetchone()

    if user and user['password'] == password:
        session['user_id'] = user['id']
        session['company_name'] = user['company_name']
        return redirect(url_for('index'))
    else:
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/create_table', methods=['POST'])
def create_table():
    table_name = request.form.get('table_name')
    columns = request.form.getlist('columns[]')
    data_types = request.form.getlist('data_types[]')

    if not table_name or not columns or not data_types or len(columns) != len(data_types):
        return redirect(url_for('index'))

    db = get_db()
    user_id = session['user_id']

    column_defs = ", ".join(f"{col} {dtype}" for col, dtype in zip(columns, data_types))
    create_table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {column_defs})"

    try:
        db.execute(create_table_sql)
        db.execute("INSERT INTO company_tables (company_id, table_name) VALUES (?, ?)", (user_id, table_name))
        db.commit()
    except sqlite3.Error:
        return redirect(url_for('index'))

    return redirect(url_for('table_view', table_name=table_name))

@app.route('/table/<string:table_name>', methods=['GET', 'POST'])
def table_view(table_name):
    db = get_db()
    user_id = session['user_id']

    # Check if table belongs to this user
    table_owner = db.execute("SELECT id FROM company_tables WHERE company_id = ? AND table_name = ?", 
                             (user_id, table_name)).fetchone()
    if not table_owner:
        return redirect(url_for('index'))

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'insert':
            # columns: we skip id column since it's autoincrement primary key
            columns = [col['name'] for col in db.execute(f"PRAGMA table_info({table_name})").fetchall() if col['name'] != 'id']
            values = request.form.getlist('values')
            if columns and values and len(columns) == len(values):
                placeholders = ", ".join(["?"] * len(values))
                db.execute(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})", values)
                db.commit()
        elif action == 'delete':
            row_id = request.form.get('row_id')
            db.execute(f"DELETE FROM {table_name} WHERE id = ?", (row_id,))
            db.commit()
        # elif action == 'update':
        #     row_id = request.form.get('row_id')
        #     # Get columns except id
        #     columns = [col['name'] for col in db.execute(f"PRAGMA table_info({table_name})").fetchall() if col['name'] != 'id']
        #     new_values = request.form.getlist('values')
        #     set_clause = ", ".join([f"{col}=?" for col in columns])
        #     db.execute(f"UPDATE {table_name} SET {set_clause} WHERE id = ?", (*new_values, row_id))
        #     db.commit()

    # Fetch rows and columns
    column_info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    columns = [col['name'] for col in column_info]
    rows = db.execute(f"SELECT * FROM {table_name}").fetchall()

    # Fetch list of all tables for nav
    tables = db.execute("SELECT table_name FROM company_tables WHERE company_id = ?", (user_id,)).fetchall()
    tables = [t['table_name'] for t in tables]

    return render_template('table.html', table_name=table_name, rows=rows, columns=columns, tables=tables)

if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        open(DATABASE, 'w').close()
    init_db()
    app.run(debug=True)
