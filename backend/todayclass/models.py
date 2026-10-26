from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

from .validation import (
    MAXIMUM_COURSE_NAME_LENGTH,
    MAXIMUM_LESSON_TITLE_LENGTH,
    MAXIMUM_LINK_TITLE_LENGTH,
    MAXIMUM_LINK_URL_LENGTH,
    MAXIMUM_USERNAME_LENGTH,
)

db = SQLAlchemy()


def naive_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(MAXIMUM_COURSE_NAME_LENGTH), nullable=False)
    lessons = db.relationship(
        'Lesson',
        backref='course',
        lazy=True,
        cascade='all, delete-orphan',
        order_by=lambda: (Lesson.day, Lesson.id),
    )


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    day = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(MAXIMUM_LESSON_TITLE_LENGTH), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    links = db.relationship(
        'Link',
        backref='lesson',
        lazy=True,
        cascade='all, delete-orphan',
        order_by=lambda: Link.id,
    )

    @property
    def label(self):
        return f'Dia {self.day} - {self.title}'


class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(MAXIMUM_LINK_TITLE_LENGTH), nullable=False)
    url = db.Column(db.String(MAXIMUM_LINK_URL_LENGTH), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(MAXIMUM_USERNAME_LENGTH), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
