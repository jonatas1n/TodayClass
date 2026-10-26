import os

BACKEND_DIRECTORY = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOCAL_DATABASE_PATH = os.path.join(BACKEND_DIRECTORY, 'courses.db')


def turso_host():
    turso_url = os.environ.get('TURSO_DATABASE_URL', '')
    return turso_url.removeprefix('libsql://').removeprefix('https://').rstrip('/')


def database_uri():
    host = turso_host()
    if not host:
        return 'sqlite:///' + LOCAL_DATABASE_PATH
    return f'sqlite+libsql://{host}/?secure=true'


def engine_options():
    options = {'pool_pre_ping': True}
    if not turso_host():
        return options
    options['connect_args'] = {'auth_token': os.environ['TURSO_AUTH_TOKEN']}
    return options


def secret_key():
    key = os.environ.get('SECRET_KEY')
    if not key:
        raise RuntimeError('SECRET_KEY is required')
    return key


def default_config():
    return {
        'SQLALCHEMY_DATABASE_URI': database_uri(),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SQLALCHEMY_ENGINE_OPTIONS': engine_options(),
        'SECRET_KEY': secret_key(),
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_SAMESITE': 'Lax',
        'SESSION_COOKIE_SECURE': True,
    }
