from flask import Flask, render_template, request, redirect, url_for, session
from db.database import *
import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for session management


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


@app.route('/insert_student', methods=['POST'])
def insert_student():
    name = request.form['name']
    gender = request.form['gender']
    username = request.form['username']
    password = request.form['password']
    class_grade = int(request.form['class_grade'])
    section = request.form['section']

    # Step 1: Find class_id based on grade and section
    class_query = "SELECT Class_id FROM Class WHERE grade = %s AND section = %s"
    class_result = query_db(class_query, (class_grade, section), receive=True, one=True)

    if not class_result:
        print("Class not found. Please create the class first.", "error")
        return redirect(url_for('manage_students'))

    class_id = class_result['Class_id']

    # Step 2: Insert into Person table
    insert_person = """
        INSERT INTO Person (Name, Gender, Type, L_username, L_password)
        VALUES (%s, %s, 'Student', %s, %s)
    """
    query_db(insert_person, (name, gender, username, password), write=True)

    # Step 3: Fetch the newly inserted P_ID
    get_pid = "SELECT P_ID FROM Person WHERE L_username = %s"
    person = query_db(get_pid, (username,), receive=True, one=True)
    p_id = person['P_ID']

    # Step 4: Insert into Students table with Attendance = 100
    insert_student = """
        INSERT INTO Students (P_ID, Class_id, Attendance)
        VALUES (%s, %s, 100)
    """
    query_db(insert_student, (p_id, class_id), write=True)

    # Step 5: Insert 6 entries in Performance table (one for each subject)
    subjects = query_db("SELECT s_id FROM Subjects", receive=True)

    for subject in subjects:
        insert_performance = """
            INSERT INTO Performance (subject_id, student_id, marks)
            VALUES (%s, %s, 0)
        """
        query_db(insert_performance, (subject['s_id'], p_id), write=True)

    print("Student added successfully!", "success")
    return redirect(url_for('manage_students'))


# Delete Student
@app.route('/delete_student', methods=['POST'])
def delete_student():
    print("Delete Student route hit!")
    student_id = request.form['student_id']

    if not student_id:
        print("No student ID provided.")
        return redirect(url_for('manage_students'))

    try:
        # Delete from Person (this cascades to Students and sets student_id to NULL in Books)
        delete_query = """
            DELETE FROM Person
            WHERE P_ID = %s AND Type = 'Student'
        """
        query_db(delete_query, (student_id,), write=True)

        print(f"Student with ID {student_id} deleted successfully!")

    except Exception as e:
        print(f"Error deleting student: {e}")

    return redirect(url_for('manage_students'))


@app.route('/admin/manage_teachers')
def manage_teachers():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    # Get all available classes
    classes = query_db('SELECT Class_id, grade, section FROM Class', receive=True)

    return render_template('manage_teachers.html', classes=classes)


@app.route('/insert_teacher', methods=['POST'])
def insert_teacher():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    name = request.form['name']
    gender = request.form['gender']
    username = request.form['username']
    password = request.form['password']
    contact = request.form['contact']
    class_teacher = request.form['class_teacher']
    class_id = request.form.get('class_id') if class_teacher == 'yes' else None

    try:
        # Step 1: Insert into Person table
        insert_person = """
            INSERT INTO Person (Name, Gender, Type, L_username, L_password)
            VALUES (%s, %s, 'Teacher', %s, %s)
        """
        query_db(insert_person, (name, gender, username, password), write=True)

        # Step 2: Fetch the newly inserted P_ID
        get_pid = "SELECT P_ID FROM Person WHERE L_username = %s"
        person = query_db(get_pid, (username,), receive=True, one=True)
        p_id = person['P_ID']

        # Step 3: Insert into Teacher table
        insert_teacher = """
            INSERT INTO Teacher (P_ID, Contact)
            VALUES (%s, %s)
        """
        query_db(insert_teacher, (p_id, contact), write=True)

        # Step 4: If assigned as class teacher
        if class_id:
            assign_class_teacher = """
                UPDATE Class
                SET class_teacher_id = %s
                WHERE Class_id = %s
            """
            query_db(assign_class_teacher, (p_id, class_id), write=True)

        print("Teacher added successfully!", "success")
        return redirect(url_for('manage_teachers'))

    except Exception as e:
        print(f"Error inserting teacher: {e}")
        return "An error occurred while inserting the teacher."

