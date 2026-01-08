from flask import Flask, render_template, request, redirect, session, send_from_directory
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# ---------------- MySQL CONFIG ---------------- #
app.config['MYSQL_HOST'] = config.MYSQL_HOST
app.config['MYSQL_USER'] = config.MYSQL_USER
app.config['MYSQL_PASSWORD'] = config.MYSQL_PASSWORD
app.config['MYSQL_DB'] = config.MYSQL_DB
mysql = MySQL(app)

# ---------------- UPLOAD CONFIG ---------------- #
UPLOAD_FOLDER = "static/pdfs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# =================================================
#                   USER ROUTES
# =================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        hashed_password = generate_password_hash(request.form['password'])

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO users(name,email,password) VALUES(%s,%s,%s)",
            (request.form['name'], request.form['email'], hashed_password)
        )
        mysql.connection.commit()
        cur.close()

        return redirect('/login')

    return render_template('register.html')


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT * FROM users WHERE email=%s",
            (request.form['email'],)
        )
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user[3], request.form['password']):
            session['user_id'] = user[0]
            next_url = session.pop('next_url', None)
            return redirect(next_url or '/subjects')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/subjects')
def subjects():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM subjects")
    subjects = cur.fetchall()
    cur.close()
    return render_template('subjects.html', subjects=subjects)


@app.route('/subject/<int:sid>')
def subject_detail(sid):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM pdfs WHERE subject_id=%s", (sid,))
    pdfs = cur.fetchall()
    cur.close()
    return render_template('subject_detail.html', pdfs=pdfs)


@app.route('/download-pdf/<int:pid>')
def download_pdf(pid):
    if 'user_id' not in session:
        session['next_url'] = f"/download-pdf/{pid}"
        return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute("SELECT file_path FROM pdfs WHERE id=%s", (pid,))
    pdf = cur.fetchone()

    if not pdf:
        cur.close()
        return "File not found", 404

    # 🔹 DOWNLOAD COUNT ADDED
    cur.execute("UPDATE pdfs SET downloads = downloads + 1 WHERE id=%s", (pid,))
    mysql.connection.commit()
    cur.close()

    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        pdf[0],
        as_attachment=True
    )

# =================================================
#                   ADMIN ROUTES
# =================================================

@app.route('/admin', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT * FROM admins WHERE username=%s",
            (request.form['username'],)
        )
        admin = cur.fetchone()
        cur.close()

        if admin and check_password_hash(admin[2], request.form['password']):
            session['admin'] = admin[0]
            return redirect('/admin/dashboard')

    return render_template('admin/admin_login.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect('/admin')

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT pdfs.id, pdfs.title, pdfs.downloads, subjects.subject_name
        FROM pdfs
        JOIN subjects ON pdfs.subject_id = subjects.id
    """)
    pdfs = cur.fetchall()

    cur.execute("SELECT * FROM subjects")
    subjects = cur.fetchall()
    cur.close()

    return render_template(
        'admin/dashboard.html',
        pdfs=pdfs,
        subjects=subjects
    )


@app.route('/admin/add-subject', methods=['POST'])
def add_subject():
    if not session.get('admin'):
        return redirect('/admin')

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO subjects(subject_name,description) VALUES(%s,%s)",
        (request.form['name'], request.form['description'])
    )
    mysql.connection.commit()
    cur.close()
    return redirect('/admin/dashboard')


# ---------- EDIT SUBJECT ----------
@app.route('/admin/edit-subject/<int:sid>', methods=['GET','POST'])
def edit_subject(sid):
    if not session.get('admin'):
        return redirect('/admin')

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        cur.execute(
            "UPDATE subjects SET subject_name=%s, description=%s WHERE id=%s",
            (request.form['name'], request.form['description'], sid)
        )
        mysql.connection.commit()
        cur.close()
        return redirect('/admin/dashboard')

    cur.execute("SELECT * FROM subjects WHERE id=%s", (sid,))
    subject = cur.fetchone()
    cur.close()

    return render_template('admin/edit_subject.html', subject=subject)


# ---------- DELETE SUBJECT ----------
@app.route('/admin/delete-subject/<int:sid>')
def delete_subject(sid):
    if not session.get('admin'):
        return redirect('/admin')

    cur = mysql.connection.cursor()
    cur.execute("SELECT file_path FROM pdfs WHERE subject_id=%s", (sid,))
    pdfs = cur.fetchall()

    for p in pdfs:
        path = os.path.join(app.config['UPLOAD_FOLDER'], p[0])
        if os.path.exists(path):
            os.remove(path)

    cur.execute("DELETE FROM pdfs WHERE subject_id=%s", (sid,))
    cur.execute("DELETE FROM subjects WHERE id=%s", (sid,))
    mysql.connection.commit()
    cur.close()
    return redirect('/admin/dashboard')


@app.route('/admin/upload-pdf', methods=['POST'])
def upload_pdf():
    if not session.get('admin'):
        return redirect('/admin')

    pdf_file = request.files['pdf']
    filename = secure_filename(pdf_file.filename)
    pdf_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO pdfs(subject_id,title,price,file_path) VALUES(%s,%s,%s,%s)",
        (request.form['subject'], request.form['title'], 0, filename)
    )
    mysql.connection.commit()
    cur.close()
    return redirect('/admin/dashboard')


@app.route('/admin/update-pdf/<int:pid>', methods=['GET','POST'])
def update_pdf(pid):
    if not session.get('admin'):
        return redirect('/admin')

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        pdf_file = request.files['pdf']
        filename = secure_filename(pdf_file.filename)
        pdf_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cur.execute(
            "UPDATE pdfs SET file_path=%s WHERE id=%s",
            (filename, pid)
        )
        mysql.connection.commit()
        cur.close()
        return redirect('/admin/dashboard')

    cur.execute("SELECT * FROM pdfs WHERE id=%s", (pid,))
    pdf = cur.fetchone()
    cur.close()

    return render_template('admin/update_pdf.html', pdf=pdf)


@app.route('/admin/delete-pdf/<int:pid>')
def delete_pdf(pid):
    if not session.get('admin'):
        return redirect('/admin')

    cur = mysql.connection.cursor()
    cur.execute("SELECT file_path FROM pdfs WHERE id=%s", (pid,))
    pdf = cur.fetchone()

    if pdf:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf[0])
        if os.path.exists(file_path):
            os.remove(file_path)

        cur.execute("DELETE FROM pdfs WHERE id=%s", (pid,))
        mysql.connection.commit()

    cur.close()
    return redirect('/admin/dashboard')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin')


if __name__ == "__main__":
    app.run(debug=True)
