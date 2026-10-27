from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from functools import wraps
import os
import secrets
from urllib.parse import urlparse

from flask import Flask, abort, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload
from werkzeug.security import check_password_hash, generate_password_hash

def development_secret_key():
    if __name__ == '__main__':
        return 'dev-only-change-me'
    raise RuntimeError('SECRET_KEY is required')


app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'courses.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or development_secret_key()
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = None

STUDENT_ROLE = 'student'
ADMIN_ROLE = 'admin'
ROLES = (STUDENT_ROLE, ADMIN_ROLE)
MINIMUM_PASSWORD_LENGTH = 8
MAXIMUM_USERNAME_LENGTH = 80
MAXIMUM_COURSE_NAME_LENGTH = 120
MAXIMUM_LESSON_TITLE_LENGTH = 120
MAXIMUM_DAY_NUMBER = 9999
MAXIMUM_LINK_TITLE_LENGTH = 100
MAXIMUM_LINK_URL_LENGTH = 255
MAXIMUM_QUESTION_PROMPT_LENGTH = 500
MAXIMUM_QUESTION_ANSWER_LENGTH = 4000
LINK_ROW_COUNT = 4
GENERIC_COURSE_NAME = 'Curso geral'
LEGACY_COURSE_TABLE = 'legacy_course'
LEGACY_LINK_TABLE = 'legacy_link'
SAO_PAULO = ZoneInfo('America/Sao_Paulo')


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(MAXIMUM_COURSE_NAME_LENGTH), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    lessons = db.relationship(
        'Lesson',
        backref='course',
        lazy=True,
        cascade='all, delete-orphan',
        order_by=lambda: (Lesson.day, Lesson.id),
    )
    questions = db.relationship(
        'Question',
        backref='course',
        lazy=True,
        cascade='all, delete-orphan',
        order_by=lambda: (Question.position, Question.id),
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
    )

    @property
    def label(self):
        return f'Dia {self.day} - {self.title}'


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    prompt = db.Column(db.String(MAXIMUM_QUESTION_PROMPT_LENGTH), nullable=False)
    answer = db.Column(db.Text, nullable=True)


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


def naive_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_utc(moment):
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def sao_paulo_date(moment):
    return as_utc(moment).astimezone(SAO_PAULO).date()


def lessons_are_finished(course):
    return all(lesson.is_completed for lesson in course.lessons)


def questions_are_answered(course):
    return all((question.answer or '').strip() for question in course.questions)


def course_requirements_met(course):
    if not course.lessons and not course.questions:
        return False
    if not lessons_are_finished(course):
        return False
    return questions_are_answered(course)


def apply_completion_state(course, moment):
    if course_requirements_met(course):
        if course.completed_at is not None:
            return False
        course.completed_at = moment
        return True
    if course.completed_at is None:
        return False
    course.completed_at = None
    return True


def ordered_courses():
    return (
        Course.query.options(selectinload(Course.lessons), selectinload(Course.questions))
        .order_by(Course.id)
        .all()
    )


def sync_course_completions(courses, moment):
    changed = False
    for course in courses:
        if apply_completion_state(course, moment):
            changed = True
    if changed:
        db.session.commit()


def course_availability(previous_course, today):
    if previous_course is None:
        return True, None
    if previous_course.completed_at is None:
        return False, 'Disponível depois de concluir o curso anterior'
    unlock_on = sao_paulo_date(previous_course.completed_at) + timedelta(days=1)
    if today >= unlock_on:
        return True, None
    return False, f'Disponível em {unlock_on.strftime("%d/%m/%Y")}'


def course_rows_for_viewer(moment=None):
    moment = moment or naive_utc_now()
    courses = ordered_courses()
    sync_course_completions(courses, moment)
    today = sao_paulo_date(moment)
    rows = []
    previous_course = None
    for course in courses:
        available, lock_label = course_availability(previous_course, today)
        if current_user.role == ADMIN_ROLE:
            available = True
            lock_label = None
        rows.append((course, len(course.lessons), available, lock_label))
        previous_course = course
    return rows


