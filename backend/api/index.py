import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from todayclass import create_app  # noqa: E402

app = create_app()
