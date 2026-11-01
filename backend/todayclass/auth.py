from functools import wraps
import secrets

from flask import abort, request, session
from flask_login import LoginManager, current_user

from .models import User, db
from .validation import ADMIN_ROLE, STUDENT_ROLE

CSRF_HEADER = 'X-CSRF-Token'
UNSAFE_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')

login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    if not str(user_id).isdigit():
        return None
    return db.session.get(User, int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    abort(401)


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
    if request.method not in UNSAFE_METHODS:
        return
    if not request.is_json:
        abort(400, description='Envie os dados como JSON.')
    if csrf_tokens_match(session.get('csrf_token'), request.headers.get(CSRF_HEADER)):
        return
    abort(400, description='Sessão expirada. Recarregue a página.')


def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role != role:
                abort(403)
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


admin_required = role_required(ADMIN_ROLE)
student_required = role_required(STUDENT_ROLE)