def course_is_open(course, moment=None):
    if current_user.role == ADMIN_ROLE:
        return True
    moment = moment or naive_utc_now()
    courses = ordered_courses()
    sync_course_completions(courses, moment)
    today = sao_paulo_date(moment)
    previous_course = None
    for candidate in courses:
        if candidate.id == course.id:
            available, _lock_label = course_availability(previous_course, today)
            return available
        previous_course = candidate
    return False


def course_status_note(course):
    if course.completed_at is not None:
        finished_on = sao_paulo_date(course.completed_at).strftime('%d/%m/%Y')
        return f'Curso concluído em {finished_on}.'
    if not course.questions or questions_are_answered(course):
        return None
    return 'Responda as perguntas para concluir o curso.'


def username_validation_error(username):
    if not username:
        return 'O usuário é obrigatório.'
    if len(username) > MAXIMUM_USERNAME_LENGTH:
        return 'O usuário é longo demais.'
    return None


def password_validation_error(password):
    if not password:
        return 'A senha é obrigatória.'
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        return f'A senha deve ter pelo menos {MINIMUM_PASSWORD_LENGTH} caracteres.'
    return None


def account_validation_error(username, password, role):
    username_error = username_validation_error(username)
    if username_error:
        return username_error
    password_error = password_validation_error(password)
    if password_error:
        return password_error
    if role not in ROLES:
        return 'Escolha um papel válido.'
    return None


def build_user(username, password, role):
    error = account_validation_error(username, password, role)
    if error:
        return error
    if User.query.filter_by(username=username).first() is not None:
        return 'Esse usuário já está em uso.'

    user = User(username=username, role=role)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        app.logger.exception('Could not create user: %s', error)
        return 'Esse usuário já está em uso.'
    return None


def existing_table_names(connection):
    rows = connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {row[0] for row in rows}


def table_column_names(connection, table_name):
    rows = connection.exec_driver_sql(f'PRAGMA table_info("{table_name}")')
    return {row[1] for row in rows}


def has_legacy_shape(connection, table_names, table_name, marker_column):
    if table_name not in table_names:
        return False
    return marker_column in table_column_names(connection, table_name)


def begin_explicit_transaction(connection):
    # pysqlite only opens a transaction before DML, so DDL would autocommit without this.
    connection.exec_driver_sql('BEGIN')


def rename_legacy_table(connection, table_names, table_name, legacy_name):
    if legacy_name in table_names:
        raise RuntimeError(f'Both {table_name} and {legacy_name} use the legacy schema.')
    connection.exec_driver_sql(f'ALTER TABLE "{table_name}" RENAME TO "{legacy_name}"')


def rename_legacy_tables():
    with db.engine.begin() as connection:
        begin_explicit_transaction(connection)
        table_names = existing_table_names(connection)
        if has_legacy_shape(connection, table_names, 'course', 'day'):
            rename_legacy_table(connection, table_names, 'course', LEGACY_COURSE_TABLE)
        if has_legacy_shape(connection, table_names, 'link', 'course_id'):
            rename_legacy_table(connection, table_names, 'link', LEGACY_LINK_TABLE)


def generic_course_id(connection):
    existing_id = connection.execute(
        text('SELECT id FROM course WHERE name = :name ORDER BY id LIMIT 1'),
        {'name': GENERIC_COURSE_NAME},
    ).scalar()
    if existing_id is not None:
        return existing_id
    result = connection.execute(
        text('INSERT INTO course (name) VALUES (:name)'),
        {'name': GENERIC_COURSE_NAME},
    )
    return result.lastrowid


def copy_legacy_lessons(connection, course_id):
    connection.execute(
        text(
            'INSERT INTO lesson (id, course_id, day, title, content, is_completed, completed_at) '
            "SELECT id, :course_id, day, 'Aula ' || day, content, COALESCE(is_completed, 0), completed_at "
            f'FROM {LEGACY_COURSE_TABLE} '
            'WHERE id NOT IN (SELECT id FROM lesson)'
        ),
        {'course_id': course_id},
    )


