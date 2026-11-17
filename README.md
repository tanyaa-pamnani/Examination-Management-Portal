# Examination Management Portal (EMP)

A web-based Examination Management Portal developed using Flask and SQLite to simplify and manage examination scheduling, slot booking, examiner assignments, and student evaluation.

## Project Overview

The Examination Management Portal provides a centralized platform for managing examination-related activities through three user roles: Admin, Examiner, and Student.

It helps automate examination administration, reduce manual scheduling work, and provide a structured evaluation process.

## Features

### Admin
- Manage courses and examinations.
- Add, edit, and delete examination details.
- Approve and deactivate examiners.
- Assign examiners to examinations.
- Create and manage examination rubrics.
- View and manage examination schedules and bookings.
- Reschedule student bookings and change examiner assignments.
- Configure booking windows and cancellation deadlines.
- Search and filter users, examinations, slots, and bookings.

### Examiner
- Register and log in to the portal.
- View assigned examinations.
- Create and manage examination slots.
- View students booked for examinations.
- Evaluate students using examination rubrics.
- Submit marks and feedback.

### Student
- Register and log in to the portal.
- Browse available examinations and slots.
- Book and cancel examination slots according to deadlines.
- View booking history and status.
- View examination results and examiner feedback.

## Technologies Used

- **Backend:** Python, Flask
- **Frontend:** HTML, CSS, Bootstrap, Jinja2
- **Database:** SQLite
- **Authentication:** Flask-Login
- **ORM:** Flask-SQLAlchemy
- **Version Control:** Git and GitHub

## Project Structure

```text
Examination-Management-Portal/
│
├── app.py
├── models.py
├── requirements.txt
├── .gitignore
│
└── templates/
    ├── admin/
    ├── examiner/
    ├── student/
    ├── login.html
    ├── examiner_register.html
    └── student_register.html
```

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/tanyaa-pamnani/Examination-Management-Portal.git
```

### 2. Navigate to the project folder

```bash
cd Examination-Management-Portal
```

### 3. Create a virtual environment

```bash
python -m venv venv
```

### 4. Activate the virtual environment

**Windows:**

```bash
venv\Scripts\activate
```

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

### 6. Run the application

```bash
python app.py
```

### 7. Open the application

Visit:

http://127.0.0.1:5000

The SQLite database is created programmatically by the application.

## Database

The application uses SQLite for storing information related to:

- Users and roles
- Courses
- Examinations
- Examiner assignments
- Examination slots
- Student bookings
- Evaluation rubrics
- Student results and feedback

## Key Functionalities

- Role-based access control.
- Examiner approval workflow.
- Examination slot scheduling.
- Prevention of duplicate active bookings.
- Booking capacity management.
- Configurable booking and cancellation deadlines.
- Rubric-based student evaluation.
- Centralized schedule and booking management.

## Future Enhancements

- Email notifications for booking confirmations.
- Automated timetable generation.
- Downloadable examination reports.
- Advanced analytics for examination performance.

## Author

Developed as an academic project.

**Project:** Examination Management Portal (EMP)
