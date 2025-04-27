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
    student_id = session.get('user_id')
    if not student_id:
        return "Unauthorized", 401

    # Fetch student's class info
    student_class_info = query_db("""
        SELECT c.grade, c.section, s.Class_id
        FROM Students s
        JOIN Class c ON s.Class_id = c.Class_id
        WHERE s.P_ID = %s
    """, (student_id,), receive=True, one=True)

    class_id = student_class_info['Class_id']
    class_name = f"Grade {student_class_info['grade']} - Section {student_class_info['section']}"

    # Fetch timetable entries for the student's class
    timetable_entries = query_db("""
        SELECT tt.day, tt.timeslot, s.s_title AS subject_name, p.Name AS teacher_name
        FROM Timetable tt
        JOIN Subjects s ON tt.subject_id = s.s_id
        JOIN Teacher t ON tt.teacher_id = t.P_ID
        JOIN Person p ON t.P_ID = p.P_ID
        WHERE tt.class_id = %s
    """, (class_id,), receive=True)

    # Organize into { day: { timeslot: {subject_name, teacher_name} } }
    timetable = {}
    for entry in timetable_entries:
        day = entry['day']
        timeslot = entry['timeslot']
        timetable.setdefault(day, {})[timeslot] = {
            'subject_name': entry['subject_name'],
            'teacher_name': entry['teacher_name']
        }

    # Fixed days and timeslots
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    timeslots = ['08:00 - 09:00', '09:00 - 10:00', '10:00 - 11:00', '11:00 - 12:00', '12:00 - 01:00', '01:00 - 02:00', '02:00 - 03:00']

    return render_template("student_timetable.html",
                           class_name=class_name,
                           timetable=timetable,
                           days=days,
                           timeslots=timeslots)


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
        SELECT DISTINCT c.grade, c.section, c.Class_id AS class_id, s.s_title, s.s_id AS subject_id
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
        teacher_id = session.get('user_id')

        if not teacher_id:
            return "Unauthorized", 401

        # Fetch teacher's name
        teacher_info = query_db("""
            SELECT Name
            FROM Person
            WHERE P_ID = %s
        """, (teacher_id,), receive=True, one=True)

        teacher_name = teacher_info['Name']

        # Fetch timetable entries for this teacher
        timetable_entries = query_db("""
            SELECT 
                tt.day,
                tt.timeslot,
                c.grade,
                c.section,
                s.s_title
            FROM Timetable tt
            JOIN Class c ON tt.class_id = c.Class_id
            JOIN Subjects s ON tt.subject_id = s.s_id
            WHERE tt.teacher_id = %s
            ORDER BY FIELD(tt.day, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'), tt.timeslot
        """, (teacher_id,), receive=True)

        # Organize timetable: {day: {timeslot: {class, subject}}}
        timetable = {}
        for entry in timetable_entries:
            day = entry['day']
            timeslot = entry['timeslot']
            timetable.setdefault(day, {})[timeslot] = {
                'class': f"Grade {entry['grade']} - {entry['section']}",
                'subject': entry['s_title']
            }

        # Days and Timeslots
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        timeslots = ['08:00 - 09:00', '09:00 - 10:00', '10:00 - 11:00', '11:00 - 12:00', '12:00 - 01:00', '01:00 - 02:00', '02:00 - 03:00']

        return render_template("teacher_timetable.html",
                               teacher_name=teacher_name,
                               timetable=timetable,
                               days=days,
                               timeslots=timeslots)
    return "Access Denied", 403


@app.route('/teacher/grades/<int:class_id>/<int:subject_id>', methods=['GET'])
def grades(class_id, subject_id):
    if session.get('role') != 'teacher':
        return "Access Denied", 403

    # Get students with their existing marks (LEFT JOIN in case no marks yet)
    students_query = """
        SELECT p.P_ID, p.Name, perf.marks
        FROM Students s
        JOIN Person p ON s.P_ID = p.P_ID
        LEFT JOIN Performance perf ON perf.student_id = s.P_ID AND perf.subject_id = %s
        WHERE s.Class_id = %s
    """
    students = query_db(students_query, (subject_id, class_id), receive=True)

    if students is None:
        students = []  # if no students, use empty list (so Jinja won't crash)

    # Get subject title
    subject_query = "SELECT s_title FROM Subjects WHERE s_id = %s"
    subject = query_db(subject_query, (subject_id,), receive=True, one=True)

    return render_template(
        "grades.html",
        students=students,
        subject=subject['s_title'],
        class_id=class_id,
        subject_id=subject_id
    )



