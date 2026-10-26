import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from todayclass import create_app  # noqa: E402
from todayclass.models import User, db  # noqa: E402
from todayclass.seed import initialize_database  # noqa: E402
from todayclass.validation import ADMIN_ROLE, STUDENT_ROLE  # noqa: E402

PASSWORD = 'senha-segura'


def testing_config():
    return {
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SECRET_KEY': 'test-secret',
        'SESSION_COOKIE_SECURE': False,
        'TESTING': True,
    }


@pytest.fixture
def app():
    app = create_app(testing_config())
    with app.app_context():
        initialize_database()
        yield app
        db.session.remove()
        db.drop_all()


class ApiClient:
    def __init__(self, client):
        self.client = client
        self.csrf_token = None

    def refresh_session(self):
        payload = self.client.get('/api/session').get_json()
        self.csrf_token = payload['csrf_token']
        return payload

    def get(self, path):
        return self.client.get(path)

    def send(self, method, path, payload=None):
        if self.csrf_token is None:
            self.refresh_session()
        return self.client.open(
            path,
            method=method,
            json=payload if payload is not None else {},
            headers={'X-CSRF-Token': self.csrf_token},
        )

    def post(self, path, payload=None):
        return self.send('POST', path, payload)

    def put(self, path, payload=None):
        return self.send('PUT', path, payload)

    def login(self, username, password=PASSWORD):
        return self.post('/api/login', {'username': username, 'password': password})


def create_user(username, role):
    user = User(username=username, role=role)
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def api(app):
    return ApiClient(app.test_client())


@pytest.fixture
def admin_api(app):
    create_user('admin', ADMIN_ROLE)
    client = ApiClient(app.test_client())
    client.login('admin')
    return client


@pytest.fixture
def student_api(app):
    create_user('aluno', STUDENT_ROLE)
    client = ApiClient(app.test_client())
    client.login('aluno')
    return client
