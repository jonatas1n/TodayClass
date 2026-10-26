from conftest import create_user

from todayclass.validation import ADMIN_ROLE


def test_session_reports_setup_needed_without_users(api):
    payload = api.refresh_session()

    assert payload['user'] is None
    assert payload['needs_setup'] is True
    assert payload['csrf_token']


def test_setup_creates_admin_and_signs_in(api):
    response = api.post('/api/setup', {'username': 'admin', 'password': 'senha-segura'})

    assert response.status_code == 201
    assert response.get_json()['user']['role'] == ADMIN_ROLE
    assert api.refresh_session()['needs_setup'] is False


def test_setup_is_closed_after_first_user(api):
    create_user('admin', ADMIN_ROLE)

    response = api.post('/api/setup', {'username': 'outro', 'password': 'senha-segura'})

    assert response.status_code == 404


def test_setup_rejects_short_password(api):
    response = api.post('/api/setup', {'username': 'admin', 'password': 'curta'})

    assert response.status_code == 400
    assert response.get_json()['error'] == 'A senha deve ter pelo menos 8 caracteres.'


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
