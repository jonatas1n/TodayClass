from datetime import datetime, timezone
from functools import wraps
import os
import secrets
from urllib.parse import urlparse

from flask import Flask, abort, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
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


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Integer, unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    links = db.relationship(
        'Link',
        backref='course',
        lazy=True,
        cascade='all, delete-orphan',
    )


class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)


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


def username_validation_error(username):
    if not username:
        return 'Username is required.'
    if len(username) > MAXIMUM_USERNAME_LENGTH:
        return 'Username is too long.'
    return None


def password_validation_error(password):
    if not password:
        return 'Password is required.'
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        return f'Password must be at least {MINIMUM_PASSWORD_LENGTH} characters.'
    return None


def account_validation_error(username, password, role):
    username_error = username_validation_error(username)
    if username_error:
        return username_error
    password_error = password_validation_error(password)
    if password_error:
        return password_error
    if role not in ROLES:
        return 'Choose a valid role.'
    return None


def build_user(username, password, role):
    error = account_validation_error(username, password, role)
    if error:
        return error
    if User.query.filter_by(username=username).first() is not None:
        return 'That username is already taken.'

    user = User(username=username, role=role)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        app.logger.exception('Could not create user: %s', error)
        return 'That username is already taken.'
    return None


def seed_sample_course():
    if Course.query.first() is not None:
        return

    course = Course(
        day=1,
        content=(
            '<h1>Welcome to Day 1!</h1>'
            '<p>This is a <strong>long form</strong> text imitating a rich text editor output.</p>'
        ),
    )
    db.session.add(course)
    db.session.flush()
    db.session.add(Link(title='Read more here', url='https://example.com', course=course))
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_sample_course()


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


def next_course_for_student():
    incomplete_course = (
        Course.query.filter_by(is_completed=False).order_by(Course.day).first()
    )
    if incomplete_course is not None:
        return incomplete_course
    return Course.query.order_by(Course.day.desc()).first()


def destination_for(user):
    if user.role == ADMIN_ROLE:
        return url_for('admin_dashboard')
    course = next_course_for_student()
    if course is None:
        return url_for('success')
    return url_for('view_course', day_id=course.day)


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
        return 'User not found.'

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
            error = 'Invalid username or password.'
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


@app.route('/day/<int:day_id>', methods=['GET', 'POST'])
@login_required
def view_course(day_id):
    course = Course.query.filter_by(day=day_id).first_or_404()
    if request.method == 'GET':
        return render_template('course.html', course=course)

    validate_csrf()
    if current_user.role != STUDENT_ROLE:
        abort(403)
    if course.is_completed:
        return redirect(url_for('success'))

    course.is_completed = True
    course.completed_at = naive_utc_now()
    db.session.commit()
    return redirect(url_for('success'))


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

    courses = Course.query.order_by(Course.day).all()
    users = User.query.order_by(User.username).all()
    return render_template('admin.html', courses=courses, users=users, error=error)


if __name__ == '__main__':
    app.config['SESSION_COOKIE_SECURE'] = False
    app.run(debug=True)
