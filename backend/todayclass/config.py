import os

BACKEND_DIRECTORY = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOCAL_DATABASE_PATH = os.path.join(BACKEND_DIRECTORY, 'courses.db')
SERVERLESS_DATABASE_PATH = '/tmp/todayclass.db'


def turso_host():
    turso_url = os.environ.get('TURSO_DATABASE_URL', '')
    return turso_url.removeprefix('libsql://').removeprefix('https://').rstrip('/')


def uses_serverless_sqlite():
    return not turso_host() and os.environ.get('VERCEL') == '1'


def serverless_admin_credentials():
    if not uses_serverless_sqlite():
        return None
    username = os.environ.get('SERVERLESS_ADMIN_USERNAME')
    password_hash = os.environ.get('SERVERLESS_ADMIN_PASSWORD_HASH')
    if not username or not password_hash:
        return None
    return username, password_hash


def database_uri():
    host = turso_host()
    if host:
        return f'sqlite+libsql://{host}/?secure=true'
    if uses_serverless_sqlite():
        return 'sqlite:///' + SERVERLESS_DATABASE_PATH
    return 'sqlite:///' + LOCAL_DATABASE_PATH


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
        'INITIALIZE_DATABASE_ON_STARTUP': uses_serverless_sqlite(),
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_SAMESITE': 'Lax',
        'SESSION_COOKIE_SECURE': True,
    }
