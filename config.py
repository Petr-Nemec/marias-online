"""
Konfigurace serveru Mariáš Online
Upravte tyto hodnoty podle potřeby
"""

# Server nastavení
HOST = '0.0.0.0'  # 0.0.0.0 = dostupný ze sítě, '127.0.0.1' = jen lokálně
PORT = 5000
DEBUG = True  # Při produkčním nasazení nastavte na False

# Bezpečnost
SECRET_KEY = 'marias_secret_key_2024_change_me_in_production'

# Herní nastavení
MAX_PLAYERS = 3
MIN_BID = 100
BID_INCREMENT = 5

# Chat nastavení
MAX_MESSAGE_LENGTH = 200
CHAT_HISTORY_LIMIT = 100

# Timeouts (v sekundách)
PLAYER_TIMEOUT = 300  # 5 minut neaktivity
BID_TIMEOUT = 60      # 1 minuta na licitaci
PLAY_TIMEOUT = 30     # 30 sekund na tah

# WebSocket nastavení
SOCKETIO_PING_TIMEOUT = 60
SOCKETIO_PING_INTERVAL = 25

# Logování
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE = 'marias_server.log'

# Pravidla hry (pro budoucí rozšíření)
GAME_RULES = {
    'card_values': {
        'A': 11,
        '10': 10,
        'K': 4,
        'Q': 3,
        'J': 2,
        '9': 0,
        '8': 0,
        '7': 0
    },
    'special_bids': {
        'betl': 0,
        'durch': 100,
        '7': 110,
        '8': 120,
        '9': 130
    },
    'marriage_points': {
        'normal': 20,
        'trump': 40
    },
    'total_points': 90
}

# Feature flags (zapni/vypni funkce)
FEATURES = {
    'chat_enabled': True,
    'spectators_enabled': True,
    'marriages_enabled': True,
    'special_bids_enabled': True,
    'statistics_enabled': False,  # Pro budoucí implementaci
    'replay_enabled': False       # Pro budoucí implementaci
}

# Zprávy a texty (pro případnou lokalizaci)
MESSAGES = {
    'cs': {
        'welcome': 'Vítejte v Mariáši Online!',
        'game_full': 'Hra je plná, sledujete jako divák',
        'waiting_players': 'Čekáme na hráče...',
        'game_started': 'Hra začíná!',
        'invalid_move': 'Neplatný tah',
        'not_your_turn': 'Nejsi na řadě',
        'bid_too_low': 'Příliš nízký příhoz',
        'round_complete': 'Kolo dokončeno',
        'game_complete': 'Hra dokončena'
    }
}

# Výchozí jazyk
DEFAULT_LANGUAGE = 'cs'

def get_server_info():
    """Vrátí informace o serveru pro výpis"""
    return {
        'host': HOST,
        'port': PORT,
        'debug': DEBUG,
        'max_players': MAX_PLAYERS,
        'features': FEATURES
    }

def validate_config():
    """Validace konfigurace"""
    errors = []
    
    if MIN_BID < 100:
        errors.append("MIN_BID musí být alespoň 100")
    
    if MAX_PLAYERS != 3:
        errors.append("MAX_PLAYERS musí být 3 pro mariáš")
    
    if BID_INCREMENT < 5:
        errors.append("BID_INCREMENT musí být alespoň 5")
    
    if errors:
        raise ValueError(f"Chyby v konfiguraci: {', '.join(errors)}")
    
    return True

# Validace při importu
try:
    validate_config()
except ValueError as e:
    print(f"⚠️  VAROVÁNÍ: {e}")