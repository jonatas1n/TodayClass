from .admin import admin_blueprint
from .courses import courses_blueprint
from .lessons import lessons_blueprint
from .session import session_blueprint

BLUEPRINTS = (session_blueprint, courses_blueprint, lessons_blueprint, admin_blueprint)
