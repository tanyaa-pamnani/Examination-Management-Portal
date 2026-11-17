from datetime import date, datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from flask_login import (
    LoginManager, login_user, login_required,
    current_user, logout_user
)
from werkzeug.security import generate_password_hash, check_password_hash

from models import (
    db, User, Course, Examination, ExaminerProfile,
    ExamAssignment, ExamSlot, Booking,
    Rubric, Evaluation, EvaluationScore
)


class EMPSetting(db.Model):
    __tablename__ = "emp_settings"

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(80), unique=True, nullable=False)
    setting_value = db.Column(db.String(200), nullable=False)


def get_emp_setting(key, default):
    setting = EMPSetting.query.filter_by(setting_key=key).first()
    return setting.setting_value if setting else default


def set_emp_setting(key, value):
    setting = EMPSetting.query.filter_by(setting_key=key).first()
    if setting is None:
        setting = EMPSetting(setting_key=key, setting_value=str(value))
        db.session.add(setting)
    else:
        setting.setting_value = str(value)


app = Flask(__name__)

app.config["SECRET_KEY"] = "emp-secret-key-2026"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///emp.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# CREATE DATABASE TABLES AND DEFAULT ADMIN
with app.app_context():
    db.create_all()

    admin = User.query.filter_by(email="admin@emp.com").first()

    if not admin:
        admin = User(
            name="Admin",
            email="admin@emp.com",
            password=generate_password_hash("admin123"),
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()


# ACCESS CHECK
def admin_required():
    return current_user.is_authenticated and current_user.role == "admin"


# HOME
@app.route("/")
def home():
    return redirect(url_for("login"))


# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):

            if not user.active:
                if user.role == "examiner":
                    flash("Your examiner account is awaiting approval or is deactivated.", "warning")
                else:
                    flash("Your account is deactivated.", "danger")

                return redirect(url_for("login"))

            login_user(user)

            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))

            elif user.role == "student":
                return redirect(url_for("student_dashboard"))

            elif user.role == "examiner":
                return redirect(url_for("examiner_dashboard"))

        flash("Incorrect email or password.", "danger")

    return render_template("login.html")


# STUDENT REGISTRATION
@app.route("/student/register", methods=["GET", "POST"])
def student_register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("student_register.html")

        if User.query.filter_by(email=email).first():
            flash("This email is already registered.", "danger")
            return render_template("student_register.html")

        student = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
            role="student"
        )

        db.session.add(student)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("student_register.html")


# EXAMINER REGISTRATION
@app.route("/examiner/register", methods=["GET", "POST"])
def examiner_register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        department = request.form.get("department", "").strip()
        qualification = request.form.get("qualification", "").strip()
        phone = request.form.get("phone", "").strip()

        if not all([name, email, password, department, qualification, phone]):
            flash("All fields are required.", "danger")
            return render_template("examiner_register.html")

        if User.query.filter_by(email=email).first():
            flash("This email is already registered.", "danger")
            return render_template("examiner_register.html")

        examiner = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
            role="examiner",
            active=False
        )

        db.session.add(examiner)
        db.session.flush()

        profile = ExaminerProfile(
            user_id=examiner.id,
            department=department,
            qualification=qualification,
            phone=phone
        )

        db.session.add(profile)
        db.session.commit()

        flash("Registration submitted! Wait for Admin approval.", "success")
        return redirect(url_for("login"))

    return render_template("examiner_register.html")


# STUDENT DASHBOARD
@app.route("/student/dashboard")
@login_required
def student_dashboard():

    if current_user.role != "student":
        return "Access denied", 403

    return render_template("student/dashboard.html")


# EXAMINER DASHBOARD
@app.route("/examiner/dashboard")
@login_required
def examiner_dashboard():

    if current_user.role != "examiner" or not current_user.active:
        return "Access denied", 403

    return render_template("examiner/dashboard.html")


# ADMIN DASHBOARD
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():

    if not admin_required():
        return "Access denied", 403

    course_count = Course.query.count()
    exam_count = Examination.query.count()

    pending_count = User.query.filter_by(
        role="examiner",
        active=False
    ).count()

    return render_template(
        "admin/dashboard.html",
        course_count=course_count,
        exam_count=exam_count,
        pending_count=pending_count
    )


# ---------------- COURSE MANAGEMENT ----------------

@app.route("/admin/courses")
@login_required
def view_courses():

    if not admin_required():
        return "Access denied", 403

    courses = Course.query.order_by(Course.course_code).all()

    return render_template("admin/courses.html", courses=courses)


