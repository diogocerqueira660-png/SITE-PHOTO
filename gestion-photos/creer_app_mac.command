#!/bin/bash
# Crée « Gestion Photos Auto.app » (dans le dossier dist) sur un Mac.
cd "$(dirname "$0")"
python3 -m pip install --user pyinstaller rawpy -r requirements.txt
python3 -m PyInstaller --noconfirm --windowed --name "Gestion Photos Auto" \
  --icon ressources/logo.icns --add-data "ressources:ressources" \
  --osx-bundle-identifier com.diogocarphotography.gestionphotos \
  --collect-all rawpy --collect-all customtkinter app.py
echo "Terminé : dist/Gestion Photos Auto.app"
