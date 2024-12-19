from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "yoursecretkey"  # replace with a secure key in production

DATABASE = 'app.db'

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

def init_db():
    with app.app_context():
        db = get_db()
        # Create table company if not exists
        db.execute('''CREATE TABLE IF NOT EXISTS company (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT UNIQUE,
                        password TEXT,
                        company_name TEXT
                      )''')
        db.commit()

@app.route('/', methods=['GET'])
def index():
    # If user is logged in, show dashboard
    if 'user_id' in session:
        return render_template('index.html', logged_in=True, company_name=session.get('company_name'))
    else:
        return render_template('index.html', logged_in=False)

@app.route('/signup', methods=['POST'])
def signup():
    email = request.form.get('signup_email')
    password = request.form.get('signup_password')
    company_name = request.form.get('signup_company_name')

    # Simple validation
    if not email or not password or not company_name:
        # In a real app, you'd probably flash a message to the user
        return redirect(url_for('index'))

    db = get_db()
    try:
        db.execute("INSERT INTO company (email, password, company_name) VALUES (?, ?, ?)", 
                   (email, password, company_name))
        db.commit()
    except sqlite3.IntegrityError:
        # Email already exists or other DB error
        return redirect(url_for('index'))

    # After sign-up, auto-log the user in
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
        # Password matches
        session['user_id'] = user[0]
        session['company_name'] = user[2]
        return redirect(url_for('index'))
    else:
        # Invalid credentials
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        open(DATABASE, 'w').close()
    init_db()
    app.run(debug=True)
