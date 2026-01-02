"""
Herní logika Licitovaného Mariáše - SPRÁVNÁ IMPLEMENTACE
Podle oficiálních pravidel Českého svazu mariáše

KRITICKÉ OPRAVY v3.0:
- Hlášky: SVRŠEK + KRÁL (ne Q+K!)
- Desítka je DRUHÁ nejsilnější karta (po esu)
- Pořadí: 7-8-9-spodek-svršek-král-10-A
- Hodnoty: A=11, 10=10, K=4, svršek=3, spodek=2
- Rozdávání: 5-5-5-(2 talon)-5-5-5
"""

import random
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class GamePhase(Enum):
    """Fáze hry"""
    WAITING = "waiting"
    BIDDING = "bidding"
    PLAYING = "playing"
    ROUND_END = "round_end"


class GameType(Enum):
    """Typy her v mariáši"""
    HRA = "hra"  # Základní hra
    SEDMA = "sedma"  # Hra se sedmou
    STO = "sto"  # Hra se stovkou
    BETL = "betl"  # Nesmí vzít žádnou
    DURCH = "durch"  # Musí vzít všechny


@dataclass
class Card:
    """
    Reprezentace karty v mariáši
    
    DŮLEŽITÉ:
    - 'J' = spodek (jack)
    - 'Q' = svršek (queen) 
    - Pri hrách s trumfy: 7 < 8 < 9 < J < Q < K < 10 < A
    """
    suit: str  # 'hearts', 'diamonds', 'clubs', 'spades'
    rank: str  # '7', '8', '9', '10', 'J', 'Q', 'K', 'A'
    
    SUITS = ['hearts', 'diamonds', 'clubs', 'spades']
    RANKS = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    
    # České názvy
    SUIT_NAMES_CZ = {
        'hearts': 'Červené/Srdce',
        'diamonds': 'Kule',
        'clubs': 'Žaludy',
        'spades': 'Zelené/Listy'
    }
    
    RANK_NAMES_CZ = {
        '7': 'Sedma',
        '8': 'Osma',
        '9': 'Devítka',
        '10': 'Desítka',
        'J': 'Spodek',  # ← DŮLEŽITÉ!
        'Q': 'Svršek',  # ← DŮLEŽITÉ!
        'K': 'Král',
        'A': 'Eso'
    }
    
    def __hash__(self):
        return hash((self.suit, self.rank))
    
    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.suit == other.suit and self.rank == other.rank
    
    def to_dict(self) -> Dict:
        return {'suit': self.suit, 'rank': self.rank}
    
    @staticmethod
    def from_dict(data: Dict) -> 'Card':
        return Card(suit=data['suit'], rank=data['rank'])
    
    def get_value(self) -> int:
        """
        Bodová hodnota karty
        SPRÁVNÉ hodnoty podle pravidel mariáše
        """
        values = {
            'A': 11,   # Eso
            '10': 10,  # Desítka
            'K': 4,    # Král
            'Q': 3,    # Svršek ← OPRAVENO!
            'J': 2,    # Spodek ← OPRAVENO!
            '9': 0,
            '8': 0,
            '7': 0
        }
        return values[self.rank]
    
    def get_order_trump_game(self, trump_suit: Optional[str] = None) -> int:
        """
        Pořadí síly karty PŘI HRE S TRUMFY
        KRITICKÉ: Desítka je DRUHÁ nejsilnější karta!
        
        Pořadí: 7 < 8 < 9 < spodek(J) < svršek(Q) < král(K) < 10 < A
        """
        # Při hře s trumfy: 10 je před esem!
        rank_order = {
            '7': 0,
            '8': 1,
            '9': 2,
            'J': 3,   # Spodek
            'Q': 4,   # Svršek
            'K': 5,   # Král
            '10': 6,  # Desítka - DRUHÁ nejsilnější! ← OPRAVENO!
            'A': 7    # Eso - nejsilnější
        }
        
        base_strength = rank_order[self.rank]
        
        # Trumf je silnější než ostatní barvy
        if trump_suit and self.suit == trump_suit:
            return 100 + base_strength
        
        return base_strength
    
    def get_order_no_trump_game(self) -> int:
        """
        Pořadí síly karty PŘI BETLU A DURCHU (bez trumfů)
        
        Pořadí: 7 < 8 < 9 < 10 < spodek(J) < svršek(Q) < král(K) < A
        """
        rank_order = {
            '7': 0,
            '8': 1,
            '9': 2,
            '10': 3,  # Desítka má normální pozici
            'J': 4,   # Spodek
            'Q': 5,   # Svršek
            'K': 6,   # Král
            'A': 7    # Eso
        }
        return rank_order[self.rank]
    
    def __repr__(self):
        return f"{self.rank}{self.suit[0].upper()}"


