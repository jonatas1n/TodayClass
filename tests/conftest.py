import os
import sys
import tempfile
from datetime import timedelta

import pytest

DATABASE_DIRECTORY = tempfile.mkdtemp(prefix='diariamente-tests-')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(DATABASE_DIRECTORY, 'test.db')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as application_module  # noqa: E402

CSRF_TOKEN = 'test-csrf-token'


@pytest.fixture
def application():
    flask_app = application_module.app
    flask_app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
    with flask_app.app_context():
        application_module.db.drop_all()
        application_module.db.create_all()
    return flask_app


def create_user(flask_app, username, role):
    with flask_app.app_context():
        user = application_module.User(username=username, role=role)
        user.set_password('a-long-password')
        application_module.db.session.add(user)
        application_module.db.session.commit()
        return user.id


def signed_in_client(flask_app, user_id):
    client = flask_app.test_client()
    with client.session_transaction() as session_state:
        session_state['_user_id'] = str(user_id)
        session_state['_fresh'] = True
        session_state['csrf_token'] = CSRF_TOKEN
    return client


@pytest.fixture
def student_client(application):
    return signed_in_client(application, create_user(application, 'pai', application_module.STUDENT_ROLE))


@pytest.fixture
def admin_client(application):
    return signed_in_client(application, create_user(application, 'admin', application_module.ADMIN_ROLE))


def add_course(flask_app, name, lesson_count=1, completed_days_ago=None):
    with flask_app.app_context():
        course = application_module.Course(name=name)
        application_module.db.session.add(course)
        completed_moment = None
        if completed_days_ago is not None:
            completed_moment = application_module.naive_utc_now() - timedelta(days=completed_days_ago)
            course.completed_at = completed_moment
        for day in range(1, lesson_count + 1):
            application_module.db.session.add(
                application_module.Lesson(
                    course=course,
                    day=day,
                    title=f'Aula {day}',
                    content='<p>Conteúdo</p>',
                    is_completed=completed_moment is not None,
                    completed_at=completed_moment,
                )
            )
        application_module.db.session.commit()
        return course.id


def first_lesson_id(flask_app, course_id):
    with flask_app.app_context():
        return application_module.db.session.get(application_module.Course, course_id).lessons[0].id


def course_completed_at(flask_app, course_id):
    with flask_app.app_context():
        return application_module.db.session.get(application_module.Course, course_id).completed_at