def copy_legacy_links(connection):
    connection.exec_driver_sql(
        'INSERT INTO link (id, title, url, lesson_id) '
        f'SELECT id, title, url, course_id FROM {LEGACY_LINK_TABLE} '
        'WHERE id NOT IN (SELECT id FROM link) '
        'AND course_id IN (SELECT id FROM lesson)'
    )


def copy_legacy_rows():
    with db.engine.begin() as connection:
        begin_explicit_transaction(connection)
        table_names = existing_table_names(connection)
        if LEGACY_COURSE_TABLE not in table_names:
            return
        copy_legacy_lessons(connection, generic_course_id(connection))
        if LEGACY_LINK_TABLE in table_names:
            copy_legacy_links(connection)
            connection.exec_driver_sql(f'DROP TABLE {LEGACY_LINK_TABLE}')
        connection.exec_driver_sql(f'DROP TABLE {LEGACY_COURSE_TABLE}')


def seed_sample_course():
    if Course.query.first() is not None:
        return

    course = Course(name=GENERIC_COURSE_NAME)
    lesson = Lesson(
        course=course,
        day=1,
        title='Aula 1',
        content=(
            '<h1>Welcome to Day 1!</h1>'
            '<p>This is a <strong>long form</strong> text imitating a rich text editor output.</p>'
        ),
    )
    db.session.add(course)
    db.session.add(Link(title='Read more here', url='https://example.com', lesson=lesson))
    db.session.commit()


def ensure_course_completed_at():
    with db.engine.begin() as connection:
        begin_explicit_transaction(connection)
        table_names = existing_table_names(connection)
        if 'course' not in table_names:
            return
        if 'completed_at' in table_column_names(connection, 'course'):
            return
        connection.exec_driver_sql('ALTER TABLE course ADD COLUMN completed_at DATETIME')


def prepare_database():
    try:
        rename_legacy_tables()
        db.create_all()
        copy_legacy_rows()
        ensure_course_completed_at()
    except Exception:
        app.logger.exception('Database migration failed')
        raise
    seed_sample_course()


with app.app_context():
    prepare_database()


@login_manager.user_loader
def load_user(user_id):
    if not str(user_id).isdigit():
        return None
    return db.session.get(User, int(user_id))


def ensure_csrf_token():
    token = session.get('csrf_token')
    if token:
        return token
    token = secrets.token_urlsafe(32)
    session['csrf_token'] = token
    return token


def csrf_tokens_match(stored_token, submitted_token):
    if not stored_token or not submitted_token:
        return False
    if len(stored_token) != len(submitted_token):
        return False
    return secrets.compare_digest(stored_token, submitted_token)


def validate_csrf():
    stored_token = session.get('csrf_token')
    submitted_token = request.form.get('csrf_token')
    if csrf_tokens_match(stored_token, submitted_token):
        return
    abort(400)


@app.context_processor
def inject_csrf_token():
    return {'csrf_token': ensure_csrf_token()}


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if current_user.role != ADMIN_ROLE:
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view


def safe_next_url(target):
    if not target or not target.startswith('/'):
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return None
    return target


def destination_for(user):
    if user.role == ADMIN_ROLE:
        return url_for('admin_dashboard')
    return url_for('course_list')


def lesson_url(lesson):
    return url_for('view_lesson', course_id=lesson.course_id, lesson_id=lesson.id)


def parse_day_number(raw_value):
    stripped_value = raw_value.strip()
    if not stripped_value.isdecimal():
        return None
    day_number = int(stripped_value)
    if day_number < 1 or day_number > MAXIMUM_DAY_NUMBER:
        return None
    return day_number


def required_text_error(field_label, value, maximum_length):
    if not value:
        return f'{field_label} é obrigatório.'
    if len(value) > maximum_length:
        return f'{field_label} é longo demais.'
    return None


