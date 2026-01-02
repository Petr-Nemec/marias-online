"""
Mariáš Online Server v3.0
SPRÁVNÁ IMPLEMENTACE podle pravidel ČSM
"""

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import logging
from datetime import datetime
from typing import Dict, Optional
import sys

from game_logic import MariaGame, GamePhase

# Konfigurace loggingu
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('marias_server.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'marias_secret_key_v3_change_in_production'

# SocketIO
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25
)

# Globální state
ACTIVE_GAME_ID = "main_game"
games: Dict[str, MariaGame] = {}


def get_game(game_id: str = ACTIVE_GAME_ID) -> MariaGame:
    """Získej nebo vytvoř hru"""
    if game_id not in games:
        games[game_id] = MariaGame()
        logger.info(f"Vytvořena nová hra: {game_id}")
    return games[game_id]


def broadcast_game_state(game: MariaGame, message: str = "", exclude_sid: Optional[str] = None):
    """Rozešli aktuální stav hry všem hráčům"""
    for session_id in list(game.players.keys()) + list(game.spectators):
        if exclude_sid and session_id == exclude_sid:
            continue
        
        try:
            state = game.get_state_for_player(session_id)
            socketio.emit('game_update', {
                'game_state': state,
                'message': message
            }, room=session_id)
        except Exception as e:
            logger.error(f"Chyba při odesílání stavu hráči {session_id}: {e}")


@app.route('/')
def index():
    """Hlavní stránka"""
    return render_template('index.html')


@app.route('/health')
def health():
    """Health check"""
    return {'status': 'ok', 'active_games': len(games), 'version': '3.0'}


