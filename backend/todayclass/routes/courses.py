from flask import Blueprint, abort, jsonify
from flask_login import current_user, login_required

from ..auth import admin_required, student_required
from ..models import Course, db
from ..payloads import form_text, json_body
from ..serializers import course_payload, course_summary_payload
from ..services import catalog_for, create_course, record_answers, replace_questions, unavailable_reason, update_course
from ..validation import ADMIN_ROLE

courses_blueprint = Blueprint('courses', __name__, url_prefix='/api/courses')


def refuse_locked_course(course):
    if current_user.role == ADMIN_ROLE:
        return
    reason = unavailable_reason(course)
    if reason is None:
        return
    abort(403, description=reason)


@courses_blueprint.get('')
@login_required
def list_courses():
    courses = [
        course_summary_payload(course, lesson_count, is_available, reason)
        for course, lesson_count, is_available, reason in catalog_for(current_user.role == ADMIN_ROLE)
    ]
    return jsonify({'courses': courses})


@courses_blueprint.post('')
@admin_required
def add_course():
    course, error = create_course(form_text(json_body(), 'name'))
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'course': course_payload(course)}), 201


@courses_blueprint.get('/<int:course_id>')
@login_required
def read_course(course_id):
    course = db.get_or_404(Course, course_id)
    refuse_locked_course(course)
    return jsonify({'course': course_payload(course)})


@courses_blueprint.put('/<int:course_id>')
@admin_required
def edit_course(course_id):
    course = db.get_or_404(Course, course_id)
    error = update_course(course, form_text(json_body(), 'name'))
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'course': course_payload(course)})


@courses_blueprint.post('/<int:course_id>/questions')
@admin_required
def save_questions(course_id):
    course = db.get_or_404(Course, course_id)
    error = replace_questions(course, json_body())
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'course': course_payload(course)})


@courses_blueprint.post('/<int:course_id>/answers')
@student_required
def save_answers(course_id):
    course = db.get_or_404(Course, course_id)
    refuse_locked_course(course)
    error = record_answers(course, json_body())
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'course': course_payload(course)})
