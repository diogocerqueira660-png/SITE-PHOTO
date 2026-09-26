@echo off
rem Crée GestionPhotosAuto.exe (dans le dossier dist) : plus besoin de Python ensuite.
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py
%PY% -m pip install --user pyinstaller -r requirements.txt
%PY% -m pip install --user rawpy
%PY% -m PyInstaller --noconfirm --onefile --windowed --name GestionPhotosAuto --icon ressources/logo.ico --add-data "ressources:ressources" --collect-all customtkinter --collect-all send2trash app.py
echo.
echo Termine : dist\GestionPhotosAuto.exe
pause
