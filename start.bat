@echo off
cd /d C:\LogoGateway
call venv\Scripts\activate.bat
uvicorn app.main:app --host 127.0.0.1 --port 8000
