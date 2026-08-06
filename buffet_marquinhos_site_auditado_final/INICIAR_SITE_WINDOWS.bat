@echo off
setlocal
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate
python -m pip install -r requirements.txt
set ADMIN_PASSWORD=troque-esta-senha
set SECRET_KEY=teste-local-buffet-marquinhos
set FLASK_DEBUG=1
python app.py
pause
