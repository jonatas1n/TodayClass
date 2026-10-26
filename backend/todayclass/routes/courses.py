from flask import Blueprint, jsonify
from flask_login import login_required

from ..auth import admin_required
from ..models import Course, db
from ..payloads import form_text, json_body
from ..serializers import course_payload, course_summary_payload
from ..services import courses_with_lesson_counts, create_course

courses_blueprint = Blueprint('courses', __name__, url_prefix='/api/courses')


@courses_blueprint.get('')
@login_required
def list_courses():
    courses = [
        course_summary_payload(course, lesson_count)
        for course, lesson_count in courses_with_lesson_counts()
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
    return jsonify({'course': course_payload(course)})