def completed_link_pairs(link_rows):
    pairs = []
    for title, url in link_rows:
        stripped_title = title.strip()
        stripped_url = url.strip()
        if not stripped_title and not stripped_url:
            continue
        pairs.append((stripped_title, stripped_url))
    return pairs


def link_rows_error(pairs):
    for title, url in pairs:
        if not title or not url:
            return 'Cada link precisa de um título e uma URL.'
        if len(title) > MAXIMUM_LINK_TITLE_LENGTH:
            return 'O título do link é longo demais.'
        if len(url) > MAXIMUM_LINK_URL_LENGTH:
            return 'A URL do link é longa demais.'
        if not url.startswith(('http://', 'https://')):
            return 'A URL do link deve começar com http:// ou https://.'
    return None


def lesson_form_error(day_number, title, content, pairs):
    if day_number is None:
        return f'O dia deve ser um número inteiro de 1 a {MAXIMUM_DAY_NUMBER}.'
    title_error = required_text_error('O título', title, MAXIMUM_LESSON_TITLE_LENGTH)
    if title_error:
        return title_error
    if not content.strip():
        return 'O conteúdo é obrigatório.'
    return link_rows_error(pairs)


def posted_link_rows():
    titles = request.form.getlist('link_title')
    urls = request.form.getlist('link_url')
    rows = [(title, url) for title, url in zip(titles, urls)]
    while len(rows) < LINK_ROW_COUNT:
        rows.append(('', ''))
    return rows[:LINK_ROW_COUNT]


def blank_link_rows():
    return [('', '') for _ in range(LINK_ROW_COUNT)]


def stored_link_rows(lesson):
    rows = [(link.title, link.url) for link in lesson.links]
    while len(rows) < LINK_ROW_COUNT:
        rows.append(('', ''))
    return rows[:LINK_ROW_COUNT]


def lesson_fields_from_request():
    return (
        request.form.get('day', ''),
        request.form.get('title', '').strip(),
        request.form.get('content', ''),
        posted_link_rows(),
    )


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


def paired_form_values(first_name, second_name):
    first_values = request.form.getlist(first_name)
    second_values = request.form.getlist(second_name)
    if len(first_values) != len(second_values):
        return None
    return list(zip(first_values, second_values))


def removed_question_ids():
    removed_ids = set()
    for raw_id in request.form.getlist('remove'):
        if str(raw_id).isdigit():
            removed_ids.add(int(raw_id))
    return removed_ids


def question_for_course(questions_by_id, raw_id):
    if not str(raw_id).isdigit():
        return None
    return questions_by_id.get(int(raw_id))


def values_by_question_id(posted_rows):
    values = {}
    for raw_id, raw_value in posted_rows:
        if str(raw_id).isdigit():
            values[int(raw_id)] = raw_value
    return values


def validated_question_updates(questions_by_id, posted_rows, removed_ids):
    updates = []
    for raw_id, raw_prompt in posted_rows:
        question = question_for_course(questions_by_id, raw_id)
        if question is None:
            return None, 'Pergunta não encontrada.'
        if question.id in removed_ids:
            continue
        prompt = raw_prompt.strip()
        error = required_text_error('O texto da pergunta', prompt, MAXIMUM_QUESTION_PROMPT_LENGTH)
        if error:
            return None, error
        updates.append((question, prompt))
    return updates, None


def validated_new_prompt(raw_prompt):
    prompt = raw_prompt.strip()
    if not prompt:
        return '', None
    error = required_text_error('O texto da pergunta', prompt, MAXIMUM_QUESTION_PROMPT_LENGTH)
    if error:
        return None, error
    return prompt, None


def unknown_removed_question(questions_by_id, removed_ids):
    for question_id in removed_ids:
        if question_id not in questions_by_id:
            return True
    return False


