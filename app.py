from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for session management

# Dummy user database
users = {
    'student1': {'password': 'pass123', 'role': 'student'},
    'teacher1': {'password': 'pass456', 'role': 'teacher'},
    'admin1': {'password': 'admin789', 'role': 'admin'},
}

# ---------- ROUTES ----------

@app.route('/')
def home():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    user = users.get(username)

    if user and user['password'] == password:
        session['username'] = username
        session['role'] = user['role']

        if user['role'] == 'student':
            return redirect(url_for('student_dashboard'))
        elif user['role'] == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        elif user['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
    else:
        return "Invalid credentials", 401


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# ---------- STUDENT ROUTES ----------

@app.route('/student')
def student_dashboard():
    if session.get('role') == 'student':
        return render_template("student_dashboard.html")
    return "Access Denied", 403

@app.route('/student/timetable')
def student_timetable():
    if session.get('role') == 'student':
        return render_template("timetable.html")  # Use dynamic context if needed
    return "Access Denied", 403


# ---------- TEACHER ROUTES ----------

@app.route('/teacher')
def teacher_dashboard():
    if session.get('role') == 'teacher':
        return render_template("teacher_dashboard.html")
    return "Access Denied", 403

@app.route('/teacher/timetable')
def teacher_timetable():
    if session.get('role') == 'teacher':
        return render_template("timetable.html")  # Can reuse timetable template
    return "Access Denied", 403

@app.route('/teacher/grades')
def grades():
    if session.get('role') == 'teacher':
        return render_template("grades.html")
    return "Access Denied", 403

@app.route('/teacher/attendance')
def attendance():
    if session.get('role') == 'teacher':
        return render_template("attendance.html")
    return "Access Denied", 403


# ---------- ADMIN ROUTES ----------

@app.route('/admin')
def admin_dashboard():
    if session.get('role') == 'admin':
        return render_template("admin_dashboard.html")
    return "Access Denied", 403

@app.route('/admin/teachers')
def teacher_list():
    if session.get('role') == 'admin':
        return render_template("teacher_list.html")
    return "Access Denied", 403

@app.route('/admin/classes')
def class_list():
    if session.get('role') == 'admin':
        return render_template("class_list.html")
    return "Access Denied", 403

@app.route('/admin/classes/<grade>/<section>')
def student_list(grade, section):
    if session.get('role') == 'admin':
        return render_template("student_list.html", grade=grade, section=section)
    return "Access Denied", 403

@app.route('/admin/books')
def books_inventory():
    if session.get('role') == 'admin':
        return render_template("books_inventory.html")
    return "Access Denied", 403


# ---------- MAIN ----------
if __name__ == '__main__':
    app.run(debug=True)
