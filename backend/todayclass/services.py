from flask import current_app
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from .models import Course, Lesson, Link, User, db, naive_utc_now
from .validation import (
    MAXIMUM_COURSE_NAME_LENGTH,
    account_validation_error,
    completed_link_pairs,
    lesson_form_error,
    parse_day_number,
    password_validation_error,
    required_text_error,
    text_value,
)


def needs_setup():
    return User.query.first() is None


def authenticate(username, password):
    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return None
    return user


def build_user(username, password, role):
    error = account_validation_error(username, password, role)
    if error:
        return None, error
    if User.query.filter_by(username=username).first() is not None:
        return None, 'Esse usuário já está em uso.'

    user = User(username=username, role=role)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        current_app.logger.exception('Could not create user: %s', error)
        return None, 'Esse usuário já está em uso.'
    return user, None


def reset_password(user, password):
    error = password_validation_error(password)
    if error:
        return error
    user.set_password(password)
    db.session.commit()
    return None


def create_course(name):
    error = required_text_error('O nome', name, MAXIMUM_COURSE_NAME_LENGTH)
    if error:
        return None, error

    course = Course(name=name)
    db.session.add(course)
    db.session.commit()
    return course, None


def lesson_fields(payload):
    day_number = parse_day_number(payload.get('day', ''))
    title = text_value(payload.get('title'))
    content = payload.get('content') if isinstance(payload.get('content'), str) else ''
    pairs = completed_link_pairs(payload.get('links'))
    error = lesson_form_error(day_number, title, content, pairs)
    return day_number, title, content, pairs, error


def create_lesson(course, payload):
    day_number, title, content, pairs, error = lesson_fields(payload)
    if error:
        return None, error

    lesson = Lesson(course=course, day=day_number, title=title, content=content)
    db.session.add(lesson)
    for link_title, url in pairs:
        lesson.links.append(Link(title=link_title, url=url))
    db.session.commit()
    return lesson, None


def update_lesson(lesson, payload):
    day_number, title, content, pairs, error = lesson_fields(payload)
    if error:
        return error

    lesson.day = day_number
    lesson.title = title
    lesson.content = content
    lesson.links.clear()
    for link_title, url in pairs:
        lesson.links.append(Link(title=link_title, url=url))
    db.session.commit()
    return None


def complete_lesson(lesson):
    if lesson.is_completed:
        return
    lesson.is_completed = True
    lesson.completed_at = naive_utc_now()
    db.session.commit()


def courses_with_lesson_counts():
    return (
        db.session.query(Course, func.count(Lesson.id))
        .outerjoin(Lesson)
        .group_by(Course.id)
        .order_by(Course.name, Course.id)
        .all()
    )


def find_lesson_or_404(course_id, lesson_id):
    return Lesson.query.filter_by(id=lesson_id, course_id=course_id).first_or_404()


def progress_lessons():
    return (
        Lesson.query.join(Course)
        .options(joinedload(Lesson.course), selectinload(Lesson.links))
        .order_by(Course.name, Course.id, Lesson.day, Lesson.id)
        .all()
    )


def users_by_name():
    return User.query.order_by(User.username).all()