@app.route("/admin/courses/add", methods=["GET", "POST"])
@login_required
def add_course():

    if not admin_required():
        return "Access denied", 403

    if request.method == "POST":

        code = request.form.get("course_code", "").strip().upper()
        name = request.form.get("course_name", "").strip()
        description = request.form.get("description", "").strip()

        if not code or not name:
            flash("Course code and name are required.", "danger")
            return render_template("admin/add_course.html")

        if Course.query.filter_by(course_code=code).first():
            flash("This course code already exists.", "danger")
            return render_template("admin/add_course.html")

        course = Course(
            course_code=code,
            course_name=name,
            description=description
        )

        db.session.add(course)
        db.session.commit()

        flash("Course added successfully!", "success")
        return redirect(url_for("view_courses"))

    return render_template("admin/add_course.html")


@app.route("/admin/courses/edit/<int:course_id>", methods=["GET", "POST"])
@login_required
def edit_course(course_id):

    if not admin_required():
        return "Access denied", 403

    course = db.session.get(Course, course_id)

    if not course:
        return "Course not found", 404

    if request.method == "POST":

        code = request.form.get("course_code", "").strip().upper()
        name = request.form.get("course_name", "").strip()
        description = request.form.get("description", "").strip()

        duplicate = Course.query.filter(
            Course.course_code == code,
            Course.id != course.id
        ).first()

        if not code or not name:
            flash("Course code and name are required.", "danger")

        elif duplicate:
            flash("This course code already exists.", "danger")

        else:
            course.course_code = code
            course.course_name = name
            course.description = description

            db.session.commit()

            flash("Course updated successfully!", "success")
            return redirect(url_for("view_courses"))

    return render_template("admin/edit_course.html", course=course)


@app.route("/admin/courses/delete/<int:course_id>", methods=["POST"])
@login_required
def delete_course(course_id):

    if not admin_required():
        return "Access denied", 403

    course = db.session.get(Course, course_id)

    if not course:
        return "Course not found", 404

    if Examination.query.filter_by(course_id=course.id).first():
        flash("Cannot delete a course linked to an examination.", "danger")
        return redirect(url_for("view_courses"))

    db.session.delete(course)
    db.session.commit()

    flash("Course deleted successfully.", "success")
    return redirect(url_for("view_courses"))


# ---------------- EXAMINATION MANAGEMENT ----------------

@app.route("/admin/examinations")
@login_required
def view_examinations():

    if not admin_required():
        return "Access denied", 403

    examinations = Examination.query.order_by(
        Examination.exam_date
    ).all()

    return render_template(
        "admin/examinations.html",
        examinations=examinations
    )


@app.route("/admin/examinations/add", methods=["GET", "POST"])
@login_required
def add_examination():

    if not admin_required():
        return "Access denied", 403

    courses = Course.query.order_by(Course.course_code).all()

    if not courses:
        flash("Add a course before creating an examination.", "warning")
        return redirect(url_for("view_courses"))

    if request.method == "POST":

        exam_name = request.form.get("exam_name", "").strip()
        exam_date = request.form.get("exam_date", "")
        description = request.form.get("description", "").strip()

        try:
            course_id = int(request.form.get("course_id", ""))
            duration = int(request.form.get("duration", ""))
            max_marks = int(request.form.get("max_marks", ""))
        except (ValueError, TypeError):
            flash("Enter valid course, duration and marks.", "danger")
            return render_template("admin/add_examination.html", courses=courses)

        course = db.session.get(Course, course_id)

        if not exam_name or not exam_date or not course:
            flash("Please complete all required fields.", "danger")

        elif duration <= 0 or max_marks <= 0:
            flash("Duration and marks must be positive.", "danger")

        else:
            exam = Examination(
                exam_name=exam_name,
                course_id=course_id,
                exam_date=exam_date,
                duration=duration,
                max_marks=max_marks,
                description=description
            )

            db.session.add(exam)
            db.session.commit()

            flash("Examination created successfully!", "success")
            return redirect(url_for("view_examinations"))

    return render_template("admin/add_examination.html", courses=courses)


@app.route("/admin/examinations/edit/<int:exam_id>", methods=["GET", "POST"])
@login_required
def edit_examination(exam_id):

    if not admin_required():
        return "Access denied", 403

    examination = db.session.get(Examination, exam_id)

    if not examination:
        return "Examination not found", 404

    courses = Course.query.order_by(Course.course_code).all()

    if request.method == "POST":

        exam_name = request.form.get("exam_name", "").strip()
        exam_date = request.form.get("exam_date", "")
        description = request.form.get("description", "").strip()

        try:
            course_id = int(request.form.get("course_id", ""))
            duration = int(request.form.get("duration", ""))
            max_marks = int(request.form.get("max_marks", ""))
        except (ValueError, TypeError):
            flash("Enter valid course, duration and marks.", "danger")
            return render_template(
                "admin/edit_examination.html",
                examination=examination,
                courses=courses
            )

        course = db.session.get(Course, course_id)

        if not exam_name or not exam_date or not course:
            flash("Please complete all required fields.", "danger")

        elif duration <= 0 or max_marks <= 0:
            flash("Duration and marks must be positive.", "danger")

        else:
            examination.exam_name = exam_name
            examination.course_id = course_id
            examination.exam_date = exam_date
            examination.duration = duration
            examination.max_marks = max_marks
            examination.description = description

            db.session.commit()

            flash("Examination updated successfully!", "success")
            return redirect(url_for("view_examinations"))

    return render_template(
        "admin/edit_examination.html",
        examination=examination,
        courses=courses
    )


