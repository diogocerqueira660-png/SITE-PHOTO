#!/bin/bash
# Lance Gestion Photos Auto sur Mac (double-clic).
cd "$(dirname "$0")"
python3 -c "import PIL" 2>/dev/null || python3 -m pip install --user -r requirements.txt
python3 app.py
