from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from .auth import login_manager, validate_csrf
from .config import default_config
from .models import db
from .routes import BLUEPRINTS

ERROR_MESSAGES = {
    401: 'Entre para continuar.',
    403: 'Você não tem permissão para isso.',
    404: 'Não encontrado.',
    405: 'Método não permitido.',
}


def error_message(error):
    default_description = type(error).description
    if error.description and error.description != default_description:
        return error.description
    return ERROR_MESSAGES.get(error.code, 'Não foi possível concluir o pedido.')


def handle_http_error(error):
    return jsonify({'error': error_message(error)}), error.code


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.update(config_overrides or default_config())

    db.init_app(app)
    login_manager.init_app(app)
    app.before_request(validate_csrf)
    app.register_error_handler(HTTPException, handle_http_error)
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)
    return app