@app.route("/admin/examinations/delete/<int:exam_id>", methods=["POST"])
@login_required
def delete_examination(exam_id):

    if not admin_required():
        return "Access denied", 403

    examination = db.session.get(Examination, exam_id)

    if not examination:
        return "Examination not found", 404

    db.session.delete(examination)
    db.session.commit()

    flash("Examination deleted successfully.", "success")
    return redirect(url_for("view_examinations"))


# ---------------- EXAMINER MANAGEMENT ----------------

# VIEW ALL EXAMINERS
@app.route("/admin/examiners")
@login_required
def view_examiners():

    if not admin_required():
        return "Access denied", 403

    examiners = User.query.filter_by(role="examiner").order_by(User.name).all()

    return render_template("admin/examiners.html", examiners=examiners)


# APPROVE EXAMINER
@app.route("/admin/examiners/approve/<int:user_id>", methods=["POST"])
@login_required
def approve_examiner(user_id):

    if not admin_required():
        return "Access denied", 403

    examiner = db.session.get(User, user_id)

    if not examiner or examiner.role != "examiner":
        return "Examiner not found", 404

    examiner.active = True
    db.session.commit()

    flash("Examiner approved successfully!", "success")
    return redirect(url_for("view_examiners"))


# DEACTIVATE EXAMINER
@app.route("/admin/examiners/deactivate/<int:user_id>", methods=["POST"])
@login_required
def deactivate_examiner(user_id):

    if not admin_required():
        return "Access denied", 403

    examiner = db.session.get(User, user_id)

    if not examiner or examiner.role != "examiner":
        return "Examiner not found", 404

    examiner.active = False
    db.session.commit()

    flash("Examiner deactivated.", "success")
    return redirect(url_for("view_examiners"))

# ---------------- EXAMINER ASSIGNMENT ----------------

# ADMIN: VIEW ASSIGNMENTS AND ASSIGN EXAMINERS
@app.route("/admin/assign-examiners", methods=["GET", "POST"])
@login_required
def assign_examiners():

    if not admin_required():
        return "Access denied", 403

    examinations = Examination.query.order_by(
        Examination.exam_date
    ).all()

    examiners = User.query.filter_by(
        role="examiner",
        active=True
    ).order_by(User.name).all()

    if request.method == "POST":

        try:
            examination_id = int(request.form.get("examination_id", ""))
            examiner_id = int(request.form.get("examiner_id", ""))
        except (ValueError, TypeError):
            flash("Please select a valid examination and examiner.", "danger")
            return redirect(url_for("assign_examiners"))

        examination = db.session.get(Examination, examination_id)
        examiner = db.session.get(User, examiner_id)

        if not examination or not examiner or examiner.role != "examiner" or not examiner.active:
            flash("Invalid examination or examiner.", "danger")

        else:
            existing = ExamAssignment.query.filter_by(
                examination_id=examination_id,
                examiner_id=examiner_id
            ).first()

            if existing:
                flash("This examiner is already assigned to this examination.", "warning")
            else:
                assignment = ExamAssignment(
                    examination_id=examination_id,
                    examiner_id=examiner_id
                )

                db.session.add(assignment)
                db.session.commit()

                flash("Examiner assigned successfully!", "success")

        return redirect(url_for("assign_examiners"))

    assignments = ExamAssignment.query.order_by(
        ExamAssignment.id.desc()
    ).all()

    return render_template(
        "admin/assign_examiners.html",
        examinations=examinations,
        examiners=examiners,
        assignments=assignments
    )


# ADMIN: REMOVE AN EXAMINER ASSIGNMENT
@app.route("/admin/assignments/delete/<int:assignment_id>", methods=["POST"])
@login_required
def delete_assignment(assignment_id):

    if not admin_required():
        return "Access denied", 403

    assignment = db.session.get(ExamAssignment, assignment_id)

    if not assignment:
        return "Assignment not found", 404

    db.session.delete(assignment)
    db.session.commit()

    flash("Examiner assignment removed.", "success")
    return redirect(url_for("assign_examiners"))




# ---------------- RUBRIC MANAGEMENT ----------------

@app.route("/admin/rubrics", methods=["GET"])
@login_required
def view_rubrics():
    if not admin_required():
        return "Access denied", 403

    examinations = Examination.query.order_by(Examination.exam_date).all()
    rubrics = Rubric.query.join(Examination).order_by(
        Examination.exam_date, Rubric.id
    ).all()

    return render_template(
        "admin/rubrics.html",
        examinations=examinations,
        rubrics=rubrics
    )