# Delete Teacher
@app.route('/delete_teacher', methods=['POST'])
def delete_teacher():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    teacher_id = request.form['teacher_id']

    try:
        # Deleting Person will cascade delete Teacher
        query_db('DELETE FROM Person WHERE P_ID = %s', (teacher_id,), write=True)
        return redirect(url_for('manage_teachers'))

    except Exception as e:
        print(f"Error deleting teacher: {e}")
        return "An error occurred while deleting the teacher."


@app.route('/admin/teachers')
def teacher_list():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    # Only pull Name, Contact, Class Teacher info
    teachers = query_db("""
        SELECT 
            p.P_ID,
            p.Name AS teacher_name,
            t.Contact,
            CASE 
                WHEN c.Class_id IS NOT NULL THEN 'Yes'
                ELSE 'No'
            END AS is_class_teacher,
            CASE 
                WHEN c.Class_id IS NOT NULL THEN CONCAT('Class ', c.grade, c.section)
                ELSE NULL
            END AS class_assigned
        FROM Teacher t
        JOIN Person p ON t.P_ID = p.P_ID
        LEFT JOIN Class c ON t.P_ID = c.class_teacher_id
        ORDER BY p.Name ASC
    """, receive=True)

    if teachers is None:
        teachers = []

    return render_template("teacher_list.html", teachers=teachers)

@app.route('/admin/classes')
def class_list():
    if session.get('role') == 'admin':
        return render_template("class_list.html")
    return "Access Denied", 403

@app.route('/admin/classes/<grade>/<section>')
def student_list(grade, section):
    if session.get('role') != 'admin':
        return "Access Denied", 403

    # 1. Find the class_id for the selected grade and section
    class_row = query_db(
        "SELECT Class_id FROM Class WHERE grade = %s AND section = %s",
        (grade, section),
        receive=True
    )

    if not class_row:
        return "No student data found for given grade and section", 404

    class_id = class_row[0]['Class_id']

    # 2. Now get the students in this class
    students = query_db("""
        SELECT
            p.P_ID AS student_id,
            p.Name,
            s.Attendance,
            ROUND(AVG(perf.marks), 2) AS average_marks
        FROM Students s
        JOIN Person p ON s.P_ID = p.P_ID
        LEFT JOIN Performance perf ON s.P_ID = perf.student_id
        WHERE s.Class_id = %s
        GROUP BY p.P_ID, p.Name, s.Attendance
    """, (class_id,), receive=True)

    if students is None:
        students = []

    return render_template(
        "student_list.html",
        students=students,
        grade=grade,
        section=section
    )

@app.route('/admin/books', methods=['GET', 'POST'])
def books_inventory():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            title = request.form.get('title')
            author = request.form.get('author')
            query_db("INSERT INTO Books (B_title, B_author) VALUES (%s, %s)",
                     (title, author), write=True)

        elif action == 'delete':
            book_id = request.form.get('book_id')
            query_db("DELETE FROM Books WHERE B_id = %s", (book_id,), write=True)

        elif action == 'issue':
            book_id = request.form.get('book_id')
            student_id = request.form.get('student_id') or None
            today = datetime.date.today() if student_id else None

            query_db("""
                UPDATE Books
                SET student_id = %s, date_issued = %s
                WHERE B_id = %s
            """, (student_id, today, book_id), write=True)

        return redirect(url_for('books_inventory'))

    # ---- GET handling ----
    books = query_db("""
        SELECT 
            b.B_id, 
            b.B_title, 
            b.B_author,
            b.date_issued, 
            b.student_id,
            p.Name AS student_name
        FROM Books b
        LEFT JOIN Students s ON b.student_id = s.P_ID
        LEFT JOIN Person p ON s.P_ID = p.P_ID
    """, receive=True)

    students = query_db("""
        SELECT p.P_ID, p.Name
        FROM Students s
        JOIN Person p ON s.P_ID = p.P_ID
        WHERE s.P_ID NOT IN (SELECT student_id FROM Books WHERE student_id IS NOT NULL)
    """, receive=True)

    if books is None:
        books = []
    if students is None:
        students = []

    return render_template("books_inventory.html", books=books, students=students)


