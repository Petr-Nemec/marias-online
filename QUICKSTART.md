# ⚡ RYCHLÝ START - Mariáš Server v2.0

> ✨ **NOVÁ VERZE** - Kompletně přepracováno podle profesionálních standardů  
> ✅ Správná pravidla mariáše podle CSM  
> ✅ Robustní kód s error handlingem  
> ✅ Production-ready kvalita

---

## 🚀 3 KROKY K HRANÍ

### 1️⃣ Nainstaluj závislosti
```bash
pip install -r requirements.txt
```

**Nebo manuálně:**
```bash
pip install flask flask-socketio python-socketio
```

**Kontrola:**
```bash
python --version  # Potřebuješ 3.8+
```

---

### 2️⃣ Spusť server
```bash
python server.py
```

**Výstup:**
```
============================================================
🃏 MARIÁŠ ONLINE SERVER
============================================================
✓ Server běží na portu 5000
✓ Lokální přístup:  http://localhost:5000
✓ Síťový přístup:   http://192.168.1.100:5000
============================================================
💡 TIP: Na jiných zařízeních použij síťovou adresu
📝 Logy se ukládají do: marias_server.log
============================================================
```

---

### 3️⃣ Připoj se a hraj!

**Na stejném počítači:**
```
http://localhost:5000
```

**Z jiného zařízení (telefon, tablet):**
1. Zjisti IP adresu serveru (je v outputu serveru)
2. Otevři: `http://[IP-adresa]:5000`
3. Např: `http://192.168.1.100:5000`

---

## 🎮 JAK HRÁT (SPRÁVNÁ PRAVIDLA v2.0)

### 📝 PRŮBĚH HRY

#### 1️⃣ **LICITACE**
- První hráč po dealerovi začíná
- Minimální příhoz: **100 bodů**
- Zvyšování po **5 bodech** (105, 110, 115...)
- Speciální hry: **Betl** (0), **Durch** (100), **Sedma** (110)
- Když 2 hráči pasují → vítěz licitace pokračuje

#### 2️⃣ **VÝBĚR TRUMFU** ⭐ NOVÉ
- **Vítěz licitace vybírá trumfovou barvu**
- Vybírá z: ♥ Srdce, ♦ Káry, ♣ Žaludy, ♠ Listy
- (V betlu a durchu není trumf)

#### 3️⃣ **TALON** ⭐ OPRAVENO
- Po výběru trumfu si vítěz **vezme 2 karty z talonu**
- Karty se mu přidají do ruky (má 12 karet)
- **Musí odhodit 2 karty** (bude mít opět 10)
- **Body z odhozených karet získá vítěz!** ⭐

#### 4️⃣ **HLÁŠENÍ SVATEB** ⭐ OPRAVENO
- **Král + Dáma** stejné barvy = **20 bodů**
- V trumfu = **40 bodů** (flék)
- ⚠️ **Lze hlásit JEN PŘED zahráním první karty ze svatby!**
- Po hlášení **MUSÍŠ zahrát krále nebo dámu z té svatby**

#### 5️⃣ **HRANÍ KARET** ⭐ OPRAVENO
**PRAVIDLA:**
1. **Musíš přiznat barvu**, pokud ji máš
2. Pokud nemáš barvu, **musíš fleknout** (zahrát trumf)
3. Pokud nemáš ani barvu ani trumf, **hraj cokoliv**
4. Štych bere **nejvyšší karta** (trumf > barva)

**POŘADÍ SÍLY KARET:**
```
7 < 8 < 9 < Svršek < Dáma < Král < 10 < Eso
```

#### 6️⃣ **BODOVÁNÍ** ⭐ OPRAVENO
**Hodnoty karet:**
- Eso (A) = 11 bodů
- Desítka (10) = 10 bodů
- Král (K) = 4 body
- Dáma (Q) = 3 body
- Svršek (J) = 2 body
- 9, 8, 7 = 0 bodů
- **Celkem: 90 bodů**

**Konec kola:**
- **Vítěz licitace** musí splnit svůj příhoz
  - ✅ Splní → **získá body z příhozu**
  - ❌ Nesplní → **ztratí body z příhozu**
- **Ostatní hráči** vždy získají své body ze štychů + hlášek

---

## ✨ CO JE NOVÉ V VERZI 2.0

### ✅ Opravená pravidla:
- ✅ Výběr trumfu PŘED talounem (ne první kartou)
- ✅ Body z talonu jdou vítězi licitace
- ✅ Svatby lze hlásit jen před zahráním karty
- ✅ Musíš zahrát K/Q z hlášené svatby
- ✅ Správná pravidla přiznávání (přiznat → flek → cokoliv)
- ✅ Speciální pravidla pro Betl a Durch

### ✅ Technické vylepšení:
- ✅ Profesionální error handling
- ✅ Kompletní logging do souboru
- ✅ Automatické reconnection
- ✅ Loading states (víš, kdy server zpracovává)
- ✅ Lepší validace vstupů
- ✅ XSS ochrana v chatu

---

## 🐛 ŘEŠENÍ PROBLÉMŮ

### Server se nespustí
```bash
# Zkontroluj Python verzi
python --version  # Musí být 3.8+

# Port už používán?
# Windows:
netstat -ano | findstr :5000

# Linux/Mac:
lsof -i :5000

# Změň port v server.py (řádek cca 190):
socketio.run(app, host='0.0.0.0', port=5001)  # Změň na 5001
```

