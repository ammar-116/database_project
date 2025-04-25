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




