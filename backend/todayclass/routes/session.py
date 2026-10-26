from flask import Blueprint, abort, jsonify
from flask_login import current_user, login_required, login_user, logout_user

from ..auth import ensure_csrf_token
from ..payloads import form_password, form_text, json_body
from ..serializers import user_payload
from ..services import authenticate, build_user, needs_setup
from ..validation import ADMIN_ROLE

session_blueprint = Blueprint('session', __name__, url_prefix='/api')


def session_payload():
    user = user_payload(current_user) if current_user.is_authenticated else None
    return {
        'user': user,
        'needs_setup': needs_setup(),
        'csrf_token': ensure_csrf_token(),
    }


@session_blueprint.get('/session')
def read_session():
    return jsonify(session_payload())


@session_blueprint.post('/setup')
def setup():
    if not needs_setup():
        abort(404)

    payload = json_body()
    user, error = build_user(form_text(payload, 'username'), form_password(payload), ADMIN_ROLE)
    if error:
        return jsonify({'error': error}), 400

    login_user(user)
    return jsonify(session_payload()), 201


@session_blueprint.post('/login')
def login():
    payload = json_body()
    user = authenticate(form_text(payload, 'username'), form_password(payload))
    if user is None:
        return jsonify({'error': 'Usuário ou senha inválidos.'}), 401

    login_user(user)
    return jsonify(session_payload())


@session_blueprint.post('/logout')
@login_required
def logout():
    logout_user()
    return jsonify(session_payload())
