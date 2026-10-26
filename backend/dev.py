import os

from flask import send_from_directory

from todayclass import create_app
from todayclass.config import default_config
from todayclass.seed import initialize_database

FRONTEND_DIRECTORY = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'public'))
DEV_PORT = 5001


def development_app():
    os.environ.setdefault('SECRET_KEY', 'dev-only-change-me')
    config = default_config()
    config['SESSION_COOKIE_SECURE'] = False
    app = create_app(config)

    @app.get('/')
    @app.get('/<path:asset_path>')
    def frontend_asset(asset_path='index.html'):
        return send_from_directory(FRONTEND_DIRECTORY, asset_path)

    with app.app_context():
        initialize_database()
    return app


if __name__ == '__main__':
    development_app().run(host='localhost', port=DEV_PORT, debug=True)
