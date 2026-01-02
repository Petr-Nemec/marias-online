# 🚀 Produkční nasazení Mariáš Serveru

Tento guide popisuje, jak nasadit Mariáš server pro produkční použití.

## ⚠️ Před nasazením

Aktuální implementace je optimalizována pro **lokální síť a testování**. Pro produkční nasazení na internet doporučujeme:

1. **Použít HTTPS** - Zabezpečené spojení
2. **Přidat autentizaci** - Uživatelské účty
3. **Použít databázi** - Pro perzistenci dat
4. **Rate limiting** - Ochrana před útoky
5. **Load balancer** - Pro více současných her

## 🏠 Lokální síť (doporučeno)

### Pro domácí použití
```bash
# Spusť server normálně
python server.py

# Server poběží na IP adrese tvého počítače
# Všichni na stejné WiFi se mohou připojit
```

**Výhody:**
- ✅ Jednoduché nastavení
- ✅ Bezpečné (pouze lokální síť)
- ✅ Nízká latence
- ✅ Žádné náklady

**Nevýhody:**
- ❌ Pouze stejná síť
- ❌ Vyžaduje běžící počítač

## 🌐 Veřejný internet

### Možnost 1: Raspberry Pi / Home Server

**Hardware:**
- Raspberry Pi 3/4 (doporučeno 4GB RAM)
- Stabilní internetové připojení
- Statická IP nebo Dynamic DNS

**Instalace:**
```bash
# Na Raspberry Pi
sudo apt update
sudo apt install python3 python3-pip

# Naklonuj projekt
git clone [your-repo]
cd mariase-server

# Instaluj závislosti
pip3 install -r requirements.txt

# Spusť jako službu
sudo nano /etc/systemd/system/marias.service
```

**Systemd service:**
```ini
[Unit]
Description=Mariáš Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/mariase-server
ExecStart=/usr/bin/python3 /home/pi/mariase-server/server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Aktivuj službu
sudo systemctl enable marias
sudo systemctl start marias
```

### Možnost 2: VPS (Virtual Private Server)

**Poskytovatelé:**
- DigitalOcean (od $5/měsíc)
- Vultr (od $5/měsíc)
- AWS EC2 (Free tier 1 rok)
- Hetzner (od €4/měsíc)

**Instalace na Ubuntu 22.04:**
```bash
# Aktualizuj systém
sudo apt update && sudo apt upgrade -y

# Instaluj Python a závislosti
sudo apt install python3 python3-pip nginx -y

# Vytvoř uživatele
sudo useradd -m -s /bin/bash marias
sudo su - marias

# Naklonuj projekt
git clone [your-repo] ~/mariase-server
cd ~/mariase-server

# Vytvoř virtual environment
python3 -m venv venv
source venv/bin/activate

# Instaluj závislosti
pip install -r requirements.txt
pip install gunicorn  # Pro produkci
```

**Gunicorn konfigurace:**
```bash
# gunicorn_config.py
bind = "127.0.0.1:5000"
workers = 4
worker_class = "eventlet"
timeout = 120
```

**Nginx konfigurace:**
```nginx
# /etc/nginx/sites-available/marias
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /socket.io {
        proxy_pass http://127.0.0.1:5000/socket.io;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
}
```

```bash
# Aktivuj konfiguraci
sudo ln -s /etc/nginx/sites-available/marias /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**SSL s Let's Encrypt:**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Možnost 3: Docker

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "server.py"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  marias:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
```

**Spuštění:**
```bash
docker-compose up -d
```

### Možnost 4: Cloud Platform

#### Heroku
```bash
# Procfile
web: gunicorn --worker-class eventlet -w 1 server:app

# runtime.txt
python-3.11.0

# Deploy
heroku create marias-game
git push heroku main
```

#### Railway.app
1. Připoj GitHub repozitář
2. Automatické nasazení
3. Získej URL

## 🔒 Bezpečnost pro produkci

### 1. Změň secret key
```python
# config.py
import secrets
SECRET_KEY = secrets.token_hex(32)
```

### 2. HTTPS
```python
# server.py
socketio = SocketIO(app, 
    cors_allowed_origins="https://your-domain.com",
    ssl_context='adhoc'  # Nebo cesta k certifikátům
)
```

### 3. Rate Limiting
```python
# pip install Flask-Limiter
from flask_limiter import Limiter

limiter = Limiter(
    app,
    key_func=lambda: request.remote_addr,
    default_limits=["200 per day", "50 per hour"]
)
```

### 4. CORS
```python
socketio = SocketIO(app, 
    cors_allowed_origins=[
        "https://your-domain.com",
        "https://www.your-domain.com"
    ]
)
```

## 📊 Monitoring

### Logování
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('marias.log'),
        logging.StreamHandler()
    ]
)
```

### Metriky
```bash
# Instaluj Prometheus exporter
pip install prometheus-flask-exporter
```

## 🔄 Zálohování

### Databáze (pokud přidáš)
```bash
# Denní záloha
0 2 * * * pg_dump marias_db > /backups/marias_$(date +\%Y\%m\%d).sql
```

### Aplikace
```bash
# Git backup
git push origin main
git push backup main  # Druhý remote
```

## 📈 Škálování

### Více workerů
```python
# gunicorn s více workery
gunicorn -w 4 -k eventlet server:app
```

### Redis session store
```python
# Pro sdílené sessions
from flask_session import Session
app.config['SESSION_TYPE'] = 'redis'
```

### Load Balancer
```nginx
upstream marias_backend {
    server 127.0.0.1:5000;
    server 127.0.0.1:5001;
    server 127.0.0.1:5002;
}
```

## 🧪 Testování před nasazením

```bash
# Spusť testy
python test_game.py

# Load testing
pip install locust
locust -f loadtest.py
```

## 📝 Checklist před nasazením

- [ ] DEBUG=False v config.py
- [ ] Změněný SECRET_KEY
- [ ] HTTPS nakonfigurováno
- [ ] Firewall pravidla nastavena
- [ ] Logování aktivní
- [ ] Zálohy nastaveny
- [ ] Monitoring aktivní
- [ ] Rate limiting zapnutý
- [ ] CORS správně nastaven
- [ ] Testy prošly
- [ ] Dokumentace aktuální

## 🆘 Troubleshooting

### Server nereaguje
```bash
# Zkontroluj logy
tail -f marias.log
journalctl -u marias -f

# Zkontroluj porty
netstat -tulpn | grep 5000

# Restartuj službu
sudo systemctl restart marias
```

### WebSocket problémy
```bash
# Zkontroluj Nginx logs
tail -f /var/log/nginx/error.log

# Test WebSocket
wscat -c ws://your-domain.com/socket.io
```

## 💰 Náklady

### Měsíční náklady pro 50-100 současných her:

- **Lokální síť:** 0 Kč (spotřeba elektřiny)
- **VPS Basic:** 150-300 Kč/měsíc
- **VPS Pro:** 500-1000 Kč/měsíc
- **Cloud (AWS/GCP):** 500-2000 Kč/měsíc

## 🎯 Doporučení

Pro začátek:
1. **Testuj lokálně** s přáteli
2. **Raspberry Pi** pro malou skupinu
3. **VPS** pro větší škálu
4. **Cloud** pro profesionální nasazení

---

**Potřebuješ pomoc?** Vytvoř issue v GitHub repozitáři.