@app.route("/admin/rubrics/add", methods=["POST"])
@login_required
def add_rubric():
    if not admin_required():
        return "Access denied", 403

    try:
        examination_id = int(request.form.get("examination_id", ""))
        max_marks = int(request.form.get("max_marks", ""))
    except (ValueError, TypeError):
        flash("Choose an examination and enter valid maximum marks.", "danger")
        return redirect(url_for("view_rubrics"))

    criterion = request.form.get("criterion", "").strip()
    description = request.form.get("description", "").strip()
    examination = db.session.get(Examination, examination_id)

    if not examination or not criterion:
        flash("Examination and criterion are required.", "danger")
    elif max_marks <= 0:
        flash("Maximum marks must be greater than zero.", "danger")
    elif Rubric.query.filter_by(
        examination_id=examination_id, criterion=criterion
    ).first():
        flash("That criterion already exists for this examination.", "warning")
    else:
        current_total = db.session.query(
            db.func.coalesce(db.func.sum(Rubric.max_marks), 0)
        ).filter_by(examination_id=examination_id).scalar()

        if current_total + max_marks > examination.max_marks:
            flash(
                f"Rubric maximum cannot exceed the examination total "
                f"({examination.max_marks} marks).",
                "danger"
            )
        else:
            db.session.add(Rubric(
                examination_id=examination_id,
                criterion=criterion,
                description=description,
                max_marks=max_marks
            ))
            db.session.commit()
            flash("Rubric criterion added successfully.", "success")

    return redirect(url_for("view_rubrics"))


@app.route("/admin/rubrics/delete/<int:rubric_id>", methods=["POST"])
@login_required
def delete_rubric(rubric_id):
    if not admin_required():
        return "Access denied", 403

    rubric = db.session.get(Rubric, rubric_id)
    if not rubric:
        return "Rubric not found", 404

    if EvaluationScore.query.filter_by(rubric_id=rubric.id).first():
        flash("This criterion has already been used and cannot be deleted.", "danger")
    else:
        db.session.delete(rubric)
        db.session.commit()
        flash("Rubric criterion deleted.", "success")

    return redirect(url_for("view_rubrics"))


# ---------------- EXAMINER EVALUATION ----------------

@app.route("/examiner/evaluate/<int:booking_id>", methods=["GET", "POST"])
@login_required
def evaluate_booking(booking_id):
    if current_user.role != "examiner" or not current_user.active:
        return "Access denied", 403

    booking = db.session.get(Booking, booking_id)
    if not booking:
        return "Booking not found", 404

    slot = booking.slot
    if not slot or slot.examiner_id != current_user.id:
        return "You cannot evaluate a student assigned to another examiner.", 403

    if booking.status != "active":
        flash("Only active bookings can be evaluated.", "warning")
        return redirect(url_for("examiner_bookings"))

    rubrics = Rubric.query.filter_by(
        examination_id=booking.examination_id
    ).order_by(Rubric.id).all()

    if not rubrics:
        flash("The Admin must create a marking rubric for this examination first.", "warning")
        return redirect(url_for("examiner_bookings"))

    evaluation = Evaluation.query.filter_by(booking_id=booking.id).first()

    if request.method == "POST":
        submitted_scores = []
        total_marks = 0

        for rubric in rubrics:
            try:
                marks = int(request.form.get(f"score_{rubric.id}", ""))
            except (ValueError, TypeError):
                flash(f"Enter valid marks for {rubric.criterion}.", "danger")
                return render_template(
                    "examiner/evaluate.html",
                    booking=booking,
                    rubrics=rubrics,
                    evaluation=evaluation
                )

            if marks < 0 or marks > rubric.max_marks:
                flash(
                    f"Marks for {rubric.criterion} must be between 0 and {rubric.max_marks}.",
                    "danger"
                )
                return render_template(
                    "examiner/evaluate.html",
                    booking=booking,
                    rubrics=rubrics,
                    evaluation=evaluation
                )

            submitted_scores.append((rubric, marks))
            total_marks += marks

        if total_marks > booking.examination.max_marks:
            flash("Total marks exceed the examination maximum.", "danger")
            return render_template(
                "examiner/evaluate.html",
                booking=booking,
                rubrics=rubrics,
                evaluation=evaluation
            )

        remarks = request.form.get("remarks", "").strip()

        if evaluation is None:
            evaluation = Evaluation(
                booking_id=booking.id,
                examiner_id=current_user.id,
                total_marks=total_marks,
                remarks=remarks
            )
            db.session.add(evaluation)
            db.session.flush()
        else:
            evaluation.examiner_id = current_user.id
            evaluation.total_marks = total_marks
            evaluation.remarks = remarks
            evaluation.evaluated_at = datetime.now()

        for rubric, marks in submitted_scores:
            score = EvaluationScore.query.filter_by(
                evaluation_id=evaluation.id,
                rubric_id=rubric.id
            ).first()

            if score is None:
                db.session.add(EvaluationScore(
                    evaluation_id=evaluation.id,
                    rubric_id=rubric.id,
                    marks_awarded=marks
                ))
            else:
                score.marks_awarded = marks

        db.session.commit()
        flash("Evaluation saved successfully.", "success")
        return redirect(url_for("examiner_bookings"))

    return render_template(
        "examiner/evaluate.html",
        booking=booking,
        rubrics=rubrics,
        evaluation=evaluation
    )


