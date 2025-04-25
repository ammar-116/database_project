from flask import Flask, render_template, request, redirect, url_for, session,jsonify
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
    print("🏠 Home route triggered")
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    print("🔒 Login route called")

    username = request.form.get('username')
    password = request.form.get('password')
    print(f"Received: {username}, {password}")

    if not username or not password:
        return "Missing credentials", 400

    result = query_db(
        "SELECT Type FROM Person WHERE L_username = %s AND L_password = %s",
        (username, password),
        receive=True
    )

    print(f"Query result: {result}")

    if result and isinstance(result[0], dict):  # now checking for dictionary
        role = result[0]['Type']
        print(f"✅ Role found: {role}")

        session['username'] = username
        session['role'] = role.lower()

        if role == 'Student':
            return redirect(url_for('student_dashboard'))
        elif role == 'Teacher':
            return redirect(url_for('teacher_dashboard'))
        elif role == 'Admin':
            return redirect(url_for('admin_dashboard'))

    print(" Invalid login or unexpected result")
    return "Invalid credentials", 401




@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# ---------- STUDENT ROUTES ----------

@app.route('/student')
def student_dashboard():
    if session.get('role') != 'student':
        return "Access Denied", 403

    username = session.get('username')
    if not username:
        return "Not logged in", 401

    student_data = query_db("""
        SELECT p.P_ID, p.Name, p.Gender, s.Attendance, c.grade, c.section, t.P_ID AS teacher_id, tp.Name AS teacher_name
        FROM Person p
        JOIN Student s ON p.P_ID = s.P_ID
        JOIN Class c ON s.Class_id = c.Class_id
        LEFT JOIN Teacher t ON c.class_teacher_id = t.P_ID
        LEFT JOIN Person tp ON t.P_ID = tp.P_ID
        WHERE p.L_username = %s
    """, (username,), receive=True, one=True)

    if not student_data:
        return "Student not found", 404

    # Grades
    grades = query_db("""
        SELECT subj.s_title AS subject, perf.marks
        FROM Performance perf
        JOIN Subject subj ON perf.subject_id = subj.s_id
        WHERE perf.student_id = %s
    """, (student_data['P_ID'],), receive=True)

    # Books issued (titles only)
    books = query_db("""
        SELECT title FROM Book
        WHERE issued_to = %s
    """, (student_data['P_ID'],), receive=True)

    return render_template('student_dashboard.html',
                           student=student_data,
                           grades=grades or [],
                           books=books or [])





@app.route('/student/timetable')
def student_timetable():
    if session.get('role') == 'student':
        return render_template("timetable.html")  # Use dynamic context if needed
    return "Access Denied", 403


# ---------- TEACHER ROUTES ----------

@app.route('/teacher')
def teacher_dashboard():
    if session.get('role') != 'teacher':
        return "Access Denied", 403

    username = session.get('username')
    teacher_data = query_db("""
        SELECT p.P_ID, p.Name, s.s_title AS Subject
        FROM Person p
        JOIN Teacher t ON p.P_ID = t.P_ID
        JOIN Timetable tt ON tt.teacher_id = t.P_ID
        JOIN Subject s ON tt.subject_id = s.s_id
        WHERE p.L_username = %s
        LIMIT 1
    """, (username,), receive=True, one=True)

    if not teacher_data:
        return "Teacher not found", 404

    teacher_id = teacher_data['P_ID']

    # Get homeroom class (if any)
    homeroom = query_db("""
        SELECT grade, section FROM Class
        WHERE class_teacher_id = %s
    """, (teacher_id,), receive=True, one=True)

    # Get distinct classes they teach from Timetable
    classes_taught = query_db("""
        SELECT DISTINCT c.grade, c.section
        FROM Timetable tt
        JOIN Class c ON tt.class_id = c.Class_id
        WHERE tt.teacher_id = %s
        ORDER BY c.grade, c.section
    """, (teacher_id,), receive=True)

    return render_template("teacher_dashboard.html",
        teacher=teacher_data,
        homeroom=homeroom,
        classes=classes_taught
    )


@app.route('/teacher/timetable')
def teacher_timetable():
    if session.get('role') == 'teacher':
        return render_template("timetable.html")  # Can reuse timetable template
    return "Access Denied", 403

@app.route('/teacher/grades/<int:grade>/<section>', methods=['GET', 'POST'])
def teacher_grades(grade, section):
    if session.get('role') != 'teacher':
        return "Access Denied", 403

    username = session.get('username')

    teacher = query_db("""
        SELECT t.P_ID, s.s_id
        FROM Person p
        JOIN Teacher t ON p.P_ID = t.P_ID
        JOIN Timetable tt ON tt.teacher_id = t.P_ID
        JOIN Subject s ON s.s_id = tt.subject_id
        WHERE p.L_username = %s AND tt.class_id = (
            SELECT Class_id FROM Class WHERE grade = %s AND section = %s
        )
        LIMIT 1
    """, (username, grade, section), receive=True, one=True)

    if not teacher:
        return "Teacher or subject not found for this class", 404

    teacher_id = teacher['P_ID']
    subject_id = teacher['s_id']

    class_id = query_db("SELECT Class_id FROM Class WHERE grade = %s AND section = %s",
                        (grade, section), receive=True, one=True)['Class_id']

    if request.method == 'POST':
        for key, val in request.form.items():
            if key.startswith("marks_"):
                student_id = key.split("_")[1]
                mark = int(val)
                existing = query_db("""
                    SELECT * FROM Performance 
                    WHERE student_id = %s AND subject_id = %s
                """, (student_id, subject_id), receive=True, one=True)
                if existing:
                    query_db("""
                        UPDATE Performance 
                        SET marks = %s 
                        WHERE student_id = %s AND subject_id = %s
                    """, (mark, student_id, subject_id), write=True)
                else:
                    query_db("""
                        INSERT INTO Performance (student_id, subject_id, marks)
                        VALUES (%s, %s, %s)
                    """, (student_id, subject_id, mark), write=True)

        return redirect(request.url)

    students = query_db("""
        SELECT p.P_ID, p.Name, pf.marks
        FROM Student s
        JOIN Person p ON p.P_ID = s.P_ID
        LEFT JOIN Performance pf ON pf.student_id = s.P_ID AND pf.subject_id = %s
        WHERE s.Class_id = %s
    """, (subject_id, class_id), receive=True)

    return render_template("grades.html", students=students, class_info=f"{grade}{section}")




@app.route('/teacher/attendance')
def teacher_attendance():
    if session.get('role') == 'teacher':
        return render_template('attendance.html')
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
