from flask import Blueprint, jsonify
from flask_login import login_required

from ..auth import admin_required, student_required
from ..models import Course, db
from ..payloads import json_body
from ..serializers import lesson_payload
from ..services import complete_lesson, create_lesson, find_lesson_or_404, update_lesson

lessons_blueprint = Blueprint(
    'lessons',
    __name__,
    url_prefix='/api/courses/<int:course_id>/lessons',
)


@lessons_blueprint.post('')
@admin_required
def add_lesson(course_id):
    course = db.get_or_404(Course, course_id)
    lesson, error = create_lesson(course, json_body())
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'lesson': lesson_payload(lesson)}), 201


@lessons_blueprint.get('/<int:lesson_id>')
@login_required
def read_lesson(course_id, lesson_id):
    lesson = find_lesson_or_404(course_id, lesson_id)
    return jsonify({'lesson': lesson_payload(lesson)})


@lessons_blueprint.put('/<int:lesson_id>')
@admin_required
def edit_lesson(course_id, lesson_id):
    lesson = find_lesson_or_404(course_id, lesson_id)
    error = update_lesson(lesson, json_body())
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'lesson': lesson_payload(lesson)})


@lessons_blueprint.post('/<int:lesson_id>/complete')
@student_required
def mark_lesson_complete(course_id, lesson_id):
    lesson = find_lesson_or_404(course_id, lesson_id)
    complete_lesson(lesson)
    return jsonify({'lesson': lesson_payload(lesson)})