# ---------------- STUDENT RESULTS ----------------

@app.route("/student/results")
@login_required
def student_results():
    if current_user.role != "student":
        return "Access denied", 403

    bookings = Booking.query.filter_by(
        student_id=current_user.id
    ).order_by(Booking.booked_at.desc()).all()

    return render_template("student/results.html", bookings=bookings)


# ---------------- EXAMINER SLOT MANAGEMENT ----------------

# EXAMINER: VIEW ASSIGNED EXAMINATIONS AND SLOTS
@app.route("/examiner/slots")
@login_required
def examiner_slots():

    if current_user.role != "examiner" or not current_user.active:
        return "Access denied", 403

    assignments = ExamAssignment.query.filter_by(
        examiner_id=current_user.id
    ).all()

    slots = ExamSlot.query.filter_by(
        examiner_id=current_user.id
    ).order_by(ExamSlot.slot_date, ExamSlot.start_time).all()

    return render_template(
        "examiner/slots.html",
        assignments=assignments,
        slots=slots
    )


# EXAMINER: VIEW STUDENTS BOOKED INTO THIS EXAMINER'S SLOTS
@app.route("/examiner/bookings")
@login_required
def examiner_bookings():

    if current_user.role != "examiner" or not current_user.active:
        return "Access denied", 403

    bookings = Booking.query.join(ExamSlot).filter(
        ExamSlot.examiner_id == current_user.id
    ).order_by(
        ExamSlot.slot_date, ExamSlot.start_time, Booking.booked_at
    ).all()

    return render_template(
        "examiner/bookings.html",
        bookings=bookings
    )


# EXAMINER: CREATE A SLOT
@app.route("/examiner/slots/add", methods=["GET", "POST"])
@login_required
def add_exam_slot():

    if current_user.role != "examiner" or not current_user.active:
        return "Access denied", 403

    assignments = ExamAssignment.query.filter_by(
        examiner_id=current_user.id
    ).all()

    if not assignments:
        flash("You have not been assigned to any examinations yet.", "warning")
        return redirect(url_for("examiner_slots"))

    if request.method == "POST":

        try:
            examination_id = int(request.form.get("examination_id", ""))
            capacity = int(request.form.get("capacity", ""))
        except (ValueError, TypeError):
            flash("Please enter valid examination and capacity values.", "danger")
            return redirect(url_for("add_exam_slot"))

        slot_date = request.form.get("slot_date", "")
        start_time = request.form.get("start_time", "")
        end_time = request.form.get("end_time", "")

        assigned_ids = [a.examination_id for a in assignments]

        if examination_id not in assigned_ids:
            flash("You cannot create a slot for an unassigned examination.", "danger")

        elif not slot_date or not start_time or not end_time:
            flash("All date and time fields are required.", "danger")

        elif capacity <= 0:
            flash("Slot capacity must be greater than zero.", "danger")

        elif end_time <= start_time:
            flash("End time must be later than start time.", "danger")

        else:
            examination = db.session.get(Examination, examination_id)

            if slot_date != examination.exam_date:
                flash("The slot date must match the examination date.", "danger")
            else:
                slot = ExamSlot(
                    examination_id=examination_id,
                    examiner_id=current_user.id,
                    slot_date=slot_date,
                    start_time=start_time,
                    end_time=end_time,
                    capacity=capacity
                )

                db.session.add(slot)
                db.session.commit()

                flash("Examination slot created successfully!", "success")
                return redirect(url_for("examiner_slots"))

        return redirect(url_for("add_exam_slot"))

    return render_template(
        "examiner/add_slot.html",
        assignments=assignments
    )


# EXAMINER: DELETE OWN SLOT
@app.route("/examiner/slots/delete/<int:slot_id>", methods=["POST"])
@login_required
def delete_exam_slot(slot_id):

    if current_user.role != "examiner" or not current_user.active:
        return "Access denied", 403

    slot = db.session.get(ExamSlot, slot_id)

    if not slot:
        return "Slot not found", 404

    if slot.examiner_id != current_user.id:
        return "You cannot delete another examiner's slot.", 403

    if Booking.query.filter_by(slot_id=slot.id).first():
        flash("This slot has booking history and cannot be deleted.", "danger")
        return redirect(url_for("examiner_slots"))

    db.session.delete(slot)
    db.session.commit()

    flash("Slot deleted successfully.", "success")
    return redirect(url_for("examiner_slots"))



