@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Environnement Python absent. Suivez l'installation dans README.md.
    echo python -m venv .venv
    echo .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo Dependances manquantes : executez la commande suivante dans ce dossier.
    echo .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -c "from urllib.request import urlopen; assert urlopen('http://127.0.0.1:8501/_stcore/health', timeout=2).read() == b'ok'" >nul 2>&1
if not errorlevel 1 (
    start "" "http://127.0.0.1:8501"
    exit /b 0
)
echo AgriPheno : http://127.0.0.1:8501
echo Gardez cette fenetre ouverte pendant l'utilisation. Ctrl+C pour arreter.
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless false
if errorlevel 1 pause
