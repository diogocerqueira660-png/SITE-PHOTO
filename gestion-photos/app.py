"""Gestion Photos Auto : lance l'appli.

    python app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from interface import lancer  # noqa: E402

if __name__ == "__main__":
    lancer()