# ---------------- STUDENT EXAMINATION BOOKING ----------------

# STUDENT: VIEW AVAILABLE EXAMINATION SLOTS
@app.route("/student/exams")
@login_required
def student_exams():

    if current_user.role != "student":
        return "Access denied", 403

    today = date.today().isoformat()

    slots = ExamSlot.query.filter(
        ExamSlot.slot_date >= today
    ).order_by(
        ExamSlot.slot_date,
        ExamSlot.start_time
    ).all()

    booking_counts = {}
    for slot in slots:
        booking_counts[slot.id] = Booking.query.filter_by(
            slot_id=slot.id,
            status="active"
        ).count()

    active_bookings = Booking.query.filter_by(
        student_id=current_user.id,
        status="active"
    ).all()

    active_exam_ids = {booking.examination_id for booking in active_bookings}

    return render_template(
        "student/exams.html",
        slots=slots,
        booking_counts=booking_counts,
        active_exam_ids=active_exam_ids,
        now=datetime.now().strftime("%Y-%m-%d %H:%M")
    )


# STUDENT: BOOK AN EXAMINATION SLOT
@app.route("/student/book/<int:slot_id>", methods=["POST"])
@login_required
def book_exam_slot(slot_id):

    if current_user.role != "student":
        return "Access denied", 403

    if get_emp_setting("booking_enabled", "yes") != "yes":
        flash("Student booking is currently closed by the Admin.", "warning")
        return redirect(url_for("student_exams"))

    now = datetime.now()
    opens_at = get_emp_setting("booking_opens_at", "")
    closes_at = get_emp_setting("booking_closes_at", "")
    try:
        if opens_at and now < datetime.strptime(opens_at, "%Y-%m-%dT%H:%M"):
            flash("The booking period has not opened yet.", "warning")
            return redirect(url_for("student_exams"))
        if closes_at and now >= datetime.strptime(closes_at, "%Y-%m-%dT%H:%M"):
            flash("The booking period is closed.", "warning")
            return redirect(url_for("student_exams"))
    except ValueError:
        flash("Booking settings contain an invalid date/time. Contact the Admin.", "danger")
        return redirect(url_for("student_exams"))

    try:
        # Acquire SQLite's write lock before checking capacity. This makes
        # the capacity check and insertion a single serialized operation.
        db.session.execute(text("BEGIN IMMEDIATE"))

        slot = db.session.get(ExamSlot, slot_id)

        if not slot:
            db.session.rollback()
            flash("This examination slot does not exist.", "danger")
            return redirect(url_for("student_exams"))

        slot_start = datetime.strptime(
            f"{slot.slot_date} {slot.start_time}",
            "%Y-%m-%d %H:%M"
        )

        if slot_start <= datetime.now():
            db.session.rollback()
            flash("This slot has already started or passed.", "warning")
            return redirect(url_for("student_exams"))

        existing_booking = Booking.query.filter_by(
            student_id=current_user.id,
            examination_id=slot.examination_id,
            status="active"
        ).first()

        if existing_booking:
            db.session.rollback()
            flash("You already have an active booking for this examination.", "warning")
            return redirect(url_for("student_exams"))

        active_count = Booking.query.filter_by(
            slot_id=slot.id,
            status="active"
        ).count()

        if active_count >= slot.capacity:
            db.session.rollback()
            flash("Sorry, this slot is full. Please choose another slot.", "warning")
            return redirect(url_for("student_exams"))

        booking = Booking(
            slot_id=slot.id,
            examination_id=slot.examination_id,
            student_id=current_user.id,
            status="active"
        )

        db.session.add(booking)
        db.session.commit()

        flash("Your examination slot has been booked successfully!", "success")
        return redirect(url_for("student_bookings"))

    except IntegrityError:
        db.session.rollback()
        flash("You already have an active booking for this examination.", "warning")
        return redirect(url_for("student_exams"))

    except (ValueError, TypeError):
        db.session.rollback()
        flash("The slot has an invalid date or time.", "danger")
        return redirect(url_for("student_exams"))


# STUDENT: VIEW CURRENT AND PREVIOUS BOOKINGS
@app.route("/student/bookings")
@login_required
def student_bookings():

    if current_user.role != "student":
        return "Access denied", 403

    bookings = Booking.query.filter_by(
        student_id=current_user.id
    ).order_by(
        Booking.booked_at.desc()
    ).all()

    return render_template(
        "student/bookings.html",
        bookings=bookings,
        now=datetime.now()
    )


