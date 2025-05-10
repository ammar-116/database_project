# Database Project - School Management System

A web-based CRUD application built with **Flask** and **MySQL**, designed to interact with a backend database for data management operations. The application allows users to perform Create, Read, Update, and Delete functionalities via a browser interface.

---

## Project Overview

This portal allows seamless interaction with a school database system through a user-friendly web interface. Here's how the user roles function:

- **Admin:** Full control over the platform. Can manage users, classes, timetables and academic data.
- **Teacher:** Can view and update student grades, take attendance, and manage class-specific data.
- **Student:** Can view personal academic performance, class schedules, and announcements.

The system ensures role-based access control to protect data integrity and privacy.

---

## Project Structure

```
database_project/
│
├── app.py                  # Main application file
├── db/                     # Handles MySQL backend connections, has the MySQL code in the comments
├── static/                 # Contains CSS files
└── templates/              # Contains HTML templates with embedded SQL queries
```

---

## Getting Started

Follow these steps to set up and run the project locally.

### 1. Clone the Repository

Navigate to the directory to where you want the folder to be created.
```bash
git clone https://github.com/ammar-116/database_project.git
cd database_project
```

### 2. Install Dependencies

Make sure you have Python installed. Set up a virtual environment. Then, install required libraries using pip:

```bash
pip3 install virtualenv
python -m venv env
.\env\Scripts\activate
pip install flask mysql-connector-python
```

### 3. Set Up the MySQL Database

- Ensure MySQL is installed and running.
- Edit server details in database.py for your own server.
- Create the required tables and insert data as needed.
- Database schema and insertion scripts are provided in the comments in the database.py file (refer to the `db/` directory).

### 4. Run the Application

```bash
python app.py
```

Then, open your web browser and navigate to:

```
http://localhost:5000
```

---

## License

This project is licensed under the [MIT License](LICENSE).  
You are free to use, modify, and distribute this software with attribution.

---

## Acknowledgements

If you use this project, please cite the original repository:  
**[ammar-116/database_project](https://github.com/ammar-116/database_project)**
