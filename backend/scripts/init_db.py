import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from todayclass import create_app  # noqa: E402
from todayclass.seed import initialize_database  # noqa: E402


def main():
    app = create_app()
    with app.app_context():
        initialize_database()
    print(f"Banco pronto em {app.config['SQLALCHEMY_DATABASE_URI'].split('?')[0]}")


if __name__ == '__main__':
    main()