# STUDENT: CANCEL A BOOKING
@app.route("/student/bookings/cancel/<int:booking_id>", methods=["POST"])
@login_required
def cancel_booking(booking_id):

    if current_user.role != "student":
        return "Access denied", 403

    booking = db.session.get(Booking, booking_id)

    if not booking or booking.student_id != current_user.id:
        return "Booking not found", 404

    if booking.status != "active":
        flash("This booking is already cancelled.", "warning")
        return redirect(url_for("student_bookings"))

    try:
        slot_start = datetime.strptime(
            f"{booking.slot.slot_date} {booking.slot.start_time}",
            "%Y-%m-%d %H:%M"
        )
    except (ValueError, TypeError):
        flash("The slot has an invalid date or time; contact the Admin.", "danger")
        return redirect(url_for("student_bookings"))

    # Cancellation cutoff is configurable by the Admin (default: 24 hours).
    try:
        cancellation_hours = int(get_emp_setting("cancellation_hours", "24"))
    except ValueError:
        cancellation_hours = 24
    cancellation_deadline = slot_start - timedelta(hours=cancellation_hours)

    if datetime.now() >= cancellation_deadline:
        flash("Cancellation is closed within 24 hours of the slot start time.", "danger")
        return redirect(url_for("student_bookings"))

    booking.status = "cancelled"
    booking.cancelled_at = datetime.now()
    db.session.commit()

    flash("Booking cancelled. Your cancellation history has been preserved.", "success")
    return redirect(url_for("student_bookings"))



# ---------------- ADMIN BOOKING WINDOW MANAGEMENT ----------------

@app.route("/admin/booking-settings", methods=["GET", "POST"])
@login_required
def admin_booking_settings():
    if not admin_required():
        return "Access denied", 403

    if request.method == "POST":
        enabled = request.form.get("booking_enabled") == "yes"
        opens_at = request.form.get("booking_opens_at", "").strip()
        closes_at = request.form.get("booking_closes_at", "").strip()
        cancellation_hours = request.form.get("cancellation_hours", "24").strip()

        try:
            hours = int(cancellation_hours)
            if hours < 0 or hours > 720:
                raise ValueError
            if opens_at:
                datetime.strptime(opens_at, "%Y-%m-%dT%H:%M")
            if closes_at:
                datetime.strptime(closes_at, "%Y-%m-%dT%H:%M")
            if opens_at and closes_at and datetime.strptime(closes_at, "%Y-%m-%dT%H:%M") <= datetime.strptime(opens_at, "%Y-%m-%dT%H:%M"):
                flash("Closing time must be later than opening time.", "danger")
                return redirect(url_for("admin_booking_settings"))
        except ValueError:
            flash("Enter valid dates/times and cancellation hours (0–720).", "danger")
            return redirect(url_for("admin_booking_settings"))

        set_emp_setting("booking_enabled", "yes" if enabled else "no")
        set_emp_setting("booking_opens_at", opens_at)
        set_emp_setting("booking_closes_at", closes_at)
        set_emp_setting("cancellation_hours", hours)
        db.session.commit()
        flash("Booking settings saved successfully.", "success")
        return redirect(url_for("admin_booking_settings"))

    return render_template(
        "admin/booking_settings.html",
        booking_enabled=get_emp_setting("booking_enabled", "yes") == "yes",
        booking_opens_at=get_emp_setting("booking_opens_at", ""),
        booking_closes_at=get_emp_setting("booking_closes_at", ""),
        cancellation_hours=get_emp_setting("cancellation_hours", "24")
    )


# ---------------- ADMIN SCHEDULE AND BOOKING MANAGEMENT ----------------


@app.route("/admin/schedule")
@login_required
def admin_schedule():
    if not admin_required():
        return "Access denied", 403

    slots = ExamSlot.query.join(Examination).order_by(
        Examination.exam_date, ExamSlot.slot_date, ExamSlot.start_time
    ).all()
    examinations = Examination.query.order_by(Examination.exam_date).all()
    active_examiners = User.query.filter_by(
        role="examiner", active=True
    ).order_by(User.name).all()

    return render_template(
        "admin/schedule.html",
        slots=slots,
        examinations=examinations,
        active_examiners=active_examiners
    )


