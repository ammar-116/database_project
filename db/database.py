import mysql.connector
from mysql.connector import Error


def get_db_connection():
    try:
        return mysql.connector.connect(
            host='localhost',
            user='root',
            password='1234',
            database='app_db'
        )
    except Error as e:
        print(f"Database connection error: {e}")
        return None

def query_db(query, args=None, receive=False, one=False, write=False):
    conn = get_db_connection()
    if conn is None:
        return None

    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, args or ())

            if write:
                conn.commit()
                return

            if receive:
                result = cursor.fetchall()
                return result[0] if one and result else result

            conn.commit()  # Commit if neither write nor receive, just to be safe

    except mysql.connector.Error as e:
        print(f"Query failed: {e}")
    finally:
        conn.close()


#------- SQL SCHEMA ---------#

# -- Base Person Table
# CREATE TABLE Person (
#     P_ID INT PRIMARY KEY AUTO_INCREMENT,
#     Name VARCHAR(100),
#     Gender VARCHAR(10),
#     Type ENUM('Admin', 'Teacher', 'Student'),
#     L_username VARCHAR(50) UNIQUE,
#     L_password VARCHAR(50)
# );
#
# -- Admin Subtype
# CREATE TABLE Admin (
#     P_ID INT PRIMARY KEY,
#     FOREIGN KEY (P_ID) REFERENCES Person(P_ID) ON DELETE CASCADE
# );
#
# -- Teacher Subtype
# CREATE TABLE Teacher (
#     P_ID INT PRIMARY KEY,
#     Contact VARCHAR(15),
#     FOREIGN KEY (P_ID) REFERENCES Person(P_ID) ON DELETE CASCADE
# );
#
# -- Subjects
# CREATE TABLE Subjects (
#     s_id INT PRIMARY KEY AUTO_INCREMENT,
#     s_title VARCHAR(50) UNIQUE
# );
#
#
# -- Class Table
# CREATE TABLE Class (
#     Class_id INT PRIMARY KEY AUTO_INCREMENT,
#     grade INT,
#     section CHAR(1),
#     class_teacher_id INT,
#     FOREIGN KEY (class_teacher_id) REFERENCES Teacher(P_ID) ON DELETE SET NULL
# );
#
# -- Student Subtype
# CREATE TABLE Students (
#     P_ID INT PRIMARY KEY,
#     Class_id INT,
#     Attendance INT,
#     FOREIGN KEY (P_ID) REFERENCES Person(P_ID) ON DELETE CASCADE,
#     FOREIGN KEY (Class_id) REFERENCES Class(Class_id)
# );
#
# -- Timetable
# CREATE TABLE Timetable (
#     T_id INT PRIMARY KEY AUTO_INCREMENT,
#     timeslot VARCHAR(20),
#     class_id INT,
#     teacher_id INT,
#     subject_id INT,
#     day VARCHAR(10),
#     FOREIGN KEY (class_id) REFERENCES Class(Class_id),
#     FOREIGN KEY (teacher_id) REFERENCES Teacher(P_ID) ON DELETE cascade,
#     FOREIGN KEY (subject_id) REFERENCES Subjects(s_id),
#     UNIQUE (timeslot, class_id, day)
# );
#
# -- Books
# CREATE TABLE Books (
#     B_id INT PRIMARY KEY AUTO_INCREMENT,
#     B_title VARCHAR(100),
#     B_author VARCHAR(100),
#     date_issued DATE,
#     student_id INT UNIQUE,
#     FOREIGN KEY (student_id) REFERENCES Students(P_ID) ON DELETE SET NULL
# );
#
#
# -- Performance
# CREATE TABLE Performance (
#     subject_id INT,
#     student_id INT,
#     marks INT,
#     PRIMARY KEY (subject_id, student_id),
#     FOREIGN KEY (subject_id) REFERENCES Subjects(s_id),
#     FOREIGN KEY (student_id) REFERENCES Students(P_ID) ON DELETE CASCADE
# );
#
#
#
#
# select* from students;
# select* from performance;
# select* from person;
# select* from teacher;
# select* from books;
# select* from class;
