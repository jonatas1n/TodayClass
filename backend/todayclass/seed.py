from .models import Course, Lesson, Link, db

SAMPLE_COURSE_NAME = 'Curso geral'


def seed_sample_course():
    if Course.query.first() is not None:
        return

    course = Course(name=SAMPLE_COURSE_NAME)
    lesson = Lesson(
        course=course,
        day=1,
        title='Aula 1',
        content=(
            '<h1>Welcome to Day 1!</h1>'
            '<p>This is a <strong>long form</strong> text imitating a rich text editor output.</p>'
        ),
    )
    lesson.links.append(Link(title='Read more here', url='https://example.com'))
    db.session.add(course)
    db.session.commit()


def initialize_database():
    db.create_all()
    seed_sample_course()
