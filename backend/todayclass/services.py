from flask import current_app
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from .models import Course, Lesson, Link, Question, User, db, naive_utc_now
from .schedule import apply_completion_state, course_availability, sao_paulo_date
from .validation import (
    MAXIMUM_COURSE_NAME_LENGTH,
    MAXIMUM_QUESTION_ANSWER_LENGTH,
    MAXIMUM_QUESTION_PROMPT_LENGTH,
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


def update_course(course, name):
    error = required_text_error('O nome', name, MAXIMUM_COURSE_NAME_LENGTH)
    if error:
        return error
    course.name = name
    db.session.commit()
    return None


def ordered_courses():
    return (
        Course.query.options(selectinload(Course.lessons), selectinload(Course.questions))
        .order_by(Course.id)
        .all()
    )


def sync_course_completions(courses, moment=None):
    moment = moment or naive_utc_now()
    changed = False
    for course in courses:
        if apply_completion_state(course, moment):
            changed = True
    if not changed:
        return
    db.session.commit()


def catalog_for(is_admin, moment=None):
    moment = moment or naive_utc_now()
    courses = ordered_courses()
    sync_course_completions(courses, moment)
    today = sao_paulo_date(moment)
    rows = []
    previous_course = None
    for course in courses:
        available, reason = course_availability(previous_course, today)
        if is_admin:
            available = True
            reason = None
        rows.append((course, len(course.lessons), available, reason))
        previous_course = course
    return rows


def unavailable_reason(course, moment=None):
    moment = moment or naive_utc_now()
    courses = ordered_courses()
    sync_course_completions(courses, moment)
    today = sao_paulo_date(moment)
    previous_course = None
    for candidate in courses:
        if candidate.id != course.id:
            previous_course = candidate
            continue
        available, reason = course_availability(previous_course, today)
        if available:
            return None
        return reason
    return None


def remember_completion(course):
    apply_completion_state(course, naive_utc_now())


def question_prompt_error(prompt):
    return required_text_error('O texto da pergunta', prompt, MAXIMUM_QUESTION_PROMPT_LENGTH)


def optional_new_prompt(raw_prompt):
    if not isinstance(raw_prompt, str):
        return None, 'O texto da pergunta é obrigatório.'
    prompt = raw_prompt.strip()
    if not prompt:
        return '', None
    error = question_prompt_error(prompt)
    if error:
        return None, error
    return prompt, None


def parsed_question_changes(course, raw_questions):
    if not isinstance(raw_questions, list):
        return None, None, 'Pergunta não encontrada.'
    questions_by_id = {question.id: question for question in course.questions}
    updates = []
    removed_ids = set()
    for item in raw_questions:
        parsed, error = one_question_change(questions_by_id, item)
        if error:
            return None, None, error
        question, prompt, removed = parsed
        if removed:
            removed_ids.add(question.id)
            continue
        updates.append((question, prompt))
    return updates, removed_ids, None


def one_question_change(questions_by_id, item):
    if not isinstance(item, dict) or not isinstance(item.get('id'), int):
        return None, 'Pergunta não encontrada.'
    question = questions_by_id.get(item['id'])
    if question is None:
        return None, 'Pergunta não encontrada.'
    if item.get('remove') is True:
        return (question, None, True), None
    prompt = item.get('prompt', '')
    if not isinstance(prompt, str):
        return None, 'O texto da pergunta é obrigatório.'
    error = question_prompt_error(prompt.strip())
    if error:
        return None, error
    return (question, prompt.strip(), False), None


def replace_questions(course, payload):
    updates, removed_ids, error = parsed_question_changes(course, payload.get('questions', []))
    if error:
        return error
    new_prompt, error = optional_new_prompt(payload.get('new_prompt', ''))
    if error:
        return error

    questions_by_id = {question.id: question for question in course.questions}
    next_position = max((question.position for question in course.questions), default=0) + 1
    for question_id in removed_ids:
        db.session.delete(questions_by_id[question_id])
    for question, prompt in updates:
        question.prompt = prompt
    if new_prompt:
        db.session.add(Question(course=course, position=next_position, prompt=new_prompt))
    remember_completion(course)
    db.session.commit()
    return None


def answer_text_error(answer):
    if len(answer) > MAXIMUM_QUESTION_ANSWER_LENGTH:
        return 'A resposta é longa demais.'
    return None


def parsed_answers(course, raw_answers):
    if not isinstance(raw_answers, list):
        return None, 'Pergunta não encontrada.'
    questions_by_id = {question.id: question for question in course.questions}
    updates = []
    for item in raw_answers:
        parsed, error = one_answer(questions_by_id, item)
        if error:
            return None, error
        updates.append(parsed)
    return updates, None


def one_answer(questions_by_id, item):
    if not isinstance(item, dict) or not isinstance(item.get('id'), int):
        return None, 'Pergunta não encontrada.'
    question = questions_by_id.get(item['id'])
    if question is None:
        return None, 'Pergunta não encontrada.'
    raw_answer = item.get('answer', '')
    if not isinstance(raw_answer, str):
        return None, 'A resposta é inválida.'
    answer = raw_answer.strip()
    error = answer_text_error(answer)
    if error:
        return None, error
    return (question, answer or None), None


def record_answers(course, payload):
    updates, error = parsed_answers(course, payload.get('answers'))
    if error:
        return error
    for question, answer in updates:
        question.answer = answer
    remember_completion(course)
    db.session.commit()
    return None


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
    remember_completion(course)
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
    moment = naive_utc_now()
    lesson.is_completed = True
    lesson.completed_at = moment
    apply_completion_state(lesson.course, moment)
    db.session.commit()


def courses_with_lesson_counts():
    return (
        db.session.query(Course, func.count(Lesson.id))
        .outerjoin(Lesson)
        .group_by(Course.id)
        .order_by(Course.id)
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