def apply_question_changes(course, posted_rows, new_prompt_raw, removed_ids):
    questions_by_id = {question.id: question for question in course.questions}
    if unknown_removed_question(questions_by_id, removed_ids):
        return 'Pergunta não encontrada.'

    updates, error = validated_question_updates(questions_by_id, posted_rows, removed_ids)
    if error:
        return error
    new_prompt, error = validated_new_prompt(new_prompt_raw)
    if error:
        return error

    next_position = max((question.position for question in course.questions), default=0) + 1
    for question_id in removed_ids:
        db.session.delete(questions_by_id[question_id])
    for question, prompt in updates:
        question.prompt = prompt
    if new_prompt:
        db.session.add(Question(course=course, position=next_position, prompt=new_prompt))
    apply_completion_state(course, naive_utc_now())
    db.session.commit()
    return None


def answer_text_error(answer):
    if len(answer) > MAXIMUM_QUESTION_ANSWER_LENGTH:
        return 'A resposta é longa demais.'
    return None


def validated_answer_updates(questions_by_id, posted_rows):
    updates = []
    for raw_id, raw_answer in posted_rows:
        question = question_for_course(questions_by_id, raw_id)
        if question is None:
            return None, 'Pergunta não encontrada.'
        answer = raw_answer.strip()
        error = answer_text_error(answer)
        if error:
            return None, error
        updates.append((question, answer or None))
    return updates, None


def save_answers(course, posted_rows):
    questions_by_id = {question.id: question for question in course.questions}
    updates, error = validated_answer_updates(questions_by_id, posted_rows)
    if error:
        return error
    for question, answer in updates:
        question.answer = answer
    apply_completion_state(course, naive_utc_now())
    db.session.commit()
    return None


def create_lesson(course, raw_day, title, content, link_rows):
    day_number = parse_day_number(raw_day)
    pairs = completed_link_pairs(link_rows)
    error = lesson_form_error(day_number, title, content, pairs)
    if error:
        return None, error

    lesson = Lesson(course=course, day=day_number, title=title, content=content)
    db.session.add(lesson)
    for link_title, url in pairs:
        db.session.add(Link(title=link_title, url=url, lesson=lesson))
    db.session.commit()
    return lesson, None


def replace_lesson_links(lesson, pairs):
    lesson.links.clear()
    for link_title, url in pairs:
        lesson.links.append(Link(title=link_title, url=url))


def update_lesson(lesson, raw_day, title, content, link_rows):
    day_number = parse_day_number(raw_day)
    pairs = completed_link_pairs(link_rows)
    error = lesson_form_error(day_number, title, content, pairs)
    if error:
        return error

    lesson.day = day_number
    lesson.title = title
    lesson.content = content
    replace_lesson_links(lesson, pairs)
    db.session.commit()
    return None


def resolve_post_login_url(user):
    next_url = safe_next_url(request.args.get('next'))
    if next_url:
        return next_url
    return destination_for(user)


def authenticate(username, password):
    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return None
    return user


def find_user_from_form():
    raw_user_id = request.form.get('user_id', '')
    if not raw_user_id.isdigit():
        return None
    return db.session.get(User, int(raw_user_id))


def reset_password_from_form():
    password = request.form.get('password', '')
    password_error = password_validation_error(password)
    if password_error:
        return password_error

    user = find_user_from_form()
    if user is None:
        return 'Usuário não encontrado.'

    user.set_password(password)
    db.session.commit()
    return None


def apply_admin_action():
    action = request.form.get('action')
    if action == 'create_user':
        return build_user(
            request.form.get('username', '').strip(),
            request.form.get('password', ''),
            request.form.get('role', ''),
        )
    if action == 'reset_password':
        return reset_password_from_form()
    abort(400)


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


@app.route('/')
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    return redirect(destination_for(current_user))


@app.route('/courses')
@login_required
def course_list():
    return render_template('courses.html', course_rows=course_rows_for_viewer())