@app.route("/admin/bookings/reschedule/<int:booking_id>", methods=["POST"])
@login_required
def admin_reschedule_booking(booking_id):
    if not admin_required():
        return "Access denied", 403

    booking = db.session.get(Booking, booking_id)
    if not booking:
        return "Booking not found", 404
    if booking.status != "active":
        flash("Only active bookings can be rescheduled.", "warning")
        return redirect(url_for("admin_schedule"))

    try:
        new_slot_id = int(request.form.get("new_slot_id", ""))
    except (ValueError, TypeError):
        flash("Please select a valid destination slot.", "danger")
        return redirect(url_for("admin_schedule"))

    new_slot = db.session.get(ExamSlot, new_slot_id)
    if not new_slot:
        flash("Destination slot not found.", "danger")
        return redirect(url_for("admin_schedule"))
    if new_slot.examination_id != booking.examination_id:
        flash("A booking can only be moved to another slot for the same examination.", "danger")
        return redirect(url_for("admin_schedule"))
    if new_slot.id == booking.slot_id:
        flash("This student is already booked in that slot.", "warning")
        return redirect(url_for("admin_schedule"))

    occupied = Booking.query.filter_by(
        slot_id=new_slot.id, status="active"
    ).count()
    if occupied >= new_slot.capacity:
        flash("The selected slot is full. Choose another slot.", "danger")
        return redirect(url_for("admin_schedule"))

    booking.slot_id = new_slot.id
    db.session.commit()
    flash("Booking rescheduled successfully.", "success")
    return redirect(url_for("admin_schedule"))


@app.route("/admin/slots/change-examiner/<int:slot_id>", methods=["POST"])
@login_required
def admin_change_slot_examiner(slot_id):
    if not admin_required():
        return "Access denied", 403

    slot = db.session.get(ExamSlot, slot_id)
    if not slot:
        return "Slot not found", 404

    try:
        examiner_id = int(request.form.get("examiner_id", ""))
    except (ValueError, TypeError):
        flash("Please select a valid examiner.", "danger")
        return redirect(url_for("admin_schedule"))

    examiner = db.session.get(User, examiner_id)
    assignment = ExamAssignment.query.filter_by(
        examination_id=slot.examination_id,
        examiner_id=examiner_id
    ).first()

    if not examiner or examiner.role != "examiner" or not examiner.active:
        flash("Select an active examiner.", "danger")
    elif not assignment:
        flash("That examiner is not assigned to this examination. Assign them first.", "danger")
    else:
        slot.examiner_id = examiner.id
        db.session.commit()
        flash("Slot examiner changed successfully.", "success")

    return redirect(url_for("admin_schedule"))



# ---------------- ADMIN SEARCH AND FILTERING ----------------

@app.route("/admin/search")
@login_required
def admin_search():
    if not admin_required():
        return "Access denied", 403

    term = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    status = request.args.get("status", "").strip()
    slot_date = request.args.get("slot_date", "").strip()
    examiner_id = request.args.get("examiner_id", "").strip()

    users_query = User.query
    if term:
        users_query = users_query.filter(
            db.or_(User.name.ilike(f"%{term}%"), User.email.ilike(f"%{term}%"))
        )
    if role in ("student", "examiner", "admin"):
        users_query = users_query.filter_by(role=role)
    users = users_query.order_by(User.name).limit(100).all()

    exams_query = Examination.query.join(Course)
    if term:
        exams_query = exams_query.filter(
            db.or_(
                Examination.exam_name.ilike(f"%{term}%"),
                Course.course_name.ilike(f"%{term}%"),
                Course.course_code.ilike(f"%{term}%")
            )
        )
    examinations = exams_query.order_by(Examination.exam_date).limit(100).all()

    slots_query = ExamSlot.query.join(Examination).join(User, ExamSlot.examiner_id == User.id)
    if term:
        slots_query = slots_query.filter(
            db.or_(Examination.exam_name.ilike(f"%{term}%"),
                   User.name.ilike(f"%{term}%"))
        )
    if slot_date:
        slots_query = slots_query.filter(ExamSlot.slot_date == slot_date)
    if examiner_id:
        try:
            slots_query = slots_query.filter(ExamSlot.examiner_id == int(examiner_id))
        except ValueError:
            pass
    slots = slots_query.order_by(ExamSlot.slot_date, ExamSlot.start_time).limit(100).all()

    bookings_query = Booking.query.join(User, Booking.student_id == User.id).join(
        Examination, Booking.examination_id == Examination.id
    )
    if term:
        bookings_query = bookings_query.filter(
            db.or_(User.name.ilike(f"%{term}%"),
                   User.email.ilike(f"%{term}%"),
                   Examination.exam_name.ilike(f"%{term}%"))
        )
    if status in ("active", "cancelled"):
        bookings_query = bookings_query.filter(Booking.status == status)
    bookings = bookings_query.order_by(Booking.booked_at.desc()).limit(100).all()

    examiners = User.query.filter_by(role="examiner", active=True).order_by(User.name).all()

    return render_template(
        "admin/search.html", term=term, role=role, status=status,
        slot_date=slot_date, examiner_id=examiner_id,
        users=users, examinations=examinations, slots=slots,
        bookings=bookings, examiners=examiners
    )

# LOGOUT
@app.route("/logout")
@login_required
def logout():

    logout_user()
    flash("You have logged out successfully.", "success")

    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)