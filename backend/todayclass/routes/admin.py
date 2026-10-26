from flask import Blueprint, jsonify

from ..auth import admin_required
from ..models import User, db
from ..payloads import form_password, form_text, json_body
from ..serializers import progress_row_payload, user_payload
from ..services import build_user, progress_lessons, reset_password, users_by_name

admin_blueprint = Blueprint('admin', __name__, url_prefix='/api/admin')


@admin_blueprint.get('/progress')
@admin_required
def read_progress():
    return jsonify({'lessons': [progress_row_payload(lesson) for lesson in progress_lessons()]})


@admin_blueprint.get('/users')
@admin_required
def list_users():
    return jsonify({'users': [user_payload(user) for user in users_by_name()]})


@admin_blueprint.post('/users')
@admin_required
def add_user():
    payload = json_body()
    user, error = build_user(
        form_text(payload, 'username'),
        form_password(payload),
        form_text(payload, 'role'),
    )
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'user': user_payload(user)}), 201


@admin_blueprint.put('/users/<int:user_id>/password')
@admin_required
def change_user_password(user_id):
    user = db.get_or_404(User, user_id)
    error = reset_password(user, form_password(json_body()))
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'user': user_payload(user)})
