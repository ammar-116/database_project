from flask import Flask, render_template, request, redirect, url_for, session
from db.database import *

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

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = "SELECT * FROM Person WHERE L_username = %s AND L_password = %s"
    cursor.execute(query, (username, password))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if user:
        session['username'] = user['L_username']
        session['role'] = user['Type'].lower()
        session['user_id'] = user['P_ID']  # This is what the dashboard route expects
        print("SESSION USER ID:", session.get("user_id"))

        if user['Type'] == 'Student':
            return redirect(url_for('student_dashboard'))
        elif user['Type'] == 'Teacher':
            return redirect(url_for('teacher_dashboard'))
        elif user['Type'] == 'Admin':
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
    student_id = session.get("user_id")

    if not student_id:
        return "Unauthorized", 401

    # Get student basic info including attendance, class, teacher
    student_info = query_db("""
        SELECT p.P_ID, p.Name, p.Gender, s.Attendance, c.grade, c.section, t.P_ID AS teacher_id, tp.Name AS teacher_name
        FROM Person p
        JOIN Students s ON p.P_ID = s.P_ID
        JOIN Class c ON s.Class_id = c.Class_id
        JOIN Teacher t ON c.class_teacher_id = t.P_ID
        JOIN Person tp ON tp.P_ID = t.P_ID
        WHERE p.P_ID = %s
    """, (student_id,), receive=True, one=True)

    # Get book issued (if any)
    book_info = query_db("""
        SELECT B_title, date_issued
        FROM Books
        WHERE student_id = %s
    """, (student_id,), receive=True, one=True)

    # Get grades for 6 subjects
    grades = query_db("""
        SELECT s.s_title, p.marks
        FROM Performance p
        JOIN Subjects s ON p.subject_id = s.s_id
        WHERE p.student_id = %s
    """, (student_id,), receive=True)

    return render_template("student_dashboard.html",
                           student=student_info,
                           book=book_info,
                           grades=grades)



@app.route('/student/timetable')
def student_timetable():
    if session.get('role') == 'student':
        return render_template("student_timetable.html")  # Use dynamic context if needed
    return "Access Denied", 403


# ---------- TEACHER ROUTES ----------

@app.route('/teacher')
def teacher_dashboard():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))

    # Get teacher basic info and homeroom class
    teacher_info_query = """
        SELECT p.P_ID, p.Name, c.grade, c.section
        FROM Person p
        JOIN Teacher t ON p.P_ID = t.P_ID
        LEFT JOIN Class c ON c.class_teacher_id = t.P_ID
        WHERE p.L_username = %s
    """
    teacher_data = query_db(teacher_info_query, (username,), receive=True, one=True)
    if not teacher_data:
        return "No teacher data found"

    teacher_id = teacher_data['P_ID']
    homeroom = f"{teacher_data['grade']}-{teacher_data['section']}" if teacher_data['grade'] else "None"

    # Get classes the teacher teaches along with subjects
    classes_query = """
        SELECT DISTINCT c.grade, c.section, s.s_title
        FROM Timetable tt
        JOIN Class c ON tt.class_id = c.Class_id
        JOIN Subjects s ON tt.subject_id = s.s_id
        WHERE tt.teacher_id = %s
    """
    classes_data = query_db(classes_query, (teacher_id,), receive=True)

    return render_template(
        'teacher_dashboard.html',
        teacher=teacher_data,
        homeroom=homeroom,
        classes=classes_data
    )



@app.route('/teacher/timetable')
def teacher_timetable():
    if session.get('role') == 'teacher':
        return render_template("teacher_timetable.html")  # Can reuse timetable template
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