@app.route('/teacher/submit_grades/<int:class_id>/<int:subject_id>', methods=['POST'])
def submit_grades(class_id, subject_id):
    if session.get('role') != 'teacher':
        return "Access Denied", 403

    for key, value in request.form.items():
        if key.startswith('marks_'):
            student_id = int(key.split('_')[1])
            try:
                marks = int(value)
            except (ValueError, TypeError):
                marks = None

            if marks is not None:
                # Check if a record already exists
                check_query = """
                    SELECT * FROM Performance
                    WHERE student_id = %s AND subject_id = %s
                """
                existing = query_db(check_query, (student_id, subject_id), receive=True, one=True)

                if existing:
                    # Update existing marks
                    update_query = """
                        UPDATE Performance
                        SET marks = %s
                        WHERE student_id = %s AND subject_id = %s
                    """
                    query_db(update_query, (marks, student_id, subject_id), write=True)
                else:
                    # Insert new marks
                    insert_query = """
                        INSERT INTO Performance (student_id, subject_id, marks)
                        VALUES (%s, %s, %s)
                    """
                    query_db(insert_query, (student_id, subject_id, marks), write=True)

    return redirect(url_for('teacher_dashboard', class_id=class_id, subject_id=subject_id))



@app.route('/teacher/attendance')
def attendance():
    if session.get('role') != 'teacher':
        return "Access Denied", 403

    teacher_id = session.get('user_id')
    print("Teacher ID:", teacher_id)

    # Step 1: Find the class where this teacher is the class teacher
    class_row = query_db(
        "SELECT * FROM Class WHERE class_teacher_id = %s",
        (teacher_id,),
        receive=True,
        one=True
    )

    if not class_row:
        return "You are not assigned as a class teacher to any class.", 403

    class_id = class_row['Class_id']
    print("Class ID:", class_id)

    # Step 2: Fetch students in that class
    students = query_db(
        """
        SELECT Students.P_ID AS student_id, Person.Name, Students.Attendance
        FROM Students
        JOIN Person ON Students.P_ID = Person.P_ID
        WHERE Students.Class_id = %s
        """,
        (class_id,),
        receive=True
    )

    if not students:
        students = []  # To prevent TypeError if no students found

    return render_template('attendance.html', students=students)



@app.route('/teacher/submit_attendance', methods=['POST'])
def submit_attendance():
    if session.get('role') != 'teacher':
        return "Access Denied", 403

    teacher_id = session.get('user_id')

    # Get the class where this teacher is the class teacher
    class_query = "SELECT Class_id FROM Class WHERE class_teacher_id = %s"
    class_row = query_db(class_query, (teacher_id,), receive=True, one=True)

    if not class_row:
        return "You are not a class teacher.", 403

    class_id = class_row['Class_id']

    # Fetch students in that class
    students_query = "SELECT P_ID, Attendance FROM Students WHERE Class_id = %s"
    students = query_db(students_query, (class_id,), receive=True)

    if not students:
        return "No students found.", 404

    for student in students:
        student_id = student['P_ID']
        current_attendance = student['Attendance'] if student['Attendance'] is not None else 0

        checkbox_name = f"attendance_{student_id}"
        checkbox_checked = checkbox_name in request.form

        # Update attendance
        if checkbox_checked:
            updated_attendance = min(current_attendance + 3, 100)  # cap at 100
        else:
            updated_attendance = max(current_attendance - 3, 0)    # minimum 0

        update_query = "UPDATE Students SET Attendance = %s WHERE P_ID = %s"
        query_db(update_query, (updated_attendance, student_id), write=True)

    return redirect(url_for('teacher_dashboard'))



# ---------- ADMIN ROUTES ----------

@app.route('/admin')
def admin_dashboard():
    if session.get('role') == 'admin':
        return render_template("admin_dashboard.html")
    return "Access Denied", 403


@app.route('/admin/manage_students')
def manage_students():
    return render_template('manage_students.html')

@app.route('/admin /manage_teachers')
def manage_teachers():
    return render_template('manage_teachers.html')

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