class Deck:
    """Správa balíčku karet"""
    
    @staticmethod
    def create_deck() -> List[Card]:
        """Vytvoř kompletní balíček 32 karet"""
        return [Card(suit, rank) for suit in Card.SUITS for rank in Card.RANKS]
    
    @staticmethod
    def shuffle_and_deal_licitovany() -> Tuple[List[List[Card]], List[Card]]:
        """
        Rozdání pro LICITOVANÝ mariáš
        
        SPRÁVNÉ rozdání: 5-5-5-(2 talon)-5-5-5
        - Každému 5 karet
        - 2 karty na talon
        - Pak znovu každému 5 karet
        """
        deck = Deck.create_deck()
        random.shuffle(deck)
        
        hands = [[], [], []]
        
        # První kolo - každému 5 karet
        for player_idx in range(3):
            for _ in range(5):
                hands[player_idx].append(deck.pop())
        
        # 2 karty do talonu
        talon = [deck.pop(), deck.pop()]
        
        # Druhé kolo - každému dalších 5 karet
        for player_idx in range(3):
            for _ in range(5):
                hands[player_idx].append(deck.pop())
        
        return hands, talon


class Player:
    """Reprezentace hráče"""
    
    def __init__(self, session_id: str, name: str, position: int):
        self.session_id = session_id
        self.name = name
        self.position = position
        self.hand: List[Card] = []
        self.tricks_won: List[List[Tuple[str, Card]]] = []
        self.declared_marriages: List[str] = []
        self.round_score = 0
        self.total_score = 0
        self.is_connected = True
    
    def reset_round(self):
        """Reset pro nové kolo"""
        self.hand = []
        self.tricks_won = []
        self.declared_marriages = []
        self.round_score = 0
    
    def has_marriage(self, suit: str) -> bool:
        """
        Kontrola svatby (HLÁŠKY)
        
        SPRÁVNĚ: Svršek (Q) + Král (K) stejné barvy!
        """
        has_queen = any(c.suit == suit and c.rank == 'Q' for c in self.hand)  # Svršek
        has_king = any(c.suit == suit and c.rank == 'K' for c in self.hand)   # Král
        return has_queen and has_king
    
    def to_dict(self, is_current: bool = False, is_bidder: bool = False, 
                is_dealer: bool = False) -> Dict:
        return {
            'id': self.session_id,
            'name': self.name,
            'position': self.position,
            'card_count': len(self.hand),
            'tricks_count': len(self.tricks_won),
            'is_current': is_current,
            'is_bidder': is_bidder,
            'is_dealer': is_dealer,
            'round_score': self.round_score,
            'total_score': self.total_score,
            'connected': self.is_connected
        }