### Nelze se připojit z jiného zařízení
```bash
# 1. Zkontroluj, že obě zařízení jsou na STEJNÉ WiFi

# 2. Zjisti správnou IP adresu:
# Windows:
ipconfig  # Hledej IPv4 Address

# Linux/Mac:
ifconfig  # Hledej inet

# 3. Firewall?
# Windows - povol port 5000:
netsh advfirewall firewall add rule name="Mariás" dir=in action=allow protocol=TCP localport=5000

# 4. Použij HTTP (NE HTTPS):
http://192.168.1.100:5000  ✅ Správně
https://192.168.1.100:5000  ❌ Špatně
```

### Karty se neaktualizují / Hra zamrzla
```bash
# 1. Otevři konzoli prohlížeče (F12)
# 2. Zkontroluj chyby
# 3. Obnov stránku (Ctrl+F5 / Cmd+Shift+R)
# 4. Zkontroluj server logy:
tail -f marias_server.log  # Linux/Mac
type marias_server.log     # Windows
```

### Chyba "Module not found"
```bash
# Reinstaluj závislosti
pip install -r requirements.txt --force-reinstall

# Nebo jedna po jedné:
pip install flask
pip install flask-socketio
pip install python-socketio
```

---

## 📱 MOBILNÍ ZAŘÍZENÍ

### iPhone/iPad:
1. Připoj se na stejnou WiFi jako server
2. Otevři **Safari** nebo **Chrome**
3. Zadej `http://[IP-serveru]:5000`
4. (Může být potřeba povolit cookies)

### Android:
1. Připoj se na stejnou WiFi
2. Otevři **Chrome**
3. Zadej `http://[IP-serveru]:5000`

### Tablet:
- Funguje stejně jako mobil
- Lepší zobrazení díky větší obrazovce
- Landscape mode podporován

---

## 🧪 TESTOVÁNÍ LOKÁLNĚ

**Před sdílením v síti otestuj:**

```bash
# 1. Spusť server
python server.py

# 2. Otevři 3 okna prohlížeče:
# - Ctrl+N (nové okno) 3x
# - nebo 3 různé prohlížeče (Chrome, Firefox, Edge)

# 3. V každém okně:
http://localhost:5000

# 4. Přidej se jako 3 různí hráči
# 5. Zahraj kompletní kolo
```

**Co testovat:**
- ✅ Licitace (příhozy, pasování)
- ✅ Výběr trumfu
- ✅ Výměna talonu
- ✅ Hlášení svateb
- ✅ Hraní karet
- ✅ Bodování
- ✅ Chat

---

## 📊 SPOUŠTĚCÍ SKRIPTY

### Windows - Dvojklik:
```batch
run.bat
```

### Linux/Mac:
```bash
chmod +x run.sh  # První spuštění
./run.sh
```

---

## 📝 LOGY A DEBUG

### Kde najdu logy?
```
marias_server.log  # Ve stejné složce jako server.py
```

### Co je v lozích?
```
2024-12-27 10:30:45 - INFO - Nová hra vytvořena
2024-12-27 10:30:50 - INFO - Hráč Alice přidán na pozici 0
2024-12-27 10:31:00 - INFO - Kolo 1 začíná, dealer pozice 0
2024-12-27 10:31:15 - INFO - Alice dal 105 (standard)
2024-12-27 10:31:20 - INFO - Bob pasoval
...
```

### Debug mode:
```python
# V server.py (pro vývoj):
socketio.run(app, debug=True)  # Změň False → True

# Dostaneš detailní traceback při chybách
```

---

## 💡 TIPY PRO NEJLEPŠÍ ZÁŽITEK

1. **Použij Chrome nebo Firefox** - Nejlepší podpora WebSocket
2. **Stabilní WiFi** - Minimalizuje odpojení
3. **Zavři ostatní aplikace** - Lepší výkon
4. **Desktop > Mobile** - Pro nejlepší UX (ale mobile funguje!)
5. **Zkontroluj logy** - Při problémech vždy zkontroluj `marias_server.log`

---

## ⚡ RYCHLÉ PŘÍKAZY

```bash
# Spustit server
python server.py

# Spustit s debug módem
python server.py  # a změň debug=True v kódu

# Spustit testy
python test_game.py

# Zjistit IP adresu
# Windows:
ipconfig | findstr IPv4

# Linux/Mac:
ifconfig | grep inet

# Zastavit server
Ctrl+C  # v terminálu kde běží
```

---

## 🎯 NEXT STEPS

Po úspěšném spuštění:

1. **Přečti pravidla** - Klikni na ℹ️ v aplikaci
2. **Otestuj lokálně** - 3 okna prohlížeče
3. **Pozvi přátele** - Sdílej IP adresu
4. **Užívej si hru!** 🎉

Pro pokročilé nastavení:
- 📖 Čti `README.md` - Kompletní dokumentace
- 🚀 Čti `DEPLOY.md` - Produkční nasazení
- 🔍 Čti `REVIEW.md` - Co je nového v 2.0

---

## 🆘 STÁLE POTŘEBUJEŠ POMOC?

1. **Zkontroluj logy:** `marias_server.log`
2. **Otevři GitHub issue** (pokud je projekt na GitHubu)
3. **Zkontroluj REVIEW.md** - Seznam všech oprav

---

**PŘIPRAVEN HRÁT?** 🃏  
Spusť `python server.py` a užívej si profesionální implementaci mariáše!

---

*Verze 2.0 - Professional Edition*  
*Všechna pravidla podle Českého svazu mariáše*  
*Kód na úrovni production software*