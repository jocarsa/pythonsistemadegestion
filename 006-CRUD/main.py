from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "yoursecretkey"  # replace with a secure key in production

DATABASE = 'app.db'

# Helper function to get DB connection
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Initialize the database
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
        return render_template('index.html', logged_in=True, company_name=session.get('company_name'), tables=[t[0] for t in tables])
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
        session['user_id'] = user[0]
        session['company_name'] = user[1]

    return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('login_email')
    password = request.form.get('login_password')

    db = get_db()
    user = db.execute("SELECT id, password, company_name FROM company WHERE email = ?", (email,)).fetchone()

    if user and user[1] == password:
        session['user_id'] = user[0]
        session['company_name'] = user[2]
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
    columns = request.form.getlist('columns')
    data_types = request.form.getlist('data_types')

    if not table_name or not columns or not data_types or len(columns) != len(data_types):
        return redirect(url_for('index'))

    db = get_db()
    user_id = session['user_id']

    column_defs = ", ".join(f"{col} {dtype}" for col, dtype in zip(columns, data_types))
    create_table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({column_defs})"

    try:
        db.execute(create_table_sql)
        db.execute("INSERT INTO company_tables (company_id, table_name) VALUES (?, ?)", (user_id, table_name))
        db.commit()
    except sqlite3.Error:
        return redirect(url_for('index'))

    return redirect(url_for('index'))

@app.route('/table/<string:table_name>', methods=['GET', 'POST'])
def table_view(table_name):
    db = get_db()
    user_id = session['user_id']

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'insert':
            columns = request.form.getlist('columns')
            values = request.form.getlist('values')
            if columns and values:
                placeholders = ", ".join(["?"] * len(values))
                db.execute(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})", values)
                db.commit()
        elif action == 'delete':
            row_id = request.form.get('row_id')
            db.execute(f"DELETE FROM {table_name} WHERE id = ?", (row_id,))
            db.commit()

    rows = db.execute(f"SELECT * FROM {table_name}").fetchall()
    columns = [description[0] for description in db.execute(f"PRAGMA table_info({table_name})").fetchall()]

    return render_template('table.html', table_name=table_name, rows=rows, columns=columns)

if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        open(DATABASE, 'w').close()
    init_db()
    app.run(debug=True)
