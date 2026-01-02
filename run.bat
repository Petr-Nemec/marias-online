@echo off
chcp 65001 >nul
echo ======================================
echo 🃏 Mariáš Server - Spouštění
echo ======================================
echo.

REM Kontrola Pythonu
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python není nainstalován!
    echo.
    echo Stáhni Python z: https://www.python.org/downloads/
    echo Při instalaci zaškrtni "Add Python to PATH"
    pause
    exit /b 1
)

echo ✓ Python nalezen
python --version

REM Kontrola závislostí
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ⚠️  Chybí závislosti. Instaluji...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ Instalace selhala!
        pause
        exit /b 1
    )
    echo ✓ Závislosti nainstalovány
)

REM Zjisti IP adresu
echo.
echo 📡 Detekuji IP adresu...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set IP=%%a
    goto :found
)
:found
set IP=%IP: =%

if "%IP%"=="" (
    set IP=localhost
)

echo ✓ Server IP: %IP%

REM Kontrola portu
netstat -ano | findstr :5000 >nul
if not errorlevel 1 (
    echo.
    echo ⚠️  Port 5000 je již používán!
    echo Změň port v souboru config.py nebo server.py
    pause
    exit /b 1
)

REM Spusť server
echo.
echo 🚀 Spouštím server...
echo ======================================
echo Lokální přístup: http://localhost:5000
echo Síťový přístup:  http://%IP%:5000
echo ======================================
echo.
echo 💡 TIP: Na jiných zařízeních otevři http://%IP%:5000
echo.
echo Stiskni Ctrl+C pro zastavení serveru
echo ======================================
echo.

python server.py

pause