@echo off
rem Lance Gestion Photos Auto (double-clic). Installe Pillow au premier lancement.
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py
%PY% -c "import PIL, customtkinter" 2>nul || %PY% -m pip install --user -r requirements.txt
if "%PY%"=="py" (start "" pyw app.py) else (start "" pythonw app.py)