@app.route('/admin/timetable', methods=['GET', 'POST'])
def admin_timetable():
    if session.get('role') != 'admin':
        return "Access Denied", 403

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    timeslots = ['08:00 - 09:00', '09:00 - 10:00', '10:00 - 11:00',
                 '11:00 - 12:00', '12:00 - 01:00', '01:00 - 02:00', '02:00 - 03:00']

    subjects = query_db("SELECT s_id, s_title FROM Subjects", receive=True)
    classes = query_db("SELECT Class_id, grade, section FROM Class", receive=True)

    selected_day = request.args.get('day') or request.form.get('day')
    selected_class_id = request.args.get('class_id') or request.form.get('class_id')

    # Fetch free teachers for each timeslot
    free_teachers = {}
    for day in days:
        for t in timeslots:
            if t == '11:00 - 12:00':  # Break time
                continue
            available_teachers = query_db("""
                SELECT Teacher.P_ID, Person.Name
                FROM Teacher
                JOIN Person ON Teacher.P_ID = Person.P_ID
                LEFT JOIN Timetable ON Teacher.P_ID = Timetable.teacher_id
                    AND Timetable.day = %s AND Timetable.timeslot = %s
                WHERE Timetable.teacher_id IS NULL
            """, (day, t), receive=True)
            free_teachers[(day, t)] = available_teachers

    # If POST -> Insert new slots
    if request.method == 'POST' and selected_day and selected_class_id:
        for t in timeslots:
            if t == '11:00 - 12:00':
                continue

            subject_key = f'subject_{t}'
            teacher_key = f'teacher_{t}'

            subject_id = request.form.get(subject_key)
            teacher_id = request.form.get(teacher_key)

            if subject_id and teacher_id:
                # Check if slot already exists
                existing = query_db("""
                    SELECT * FROM Timetable WHERE class_id = %s AND day = %s AND timeslot = %s
                """, (selected_class_id, selected_day, t), receive=True)

                if not existing:
                    # Insert only if empty
                    query_db("""
                        INSERT INTO Timetable (timeslot, class_id, teacher_id, subject_id, day)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (t, selected_class_id, teacher_id, subject_id, selected_day))

        return redirect(url_for('admin_timetable', day=selected_day, class_id=selected_class_id))

    # Fetch existing timetable slots if both selected
    existing_slots = {}
    if selected_day and selected_class_id:
        existing_slots_query = query_db("""
            SELECT 
                timeslot, 
                Subjects.s_id AS subject_id, 
                Subjects.s_title AS subject_title,
                Teacher.P_ID AS teacher_id, 
                Person.Name AS teacher_name
            FROM Timetable
            JOIN Subjects ON Timetable.subject_id = Subjects.s_id
            JOIN Teacher ON Timetable.teacher_id = Teacher.P_ID
            JOIN Person ON Teacher.P_ID = Person.P_ID
            WHERE Timetable.day = %s AND Timetable.class_id = %s
        """, (selected_day, selected_class_id), receive=True)

        existing_slots = {slot['timeslot']: slot for slot in existing_slots_query}

    return render_template('admin_timetable.html',
                           days=days,
                           classes=classes,
                           subjects=subjects,
                           timeslots=timeslots,
                           existing_slots=existing_slots,
                           free_teachers=free_teachers,
                           selected_day=selected_day,
                           selected_class_id=selected_class_id)

@app.route('/admin/timetable/create', methods=['POST'])
def create_slot():
    class_id = request.form.get('class_id')
    day = request.form.get('day')
    timeslot = request.form.get('timeslot')
    subject_id = request.form.get('subject_id')
    teacher_id = request.form.get('teacher_id')

    # Insert into Timetable
    query_db('''
        INSERT INTO Timetable (timeslot, class_id, teacher_id, subject_id, day)
        VALUES (%s, %s, %s, %s, %s)
    ''', (timeslot, class_id, teacher_id, subject_id, day))

    return redirect(url_for('admin_timetable', day=day, class_id=class_id))


@app.route('/admin/timetable/clear', methods=['POST'])
def clear_slot():
    class_id = request.form['class_id']
    day = request.form['day']
    timeslot = request.form['timeslot']

    query_db("""
        DELETE FROM Timetable 
        WHERE class_id = %s AND day = %s AND timeslot = %s
    """, (class_id, day, timeslot))

    return redirect(url_for('admin_timetable', day=day, class_id=class_id))



# ---------- MAIN ----------
if __name__ == '__main__':
    app.run(debug=True)