@socketio.on('connect')
def handle_connect():
    """Nové připojení"""
    session_id = request.sid
    logger.info(f"Připojení: {session_id}")
    
    game = get_game()
    join_room(ACTIVE_GAME_ID)
    
    emit('connection_established', {
        'session_id': session_id,
        'game_state': game.get_state_for_player(session_id),
        'version': '3.0'
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Odpojení"""
    session_id = request.sid
    logger.info(f"Odpojení: {session_id}")
    
    game = get_game()
    
    if session_id in game.players:
        player = game.players[session_id]
        player.is_connected = False
        logger.info(f"Hráč {player.name} odpojen")
        
        if game.phase != GamePhase.WAITING:
            broadcast_game_state(game, f"{player.name} se odpojil")


@socketio.on('join_game')
def handle_join_game(data: dict):
    """Připojení do hry"""
    session_id = request.sid
    player_name = data.get('name', f'Hráč_{session_id[:4]}')
    
    if not player_name or len(player_name) > 20:
        emit('error', {'message': 'Jméno musí mít 1-20 znaků'})
        return
    
    game = get_game()
    
    try:
        result = game.add_player(session_id, player_name)
        
        if result['success']:
            state = game.get_state_for_player(session_id)
            emit('joined_game', {
                'success': True,
                'position': result.get('position'),
                'is_player': result.get('is_player', False),
                'game_state': state
            })
            
            message = f"{player_name} se připojil"
            if not result.get('is_player'):
                message += " (divák)"
            
            broadcast_game_state(game, message, exclude_sid=session_id)
            
            if game.can_start() and game.phase == GamePhase.WAITING:
                game.start_new_round()
                broadcast_game_state(game, "Hra začíná! Licitace začíná.")
        else:
            emit('joined_game', {
                'success': False,
                'message': result.get('message', 'Nelze se připojit')
            })
    
    except Exception as e:
        logger.error(f"Chyba při připojování hráče: {e}", exc_info=True)
        emit('error', {'message': 'Chyba při připojování do hry'})


@socketio.on('bid_game')
def handle_bid_game(data: dict):
    """Licitace - nabídka hry"""
    session_id = request.sid
    game_type = data.get('game_type')
    
    if not game_type:
        emit('error', {'message': 'Chybí typ hry'})
        return
    
    game = get_game()
    
    try:
        result = game.bid_game(session_id, game_type)
        
        if result['success']:
            broadcast_game_state(game, result.get('message', ''))
            
            if result.get('bidding_over'):
                socketio.emit('bidding_complete', {}, room=ACTIVE_GAME_ID)
        else:
            emit('error', {'message': result.get('message', 'Neplatný příhoz')})
    
    except Exception as e:
        logger.error(f"Chyba při licitaci: {e}", exc_info=True)
        emit('error', {'message': 'Chyba při zpracování licitace'})


@socketio.on('pass_bid')
def handle_pass_bid():
    """Pas v licitaci"""
    session_id = request.sid
    game = get_game()
    
    try:
        result = game.pass_bid(session_id)
        
        if result['success']:
            broadcast_game_state(game, result.get('message', ''))
            
            if result.get('bidding_over'):
                socketio.emit('bidding_complete', {}, room=ACTIVE_GAME_ID)
        else:
            emit('error', {'message': result.get('message', 'Nelze pasovat')})
    
    except Exception as e:
        logger.error(f"Chyba při pasování: {e}", exc_info=True)
        emit('error', {'message': 'Chyba při pasování'})


@socketio.on('select_trump_and_discard')
def handle_trump_and_discard(data: dict):
    """Výběr trumfu a odhození karet"""
    session_id = request.sid
    trump_suit = data.get('trump_suit')
    cards_to_discard = data.get('cards', [])
    
    if not trump_suit:
        emit('error', {'message': 'Musíš vybrat trumf'})
        return
    
    if not isinstance(cards_to_discard, list) or len(cards_to_discard) != 2:
        emit('error', {'message': 'Musíš vybrat přesně 2 karty k odhození'})
        return
    
    game = get_game()
    
    try:
        result = game.select_trump_and_discard(session_id, trump_suit, cards_to_discard)
        
        if result['success']:
            broadcast_game_state(game, result.get('message', ''))
        else:
            emit('error', {'message': result.get('message', 'Chyba při výběru')})
    
    except Exception as e:
        logger.error(f"Chyba při výběru trumfu: {e}", exc_info=True)
        emit('error', {'message': 'Chyba při výběru trumfu'})


@socketio.on('declare_marriage')
def handle_declare_marriage(data: dict):
    """Hlášení svatby (mariáše)"""
    session_id = request.sid
    suit = data.get('suit')
    
    if not suit:
        emit('error', {'message': 'Musíš vybrat barvu'})
        return
    
    game = get_game()
    
    try:
        result = game.declare_marriage(session_id, suit)
        
        if result['success']:
            broadcast_game_state(game, result.get('message', ''))
        else:
            emit('error', {'message': result.get('message', 'Nelze hlásit')})
    
    except Exception as e:
        logger.error(f"Chyba při hlášení svatby: {e}", exc_info=True)
        emit('error', {'message': 'Chyba při hlášení svatby'})


@socketio.on('play_card')
def handle_play_card(data: dict):
    """Zahrání karty"""
    session_id = request.sid
    card_data = data.get('card')
    
    if not card_data:
        emit('error', {'message': 'Chybí data karty'})
        return
    
    game = get_game()
    
    try:
        result = game.play_card(session_id, card_data)
        
        if result['success']:
            broadcast_game_state(game, result.get('message', ''))
            
            if result.get('trick_complete'):
                socketio.sleep(1.5)
                socketio.emit('trick_complete', {
                    'winner': result.get('winner'),
                    'winner_name': result.get('winner_name')
                }, room=ACTIVE_GAME_ID)
            
            if result.get('round_complete'):
                socketio.sleep(2)
                socketio.emit('round_complete', {
                    'round_results': result.get('round_results')
                }, room=ACTIVE_GAME_ID)
        else:
            emit('error', {'message': result.get('message', 'Nelze zahrát kartu')})
    
    except Exception as e:
        logger.error(f"Chyba při hraní karty: {e}", exc_info=True)
        emit('error', {'message': 'Chyba při zpracování tahu'})


@socketio.on('start_new_round')
def handle_new_round():
    """Začátek nového kola"""
    session_id = request.sid
    game = get_game()
    
    try:
        if game.can_start() and game.phase == GamePhase.ROUND_END:
            game.start_new_round()
            broadcast_game_state(game, "Nové kolo začíná!")
        else:
            emit('error', {'message': 'Nelze začít nové kolo'})
    
    except Exception as e:
        logger.error(f"Chyba při začátku kola: {e}", exc_info=True)
        emit('error', {'message': 'Chyba při začátku kola'})


@socketio.on('chat_message')
def handle_chat(data: dict):
    """Chat zpráva"""
    session_id = request.sid
    message = data.get('message', '').strip()
    
    if not message or len(message) > 200:
        return
    
    message = message.replace('<', '&lt;').replace('>', '&gt;')
    
    game = get_game()
    
    player_name = 'Divák'
    if session_id in game.players:
        player_name = game.players[session_id].name
    
    socketio.emit('chat_message', {
        'player': player_name,
        'message': message,
        'timestamp': datetime.now().strftime('%H:%M:%S')
    }, room=ACTIVE_GAME_ID)


@socketio.on_error_default
def default_error_handler(e):
    """Globální error handler"""
    logger.error(f"SocketIO error: {e}", exc_info=True)
    emit('error', {'message': 'Nastala chyba na serveru'})


if __name__ == '__main__':
    import socket
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "localhost"
    
    print("=" * 60)
    print("🃏 MARIÁŠ ONLINE SERVER v3.0")
    print("=" * 60)
    print("✅ SPRÁVNÁ PRAVIDLA:")
    print("  - Hlášky: Svršek (Q) + Král (K)")
    print("  - Desítka je DRUHÁ nejsilnější karta")
    print("  - Pořadí: 7-8-9-J-Q-K-10-A")
    print("  - Rozdávání: 5-5-5-(2 talon)-5-5-5")
    print("=" * 60)
    print(f"✓ Server běží na portu 5000")
    print(f"✓ Lokální přístup:  http://localhost:5000")
    print(f"✓ Síťový přístup:   http://{local_ip}:5000")
    print("=" * 60)
    print("📝 Logy se ukládají do: marias_server.log")
    print("=" * 60)
    print("")
    
    try:
        socketio.run(
            app,
            host='0.0.0.0',
            port=5000,
            debug=False,
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        logger.info("Server zastaven uživatelem")
        print("\n\n👋 Server ukončen")
    except Exception as e:
        logger.error(f"Kritická chyba serveru: {e}", exc_info=True)
        print(f"\n\n❌ Chyba: {e}")