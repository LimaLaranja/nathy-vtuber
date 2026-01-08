@echo off
echo Iniciando o servidor VTuber...
cd /d "C:\VTuber\backend"
call .\venv\Scripts\activate.bat
python main.py
pause