@app.route('/courses/new', methods=['GET', 'POST'])
@admin_required
def new_course():
    error = None
    name = ''
    if request.method == 'POST':
        validate_csrf()
        name = request.form.get('name', '').strip()
        course, error = create_course(name)
        if error is None:
            return redirect(url_for('view_course', course_id=course.id))

    return render_template(
        'new_course.html',
        error=error,
        name=name,
        page_title='Novo curso',
        submit_label='Criar curso',
        submit_icon='plus',
        cancel_url=url_for('course_list'),
        back_label='Todos os cursos',
    )


def render_course_page(course, question_error=None, answer_error=None, new_prompt='', removed_ids=None, posted_prompts=None, posted_answers=None):
    return render_template(
        'course.html',
        course=course,
        question_error=question_error,
        answer_error=answer_error,
        new_prompt=new_prompt,
        removed_ids=removed_ids or set(),
        posted_prompts=posted_prompts or {},
        posted_answers=posted_answers or {},
        status_note=course_status_note(course),
    )


def locked_course_redirect(course):
    if course_is_open(course):
        return None
    return redirect(url_for('course_list'))


@app.route('/courses/<int:course_id>')
@login_required
def view_course(course_id):
    course = db.get_or_404(Course, course_id)
    locked = locked_course_redirect(course)
    if locked is not None:
        return locked
    return render_course_page(course)


