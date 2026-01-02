#!/bin/bash
# run.sh - Spouštěcí skript pro Linux/Mac
# Použití: ./run.sh
# (Nejprve udělej: chmod +x run.sh)

echo "======================================"
echo "🃏 Mariáš Server - Spouštění"
echo "======================================"
echo ""

# Kontrola Pythonu
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 není nainstalován!"
    exit 1
fi

echo "✓ Python verze: $(python3 --version)"

# Kontrola závislostí
if ! python3 -c "import flask" 2>/dev/null; then
    echo ""
    echo "⚠️  Chybí závislosti. Instaluji..."
    pip3 install -r requirements.txt
fi

# Zjisti IP adresu
echo ""
echo "📡 Detekuji IP adresu..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    IP=$(hostname -I | awk '{print $1}')
else
    IP="localhost"
fi

echo "✓ Server IP: $IP"

# Spusť server
echo ""
echo "🚀 Spouštím server..."
echo "======================================"
echo "Lokální přístup: http://localhost:5000"
echo "Síťový přístup:  http://$IP:5000"
echo "======================================"
echo ""
echo "Stiskni Ctrl+C pro zastavení serveru"
echo ""

python3 server.py