from conftest import create_user
from werkzeug.security import generate_password_hash

from todayclass import create_app
from todayclass.models import User, db
from todayclass.validation import ADMIN_ROLE


def test_serverless_sqlite_initializes_schema_on_startup(tmp_path):
    database_path = tmp_path / 'todayclass.db'
    app = create_app({
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{database_path}',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SECRET_KEY': 'test-secret',
        'INITIALIZE_DATABASE_ON_STARTUP': True,
        'TESTING': True,
    })

    response = app.test_client().get('/api/session')

    assert response.status_code == 200
    assert response.get_json()['needs_setup'] is False

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_serverless_sqlite_provisions_configured_admin(tmp_path, monkeypatch):
    database_path = tmp_path / 'todayclass.db'
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('SERVERLESS_ADMIN_USERNAME', 'owner@example.com')
    monkeypatch.setenv('SERVERLESS_ADMIN_PASSWORD_HASH', generate_password_hash('test-password'))
    app = create_app({
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{database_path}',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SECRET_KEY': 'test-secret',
        'INITIALIZE_DATABASE_ON_STARTUP': True,
        'TESTING': True,
    })

    with app.app_context():
        owner = User.query.filter_by(username='owner@example.com').one()

        assert owner.role == ADMIN_ROLE
        assert owner.check_password('test-password')
        db.session.remove()
        db.drop_all()


def test_session_never_offers_public_setup(api):
    payload = api.refresh_session()

    assert payload['user'] is None
    assert payload['needs_setup'] is False
    assert payload['csrf_token']


def test_public_setup_route_is_not_available(api):
    response = api.post('/api/setup', {'username': 'admin', 'password': 'senha-segura'})

    assert response.status_code == 404


def test_login_with_wrong_password_is_rejected(api):
    create_user('admin', ADMIN_ROLE)

    response = api.login('admin', 'senha-errada')

    assert response.status_code == 401
    assert response.get_json()['error'] == 'Usuário ou senha inválidos.'


def test_login_and_logout_change_the_session_user(api):
    create_user('admin', ADMIN_ROLE)

    assert api.login('admin').get_json()['user']['username'] == 'admin'
    assert api.post('/api/logout').get_json()['user'] is None
    assert api.get('/api/courses').status_code == 401


def test_unsafe_request_without_csrf_token_is_rejected(api):
    create_user('admin', ADMIN_ROLE)

    response = api.client.post('/api/login', json={'username': 'admin', 'password': 'senha-segura'})

    assert response.status_code == 400
    assert response.get_json()['error'] == 'Sessão expirada. Recarregue a página.'


def test_unsafe_request_with_wrong_csrf_token_is_rejected(api):
    api.refresh_session()
    api.csrf_token = 'token-falso'

    response = api.post('/api/login', {'username': 'admin', 'password': 'senha-segura'})

    assert response.status_code == 400