@app.route('/courses/<int:course_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_course(course_id):
    course = db.get_or_404(Course, course_id)
    error = None
    name = course.name
    if request.method == 'POST':
        validate_csrf()
        name = request.form.get('name', '').strip()
        error = update_course(course, name)
        if error is None:
            return redirect(url_for('view_course', course_id=course.id))

    return render_template(
        'new_course.html',
        error=error,
        name=name,
        page_title='Editar curso',
        submit_label='Salvar',
        submit_icon='check',
        cancel_url=url_for('view_course', course_id=course.id),
        back_label=course.name,
    )


@app.route('/courses/<int:course_id>/questions', methods=['POST'])
@admin_required
def save_course_questions(course_id):
    course = db.get_or_404(Course, course_id)
    validate_csrf()
    posted_rows = paired_form_values('question_id', 'prompt')
    new_prompt = request.form.get('new_prompt', '')
    removed_ids = removed_question_ids()
    if posted_rows is None:
        return render_course_page(
            course,
            question_error='Pergunta não encontrada.',
            new_prompt=new_prompt,
            removed_ids=removed_ids,
        )

    error = apply_question_changes(course, posted_rows, new_prompt, removed_ids)
    if error:
        return render_course_page(
            course,
            question_error=error,
            new_prompt=new_prompt,
            removed_ids=removed_ids,
            posted_prompts=values_by_question_id(posted_rows),
        )
    return redirect(url_for('view_course', course_id=course.id))


@app.route('/courses/<int:course_id>/answers', methods=['POST'])
@login_required
def save_course_answers(course_id):
    course = db.get_or_404(Course, course_id)
    validate_csrf()
    if current_user.role != STUDENT_ROLE:
        abort(403)
    locked = locked_course_redirect(course)
    if locked is not None:
        return locked

    posted_rows = paired_form_values('question_id', 'answer')
    if posted_rows is None:
        return render_course_page(course, answer_error='Pergunta não encontrada.')

    error = save_answers(course, posted_rows)
    if error:
        return render_course_page(
            course,
            answer_error=error,
            posted_answers=values_by_question_id(posted_rows),
        )
    return redirect(url_for('view_course', course_id=course.id))


@app.route('/courses/<int:course_id>/lessons/new', methods=['GET', 'POST'])
@admin_required
def new_lesson(course_id):
    course = db.get_or_404(Course, course_id)
    error = None
    day_value = ''
    title = ''
    content = ''
    link_rows = blank_link_rows()
    if request.method == 'POST':
        validate_csrf()
        day_value, title, content, link_rows = lesson_fields_from_request()
        lesson, error = create_lesson(course, day_value, title, content, link_rows)
        if error is None:
            return redirect(lesson_url(lesson))

    return render_template(
        'lesson_form.html',
        course=course,
        error=error,
        day_value=day_value,
        title=title,
        content=content,
        link_rows=link_rows,
        page_title='Nova aula',
        submit_label='Criar aula',
        submit_icon='plus',
        cancel_url=url_for('view_course', course_id=course.id),
    )


@app.route('/courses/<int:course_id>/lessons/<int:lesson_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_lesson(course_id, lesson_id):
    lesson = find_lesson_or_404(course_id, lesson_id)
    error = None
    day_value = str(lesson.day)
    title = lesson.title
    content = lesson.content
    link_rows = stored_link_rows(lesson)
    if request.method == 'POST':
        validate_csrf()
        day_value, title, content, link_rows = lesson_fields_from_request()
        error = update_lesson(lesson, day_value, title, content, link_rows)
        if error is None:
            return redirect(lesson_url(lesson))

    return render_template(
        'lesson_form.html',
        course=lesson.course,
        error=error,
        day_value=day_value,
        title=title,
        content=content,
        link_rows=link_rows,
        page_title='Editar aula',
        submit_label='Salvar',
        submit_icon='check',
        cancel_url=lesson_url(lesson),
    )


@app.route('/courses/<int:course_id>/lessons/<int:lesson_id>', methods=['GET', 'POST'])
@login_required
def view_lesson(course_id, lesson_id):
    lesson = find_lesson_or_404(course_id, lesson_id)
    locked = locked_course_redirect(lesson.course)
    if locked is not None:
        return locked
    if request.method == 'GET':
        return render_template('lesson.html', lesson=lesson)

    validate_csrf()
    if current_user.role != STUDENT_ROLE:
        abort(403)
    if lesson.is_completed:
        return redirect(url_for('success'))

    moment = naive_utc_now()
    lesson.is_completed = True
    lesson.completed_at = moment
    apply_completion_state(lesson.course, moment)
    db.session.commit()
    return redirect(url_for('success'))


@app.route('/day/<int:day_id>')
@login_required
def legacy_day_redirect(day_id):
    lessons = Lesson.query.filter_by(day=day_id).limit(2).all()
    if len(lessons) != 1:
        abort(404)
    return redirect(lesson_url(lessons[0]))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(resolve_post_login_url(current_user))

    error = None
    if request.method == 'POST':
        validate_csrf()
        user = authenticate(
            request.form.get('username', '').strip(),
            request.form.get('password', ''),
        )
        if user is None:
            error = 'Usuário ou senha inválidos.'
        else:
            login_user(user)
            return redirect(resolve_post_login_url(user))

    needs_setup = User.query.first() is None
    return render_template('login.html', error=error, needs_setup=needs_setup)


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    validate_csrf()
    logout_user()
    return redirect(url_for('login'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if User.query.first() is not None:
        abort(404)

    error = None
    if request.method == 'POST':
        validate_csrf()
        error = build_user(
            request.form.get('username', '').strip(),
            request.form.get('password', ''),
            ADMIN_ROLE,
        )
        if error is None:
            return redirect(url_for('login'))

    return render_template('setup.html', error=error)


@app.route('/success')
@login_required
def success():
    return render_template('success.html')


@app.route('/secret-admin-dashboard', methods=['GET', 'POST'])
@admin_required
def admin_dashboard():
    error = None
    if request.method == 'POST':
        validate_csrf()
        error = apply_admin_action()
        if error is None:
            return redirect(url_for('admin_dashboard'))

    lessons = (
        Lesson.query.join(Course)
        .options(joinedload(Lesson.course), selectinload(Lesson.links))
        .order_by(Course.name, Course.id, Lesson.day, Lesson.id)
        .all()
    )
    users = User.query.order_by(User.username).all()
    return render_template('admin.html', lessons=lessons, users=users, error=error)


if __name__ == '__main__':
    app.config['SESSION_COOKIE_SECURE'] = False
    app.run(debug=True)
