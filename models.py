
from datetime import datetime

from sqlalchemy import Index, text
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    active = db.Column(db.Boolean, default=True)


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(20), unique=True, nullable=False)
    course_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)


class Examination(db.Model):
    __tablename__ = "examinations"

    id = db.Column(db.Integer, primary_key=True)
    exam_name = db.Column(db.String(150), nullable=False)
    course_id = db.Column(
        db.Integer, db.ForeignKey("courses.id"), nullable=False
    )
    exam_date = db.Column(db.String(20), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    max_marks = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)

    course = db.relationship("Course", backref="examinations")


class ExaminerProfile(db.Model):
    __tablename__ = "examiner_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"),
        unique=True, nullable=False
    )
    department = db.Column(db.String(100), nullable=False)
    qualification = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(15), nullable=False)

    user = db.relationship("User", backref="examiner_profile")


class ExamAssignment(db.Model):
    __tablename__ = "exam_assignments"

    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(
        db.Integer, db.ForeignKey("examinations.id"), nullable=False
    )
    examiner_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint(
            "examination_id",
            "examiner_id",
            name="unique_examiner_assignment"
        ),
    )

    examination = db.relationship("Examination", backref="assignments")
    examiner = db.relationship("User", backref="exam_assignments")


class ExamSlot(db.Model):
    __tablename__ = "exam_slots"

    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(
        db.Integer, db.ForeignKey("examinations.id"), nullable=False
    )
    examiner_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    slot_date = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)

    examination = db.relationship("Examination", backref="slots")
    examiner = db.relationship("User", backref="exam_slots")


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(
        db.Integer, db.ForeignKey("exam_slots.id"), nullable=False
    )
    examination_id = db.Column(
        db.Integer, db.ForeignKey("examinations.id"), nullable=False
    )
    student_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    status = db.Column(db.String(20), nullable=False, default="active")
    booked_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    slot = db.relationship("ExamSlot", backref="bookings")
    examination = db.relationship("Examination", backref="bookings")
    student = db.relationship("User", backref="bookings")

    __table_args__ = (
        Index(
            "uq_active_booking_per_student_exam",
            "student_id",
            "examination_id",
            unique=True,
            sqlite_where=text("status = 'active'")
        ),
        Index("ix_bookings_slot_status", "slot_id", "status"),
    )


class Rubric(db.Model):
    __tablename__ = "rubrics"

    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(
        db.Integer, db.ForeignKey("examinations.id"), nullable=False
    )
    criterion = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    max_marks = db.Column(db.Integer, nullable=False)

    examination = db.relationship("Examination", backref="rubrics")

    __table_args__ = (
        db.UniqueConstraint(
            "examination_id",
            "criterion",
            name="unique_rubric_criterion"
        ),
    )


class Evaluation(db.Model):
    __tablename__ = "evaluations"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(
        db.Integer, db.ForeignKey("bookings.id"),
        unique=True, nullable=False
    )
    examiner_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    total_marks = db.Column(db.Integer, nullable=False, default=0)
    remarks = db.Column(db.Text)
    evaluated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.now
    )

    booking = db.relationship(
        "Booking",
        backref=db.backref("evaluation", uselist=False)
    )
    examiner = db.relationship("User", backref="evaluations")


class EvaluationScore(db.Model):
    __tablename__ = "evaluation_scores"

    id = db.Column(db.Integer, primary_key=True)
    evaluation_id = db.Column(
        db.Integer, db.ForeignKey("evaluations.id"), nullable=False
    )
    rubric_id = db.Column(
        db.Integer, db.ForeignKey("rubrics.id"), nullable=False
    )
    marks_awarded = db.Column(db.Integer, nullable=False)

    evaluation = db.relationship("Evaluation", backref="scores")
    rubric = db.relationship("Rubric")

    __table_args__ = (
        db.UniqueConstraint(
            "evaluation_id",
            "rubric_id",
            name="unique_evaluation_rubric"
        ),
    )