class MariaGame:
    """
    Licitovaný Mariáš - Kompletní implementace podle ČSM
    
    V3.0 - SPRÁVNÁ PRAVIDLA
    """
    
    # Hodnoty her podle pravidel
    GAME_VALUES = {
        GameType.HRA: 1,
        GameType.SEDMA: 2,
        GameType.STO: 4,
        GameType.BETL: 10,
        GameType.DURCH: 20
    }
    
    MARRIAGE_POINTS = 20
    TRUMP_MARRIAGE_POINTS = 40
    LAST_TRICK_POINTS = 10
    TOTAL_CARD_POINTS = 90
    
    def __init__(self):
        self.players: Dict[str, Player] = {}
        self.spectators: set = set()
        self.phase = GamePhase.WAITING
        
        # Herní stav
        self.round_number = 0
        self.dealer_position = 0
        self.current_player_position = 0
        
        # Karty
        self.talon: List[Card] = []
        self.talon_discarded: List[Card] = []
        self.current_trick: List[Tuple[str, Card]] = []
        
        # Licitace
        self.current_game_type = GameType.HRA
        self.bidder_id: Optional[str] = None
        self.bidding_players: List[str] = []
        self.bidding_index = 0
        
        # Hra
        self.trump_suit: Optional[str] = None
        self.lead_suit: Optional[str] = None
        self.trick_number = 0
        self.first_marriage_card_played: Dict[str, bool] = {}
        
        logger.info("Nová hra vytvořena")
    
    def add_player(self, session_id: str, name: str) -> Dict:
        """Přidej hráče do hry"""
        if session_id in self.players:
            return {'success': True, 'is_player': True, 
                    'position': self.players[session_id].position}
        
        occupied_positions = {p.position for p in self.players.values()}
        
        if len(occupied_positions) < 3:
            position = next(i for i in range(3) if i not in occupied_positions)
            player = Player(session_id, name, position)
            self.players[session_id] = player
            
            logger.info(f"Hráč {name} přidán na pozici {position}")
            return {'success': True, 'is_player': True, 'position': position}
        else:
            self.spectators.add(session_id)
            logger.info(f"Divák {name} přidán")
            return {'success': True, 'is_player': False, 
                    'message': 'Hra je plná, sledujete jako divák'}
    
    def remove_player(self, session_id: str):
        """Odstraň hráče"""
        if session_id in self.players:
            player = self.players[session_id]
            logger.info(f"Hráč {player.name} odpojen")
            del self.players[session_id]
            
            if len(self.players) < 3 and self.phase != GamePhase.WAITING:
                self.reset_game()
        elif session_id in self.spectators:
            self.spectators.remove(session_id)
    
    def can_start(self) -> bool:
        """Lze začít hru?"""
        return len(self.players) == 3
    
    def start_new_round(self):
        """Začni nové kolo"""
        if not self.can_start():
            raise ValueError("Nelze začít hru, není 3 hráčů")
        
        self.round_number += 1
        self.phase = GamePhase.BIDDING
        
        # Reset
        for player in self.players.values():
            player.reset_round()
        
        self.current_trick = []
        self.trick_number = 0
        self.trump_suit = None
        self.lead_suit = None
        self.talon_discarded = []
        self.first_marriage_card_played = {}
        
        # Rozdej karty - SPRÁVNÉ rozdání pro licitovaný mariáš
        player_list = self._get_players_by_position()
        hands, talon = Deck.shuffle_and_deal_licitovany()
        
        for player, hand in zip(player_list, hands):
            # Seřaď karty pro lepší přehlednost
            player.hand = sorted(hand, key=lambda c: (
                Card.SUITS.index(c.suit), 
                Card.RANKS.index(c.rank)
            ))
        
        self.talon = talon
        
        # Licitace začíná hráč po dealerovi (forhont)
        self.current_player_position = (self.dealer_position + 1) % 3
        
        # Setup licitace
        self.bidding_players = [p.session_id for p in self._get_players_by_position()]
        self.bidding_index = self.current_player_position
        self.current_game_type = GameType.HRA
        self.bidder_id = None
        
        logger.info(f"Kolo {self.round_number} začíná, rozdává pozice {self.dealer_position}")
    
    # ========== LICITACE ==========
    
    def bid_game(self, session_id: str, game_type: str) -> Dict:
        """
        Licitace hry
        
        Pořadí her: hra < sedma < sto < betl < durch
        """
        if self.phase != GamePhase.BIDDING:
            return {'success': False, 'message': 'Teď není čas na licitaci'}
        
        player = self.players.get(session_id)
        if not player or player.position != self.current_player_position:
            return {'success': False, 'message': 'Nejsi na řadě'}
        
        try:
            new_type = GameType(game_type)
        except ValueError:
            return {'success': False, 'message': 'Neplatný typ hry'}
        
        # Kontrola, že nabízí vyšší hru
        game_order = [GameType.HRA, GameType.SEDMA, GameType.STO, 
                      GameType.BETL, GameType.DURCH]
        
        current_index = game_order.index(self.current_game_type)
        new_index = game_order.index(new_type)
        
        if new_index <= current_index:
            return {'success': False, 'message': 'Musíš nabídnout vyšší hru'}
        
        # Přijmi příhoz
        self.current_game_type = new_type
        self.bidder_id = session_id
        
        logger.info(f"{player.name} nabízí {game_type}")
        
        # Další hráč
        self._next_bidder()
        
        return {'success': True, 
                'message': f'{player.name} nabízí {game_type}'}
    
    def pass_bid(self, session_id: str) -> Dict:
        """Pas v licitaci"""
        if self.phase != GamePhase.BIDDING:
            return {'success': False, 'message': 'Teď není čas na licitaci'}
        
        player = self.players.get(session_id)
        if not player or player.position != self.current_player_position:
            return {'success': False, 'message': 'Nejsi na řadě'}
        
        logger.info(f"{player.name} pasoval")
        
        # Odstraň z licitace
        self.bidding_players = [p for p in self.bidding_players if p != session_id]
        
        # Pokud zbývá jen jeden hráč, končí licitace
        if len(self.bidding_players) <= 1:
            if self.bidder_id:
                return self._end_bidding()
            else:
                # Nikdo nechtěl hrát - znovu rozdej
                logger.info("Nikdo nechtěl hrát, nové rozdání")
                self.start_new_round()
                return {'success': True, 'message': 'Nové rozdání - nikdo nechtěl hrát'}
        
        # Další hráč
        self._next_bidder()
        
        return {'success': True, 'message': f'{player.name} pasoval'}
    
    def _next_bidder(self):
        """Přepni na dalšího licitujícího hráče"""
        while True:
            self.current_player_position = (self.current_player_position + 1) % 3
            player_id = self._get_player_at_position(self.current_player_position)
            
            if player_id in self.bidding_players:
                break
    
    def _end_bidding(self) -> Dict:
        """Ukonči licitaci"""
        if not self.bidder_id:
            return {'success': False, 'message': 'Chyba licitace'}
        
        bidder = self.players[self.bidder_id]
        
        # Vítěz si vezme talon a odhodí 2 karty
        bidder.hand.extend(self.talon)
        bidder.hand.sort(key=lambda c: (Card.SUITS.index(c.suit), Card.RANKS.index(c.rank)))
        
        self.phase = GamePhase.PLAYING
        self.current_player_position = bidder.position
        
        logger.info(f"{bidder.name} vyhrál licitaci s {self.current_game_type.value}")
        
        return {
            'success': True,
            'bidding_over': True,
            'message': f'{bidder.name} vyhrál licitaci, vezme si talon a zvolí trumf'
        }
    
    # ========== TALON ==========
    
    def select_trump_and_discard(self, session_id: str, trump_suit: str, 
                                  cards_to_discard: List[Dict]) -> Dict:
        """
        Vítěz licitace vybírá trumf a odhazuje 2 karty
        
        DŮLEŽITÉ: Body z odhozených karet získá vítěz!
        """
        if self.phase != GamePhase.PLAYING:
            return {'success': False, 'message': 'Nesprávná fáze'}
        
        if session_id != self.bidder_id:
            return {'success': False, 'message': 'Nejsi vítěz licitace'}
        
        if trump_suit not in Card.SUITS:
            return {'success': False, 'message': 'Neplatná barva trumfu'}
        
        if len(cards_to_discard) != 2:
            return {'success': False, 'message': 'Musíš odhodit přesně 2 karty'}
        
        bidder = self.players[self.bidder_id]
        discard_cards = [Card.from_dict(c) for c in cards_to_discard]
        
        # Kontrola, že má karty
        for card in discard_cards:
            if card not in bidder.hand:
                return {'success': False, 'message': 'Nemáš tyto karty'}
        
        # Pravidlo: Nesmí odhodit esa a desítky (kromě betlu/durchu)
        if self.current_game_type not in [GameType.BETL, GameType.DURCH]:
            for card in discard_cards:
                if card.rank in ['A', '10']:
                    return {'success': False, 
                            'message': 'Nesmíš odhodit esa a desítky!'}
        
        # Odstraň karty z ruky
        for card in discard_cards:
            bidder.hand.remove(card)
        
        # Ulož odhozené karty (jejich body půjdou vítězi)
        self.talon_discarded = discard_cards
        
        # Nastav trumf
        self.trump_suit = trump_suit
        
        logger.info(f"Trumf: {trump_suit}, odhozeno: {discard_cards}")
        
        return {
            'success': True,
            'message': f'Trumf: {Card.SUIT_NAMES_CZ[trump_suit]}, hra začíná!'
        }
    
    # ========== HLÁŠENÍ SVATEB ==========
    
    def declare_marriage(self, session_id: str, suit: str) -> Dict:
        """
        Hlášení svatby (mariáše)
        
        SPRÁVNĚ: Svršek (Q) + Král (K) stejné barvy!
        Hláška se provede položením první karty (Q nebo K) na své zdvihy
        """
        if self.phase != GamePhase.PLAYING:
            return {'success': False, 'message': 'Teď nemůžeš hlásit'}
        
        player = self.players.get(session_id)
        if not player or player.position != self.current_player_position:
            return {'success': False, 'message': 'Nejsi na řadě'}
        
        # V betlu a durchu nelze hlásit
        if self.current_game_type in [GameType.BETL, GameType.DURCH]:
            return {'success': False, 'message': 'V této hře nelze hlásit svatby'}
        
        # Kontrola svatby
        if not player.has_marriage(suit):
            return {'success': False, 
                    'message': 'Nemáš svrška (Q) a krále (K) této barvy'}
        
        # Již hlášeno?
        if suit in player.declared_marriages:
            return {'success': False, 'message': 'Tuto svatbu jsi už hlásil'}
        
        # Hláška platí
        player.declared_marriages.append(suit)
        self.first_marriage_card_played[f"{session_id}_{suit}"] = False
        
        # Body
        points = self.TRUMP_MARRIAGE_POINTS if suit == self.trump_suit else self.MARRIAGE_POINTS
        
        suit_name = Card.SUIT_NAMES_CZ[suit]
        marriage_type = "fleka" if suit == self.trump_suit else "mariáše"
        
        logger.info(f"{player.name} hlásí {marriage_type} v {suit} (+{points})")
        
        return {
            'success': True,
            'message': f'{player.name} hlásí {marriage_type} {suit_name} (+{points} bodů)',
            'points': points
        }
    
    # ========== HRANÍ KARET ==========
    
    def play_card(self, session_id: str, card_data: Dict) -> Dict:
        """Zahraj kartu"""
        if self.phase != GamePhase.PLAYING:
            return {'success': False, 'message': 'Teď nemůžeš hrát kartu'}
        
        player = self.players.get(session_id)
        if not player or player.position != self.current_player_position:
            return {'success': False, 'message': 'Nejsi na řadě'}
        
        card = Card.from_dict(card_data)
        
        if card not in player.hand:
            return {'success': False, 'message': 'Nemáš tuto kartu'}
        
        # Pokud hlásil svatbu, MUSÍ zahrát Q nebo K z té svatby
        for suit in player.declared_marriages:
            key = f"{session_id}_{suit}"
            if key in self.first_marriage_card_played and not self.first_marriage_card_played[key]:
                # Musí zahrát Q nebo K z této svatby
                if card.suit == suit and card.rank in ['Q', 'K']:
                    self.first_marriage_card_played[key] = True
                    break
                else:
                    return {'success': False, 
                            'message': 'Musíš zahrát svrška (Q) nebo krále (K) z hlášené svatby'}
        
        # Validace tahu
        if len(self.current_trick) == 0:
            self.lead_suit = card.suit
        else:
            if not self._is_valid_play(player, card):
                return {'success': False, 
                        'message': 'Neplatný tah - musíš přiznat barvu nebo flek'}
        
        # Zahraj kartu
        player.hand.remove(card)
        self.current_trick.append((session_id, card))
        
        logger.info(f"{player.name} hraje {card}")
        
        message = f'{player.name} hraje {Card.RANK_NAMES_CZ[card.rank]} {Card.SUIT_NAMES_CZ[card.suit]}'
        
        # Všichni hráli?
        if len(self.current_trick) == 3:
            return self._complete_trick(message)
        
        # Další hráč
        self._next_player()
        
        return {'success': True, 'message': message}
    
    def _is_valid_play(self, player: Player, card: Card) -> bool:
        """
        Validace tahu podle pravidel mariáše
        1. Musíš přiznat barvu
        2. Pokud nemáš barvu, musíš flek
        3. Pokud nemáš ani barvu ani flek, můžeš hrát cokoliv
        4. Musíš přebíjet (pokud můžeš)
        """
        lead_card = self.current_trick[0][1]
        lead_suit = lead_card.suit
        
        has_lead_suit = any(c.suit == lead_suit for c in player.hand)
        has_trump = self.trump_suit and any(c.suit == self.trump_suit for c in player.hand)
        
        # Má barvu - musí ji zahrát
        if has_lead_suit:
            if card.suit != lead_suit:
                return False
            # TODO: Kontrola přebíjení (pokud může, musí)
            return True
        
        # Nemá barvu - musí fleknout (pokud má trumf)
        if has_trump:
            return card.suit == self.trump_suit
        
        # Nemá ani barvu ani trumf - může hrát cokoliv
        return True
    
    def _complete_trick(self, last_message: str) -> Dict:
        """Dokonči štych"""
        winner_id = self._determine_trick_winner()
        winner = self.players[winner_id]
        
        winner.tricks_won.append(self.current_trick.copy())
        
        self.trick_number += 1
        self.current_trick = []
        self.lead_suit = None
        
        # Další hraje vítěz
        self.current_player_position = winner.position
        
        logger.info(f"{winner.name} bere štych {self.trick_number}")
        
        # Konec kola?
        if self.trick_number >= 10:
            return self._end_round(last_message)
        
        return {
            'success': True,
            'message': last_message,
            'trick_complete': True,
            'winner': winner_id,
            'winner_name': winner.name
        }
    
    def _determine_trick_winner(self) -> str:
        """
        Určí vítěze štychu
        
        DŮLEŽITÉ: Používá správné pořadí karet včetně desítky!
        """
        lead_suit = self.current_trick[0][1].suit
        
        best_player_id = self.current_trick[0][0]
        best_card = self.current_trick[0][1]
        
        # Použij správnou funkci podle typu hry
        if self.current_game_type in [GameType.BETL, GameType.DURCH]:
            best_strength = best_card.get_order_no_trump_game()
        else:
            best_strength = best_card.get_order_trump_game(self.trump_suit)
        
        for player_id, card in self.current_trick[1:]:
            if self.current_game_type in [GameType.BETL, GameType.DURCH]:
                strength = card.get_order_no_trump_game()
            else:
                strength = card.get_order_trump_game(self.trump_suit)
            
            # Trumf bije vše
            if self.trump_suit:
                if card.suit == self.trump_suit and best_card.suit != self.trump_suit:
                    best_player_id = player_id
                    best_card = card
                    best_strength = strength
                elif (card.suit == self.trump_suit and best_card.suit == self.trump_suit) or \
                     (card.suit == lead_suit and best_card.suit == lead_suit):
                    if strength > best_strength:
                        best_player_id = player_id
                        best_card = card
                        best_strength = strength
            else:
                # Bez trumfu - jen stejná barva
                if card.suit == lead_suit and strength > best_strength:
                    best_player_id = player_id
                    best_card = card
                    best_strength = strength
        
        return best_player_id
    
    # ========== KONEC KOLA ==========
    
    def _end_round(self, last_message: str) -> Dict:
        """Konec kola - spočítej body"""
        self.phase = GamePhase.ROUND_END
        
        logger.info("Konec kola, počítání bodů")
        
        # Spočítej body každého hráče
        for player in self.players.values():
            points = 0
            
            # Body z karet ve štychách
            for trick in player.tricks_won:
                for _, card in trick:
                    points += card.get_value()
            
            # Body z hlášek
            for suit in player.declared_marriages:
                points += self.TRUMP_MARRIAGE_POINTS if suit == self.trump_suit else self.MARRIAGE_POINTS
            
            player.round_score = points
        
        # Body z odhozených karet z talonu jdou vítězi
        if self.bidder_id and self.talon_discarded:
            bidder = self.players[self.bidder_id]
            talon_points = sum(card.get_value() for card in self.talon_discarded)
            bidder.round_score += talon_points
            logger.info(f"Body z talonu ({talon_points}) přičteny vítězi")
        
        # Body za poslední štych
        for player in self.players.values():
            if len(player.tricks_won) > 0 and self.trick_number == 10:
                # Poslední štych byl v player.tricks_won[-1]
                if player.tricks_won[-1] == self.players[self._get_player_at_position(player.position)].tricks_won[-1]:
                    player.round_score += self.LAST_TRICK_POINTS
                    logger.info(f"{player.name} získal poslední štych (+10)")
        
        # Kontrola splnění závazku
        bidder = self.players[self.bidder_id]
        game_value = self.GAME_VALUES[self.current_game_type]
        
        success = False
        
        if self.current_game_type == GameType.BETL:
            success = len(bidder.tricks_won) == 0
        elif self.current_game_type == GameType.DURCH:
            success = len(bidder.tricks_won) == 10
        elif self.current_game_type == GameType.SEDMA:
            # TODO: Kontrola sedmy (poslední štych trumfovou sedmou)
            success = bidder.round_score > (self.TOTAL_CARD_POINTS // 2)
        elif self.current_game_type == GameType.STO:
            success = bidder.round_score >= 100
        else:  # HRA
            success = bidder.round_score > (self.TOTAL_CARD_POINTS // 2)
        
        if success:
            bidder.total_score += game_value * 20  # Základní sazba 20h
        else:
            bidder.total_score -= game_value * 20
        
        # Ostatní hráči dostanou své body (bez závazku)
        for player_id, player in self.players.items():
            if player_id != self.bidder_id:
                # V licitovaném mariáši protihráči nedostávají body automaticky
                # (v některých variantách ano, záleží na pravidlech)
                pass
        
        # Dealer rotuje
        self.dealer_position = (self.dealer_position + 1) % 3
        
        round_results = {
            player_id: {
                'round_score': player.round_score,
                'total_score': player.total_score,
                'tricks_count': len(player.tricks_won),
                'is_bidder': player_id == self.bidder_id,
                'success': player_id == self.bidder_id and success
            }
            for player_id, player in self.players.items()
        }
        
        logger.info(f"Výsledky kola: {round_results}")
        
        return {
            'success': True,
            'message': last_message,
            'round_complete': True,
            'round_results': round_results
        }
    
    # ========== POMOCNÉ METODY ==========
    
    def _get_players_by_position(self) -> List[Player]:
        """Vrátí hráče seřazené podle pozice"""
        return sorted(self.players.values(), key=lambda p: p.position)
    
    def _get_player_at_position(self, position: int) -> str:
        """Vrátí ID hráče na dané pozici"""
        for pid, player in self.players.items():
            if player.position == position:
                return pid
        return None
    
    def _next_player(self):
        """Přepni na dalšího hráče"""
        self.current_player_position = (self.current_player_position + 1) % 3
    
    def reset_game(self):
        """Reset celé hry"""
        self.phase = GamePhase.WAITING
        self.round_number = 0
        self.dealer_position = 0
        for player in self.players.values():
            player.reset_round()
            player.total_score = 0
        logger.info("Hra resetována")
    
    # ========== SERIALIZACE ==========
    
    def get_state_for_player(self, session_id: str) -> Dict:
        """Získej herní stav pro konkrétního hráče"""
        player = self.players.get(session_id)
        is_player = player is not None
        
        current_player_id = self._get_player_at_position(self.current_player_position)
        
        players_list = [
            p.to_dict(
                is_current=(p.session_id == current_player_id),
                is_bidder=(p.session_id == self.bidder_id),
                is_dealer=(p.position == self.dealer_position)
            )
            for p in self._get_players_by_position()
        ]
        
        state = {
            'phase': self.phase.value,
            'round_number': self.round_number,
            'trick_number': self.trick_number,
            'is_player': is_player,
            'players': players_list,
            'current_game_type': self.current_game_type.value if self.current_game_type else None,
            'trump_suit': self.trump_suit,
            'lead_suit': self.lead_suit,
            'current_trick': [
                {
                    'player_id': pid,
                    'player_name': self.players[pid].name,
                    'card': card.to_dict()
                }
                for pid, card in self.current_trick
            ],
            'is_your_turn': is_player and player.position == self.current_player_position,
            'is_bidder': is_player and session_id == self.bidder_id,
        }
        
        if is_player:
            state['hand'] = [card.to_dict() for card in player.hand]
            state['declared_marriages'] = player.declared_marriages
            state['tricks_won_count'] = len(player.tricks_won)
            
            # Pokud je vítěz a má talon, musí odhodit
            if session_id == self.bidder_id and self.phase == GamePhase.PLAYING and not self.trump_suit:
                state['needs_trump_and_discard'] = True
                state['has_talon'] = True
        
        return state