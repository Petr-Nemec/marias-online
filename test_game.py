"""
Kompletní test suite pro Mariáš v2.0
Testuje všechna nová pravidla a opravy
"""

import sys
from game_logic import Card, Deck, MariaGame, GamePhase, BidType, Player

class TestColors:
    """ANSI barvy pro hezký výstup"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_test(name):
    """Pěkný výpis testu"""
    print(f"\n{TestColors.BLUE}🧪 Test: {name}{TestColors.RESET}")

def print_success():
    """Úspěch"""
    print(f"   {TestColors.GREEN}✓ Úspěch{TestColors.RESET}")

def print_error(msg):
    """Chyba"""
    print(f"   {TestColors.RED}✗ Chyba: {msg}{TestColors.RESET}")

def print_info(msg):
    """Info"""
    print(f"   {TestColors.YELLOW}ℹ {msg}{TestColors.RESET}")


# ========== ZÁKLADNÍ TESTY ==========

def test_card_creation():
    """Test vytvoření karty"""
    print_test("Vytvoření karty")
    
    card = Card('hearts', 'A')
    assert card.suit == 'hearts', "Špatná barva"
    assert card.rank == 'A', "Špatný rank"
    assert card.get_value() == 11, "Špatná hodnota esa"
    
    print_success()

def test_card_strength():
    """Test síly karet s trumfem"""
    print_test("Síla karet s trumfem")
    
    ace = Card('hearts', 'A')
    seven = Card('hearts', '7')
    trump_seven = Card('spades', '7')
    
    # Eso je silnější než sedma
    assert ace.get_order() > seven.get_order(), "Eso by mělo být silnější než 7"
    
    # Trumfová sedma je silnější než netrumfové eso
    assert trump_seven.get_order('spades') > ace.get_order('spades'), \
        "Trumfová karta by měla být silnější než netrumf"
    
    print_success()

def test_deck_creation():
    """Test vytvoření balíčku"""
    print_test("Vytvoření balíčku 32 karet")
    
    deck = Deck.create_deck()
    assert len(deck) == 32, f"Balíček musí mít 32 karet, má {len(deck)}"
    
    # Kontrola unikátnosti
    unique_cards = set((c.suit, c.rank) for c in deck)
    assert len(unique_cards) == 32, "Karty musí být unikátní"
    
    print_success()

def test_deck_dealing():
    """Test rozdání karet"""
    print_test("Rozdání karet (3x10 + 2 talon)")
    
    hands, talon = Deck.shuffle_and_deal(3)
    
    assert len(hands) == 3, "Musí být 3 ruce"
    assert all(len(hand) == 10 for hand in hands), "Každá ruka musí mít 10 karet"
    assert len(talon) == 2, "Talon musí mít 2 karty"
    
    # Kontrola celkového počtu
    total_cards = sum(len(hand) for hand in hands) + len(talon)
    assert total_cards == 32, f"Celkem musí být 32 karet, je {total_cards}"
    
    print_success()


# ========== GAME INITIALIZATION ==========

def test_game_initialization():
    """Test inicializace hry"""
    print_test("Inicializace hry")
    
    game = MariaGame()
    
    assert game.phase == GamePhase.WAITING, "Fáze by měla být WAITING"
    assert len(game.players) == 0, "Počet hráčů by měl být 0"
    assert game.current_bid == 100, "Minimální příhoz by měl být 100"
    
    print_success()

def test_add_players():
    """Test přidání hráčů"""
    print_test("Přidání 3 hráčů + 1 divák")
    
    game = MariaGame()
    
    # Přidej 3 hráče
    result1 = game.add_player('p1', 'Alice')
    result2 = game.add_player('p2', 'Bob')
    result3 = game.add_player('p3', 'Charlie')
    
    assert result1['success'] and result1['is_player'], "Alice by měla být hráč"
    assert result2['success'] and result2['is_player'], "Bob by měl být hráč"
    assert result3['success'] and result3['is_player'], "Charlie by měl být hráč"
    
    # 4. hráč by měl být divák
    result4 = game.add_player('p4', 'David')
    assert result4['success'] and not result4['is_player'], "David by měl být divák"
    
    print_info(f"Hráči: {len(game.players)}, Diváci: {len(game.spectators)}")
    print_success()


# ========== NOVÁ PRAVIDLA - LICITACE ==========

def test_game_start():
    """Test začátku hry"""
    print_test("Začátek hry a rozdání karet")
    
    game = MariaGame()
    game.add_player('p1', 'Alice')
    game.add_player('p2', 'Bob')
    game.add_player('p3', 'Charlie')
    
    assert game.can_start(), "Hra by měla být připravena začít"
    
    game.start_new_round()
    
    assert game.phase == GamePhase.BIDDING, f"Fáze by měla být BIDDING, je {game.phase}"
    assert len(game.players) == 3, "Měli by být 3 hráči"
    assert all(len(p.hand) == 10 for p in game.players.values()), "Každý hráč by měl mít 10 karet"
    assert len(game.talon) == 2, "Talon by měl mít 2 karty"
    
    print_info(f"Dealer: pozice {game.dealer_position}")
    print_info(f"První hráč: pozice {game.current_player_position}")
    print_success()

def test_bidding_validation():
    """Test validace licitace"""
    print_test("Validace licitace")
    
    game = MariaGame()
    game.add_player('p1', 'Alice')
    game.add_player('p2', 'Bob')
    game.add_player('p3', 'Charlie')
    game.start_new_round()
    
    current = next(pid for pid, p in game.players.items() 
                   if p.position == game.current_player_position)
    
    # Platný příhoz
    result = game.place_bid(current, 105)
    assert result['success'], "Platný příhoz by měl projít"
    assert game.current_bid == 105, "Aktuální příhoz by měl být 105"
    
    # Neplatný příhoz (příliš nízký)
    wrong_player = next(pid for pid, p in game.players.items() 
                       if p.position == game.current_player_position)
    result = game.place_bid(wrong_player, 105)
    assert not result['success'], "Příliš nízký příhoz by neměl projít"
    
    # Neplatný příhoz (ne násobek 5)
    result = game.place_bid(wrong_player, 107)
    assert not result['success'], "Příhoz co není násobek 5 by neměl projít"
    
    print_success()

def test_bidding_complete():
    """Test dokončení licitace"""
    print_test("Dokončení licitace (2 pasy)")
    
    game = MariaGame()
    game.add_player('p1', 'Alice')
    game.add_player('p2', 'Bob')
    game.add_player('p3', 'Charlie')
    game.start_new_round()
    
    players_list = [pid for pid, p in sorted(game.players.items(), 
                                             key=lambda x: x[1].position)]
    
    # První hráč dá příhoz
    game.place_bid(players_list[game.current_player_position], 110)
    
    # Další 2 hráči pasují
    game.pass_bid(players_list[game.current_player_position])
    result = game.pass_bid(players_list[game.current_player_position])
    
    assert result.get('bidding_over'), "Licitace by měla skončit"
    assert game.phase == GamePhase.TRUMP_SELECTION, \
        f"Fáze by měla být TRUMP_SELECTION, je {game.phase}"
    
    print_info(f"Vítěz licitace: {game.bidder_id}")
    print_success()


# ========== NOVÁ PRAVIDLA - TRUMF A TALON ==========

def test_trump_selection():
    """Test výběru trumfu (NOVÉ v2.0)"""
    print_test("Výběr trumfu vítězem licitace")
    
    game = MariaGame()
    game.add_player('p1', 'Alice')
    game.add_player('p2', 'Bob')
    game.add_player('p3', 'Charlie')
    game.start_new_round()
    
    # Simuluj konec licitace
    players_list = [pid for pid, p in sorted(game.players.items(), 
                                             key=lambda x: x[1].position)]
    game.place_bid(players_list[game.current_player_position], 110)
    game.pass_bid(players_list[game.current_player_position])
    game.pass_bid(players_list[game.current_player_position])
    
    bidder = game.bidder_id
    
    # Vítěz vybírá trumf
    result = game.select_trump(bidder, 'hearts')
    assert result['success'], "Výběr trumfu by měl projít"
    assert game.trump_suit == 'hearts', "Trumf by měl být hearts"
    assert game.phase == GamePhase.TALON_EXCHANGE, \
        "Fáze by měla být TALON_EXCHANGE"
    
    # Hráč by měl mít 12 karet (10 + 2 z talonu)
    assert len(game.players[bidder].hand) == 12, \
        f"Vítěz by měl mít 12 karet, má {len(game.players[bidder].hand)}"
    
    print_info(f"Trumf vybrán: {game.trump_suit}")
    print_success()

def test_talon_exchange():
    """Test výměny talonu (OPRAVENO v2.0)"""
    print_test("Výměna talonu - odhoď 2 karty")
    
    game = MariaGame()
    game.add_player('p1', 'Alice')
    game.add_player('p2', 'Bob')
    game.add_player('p3', 'Charlie')
    game.start_new_round()
    
    # Simuluj licitaci a výběr trumfu
    players_list = [pid for pid, p in sorted(game.players.items(), 
                                             key=lambda x: x[1].position)]
    game.place_bid(players_list[game.current_player_position], 110)
    game.pass_bid(players_list[game.current_player_position])
    game.pass_bid(players_list[game.current_player_position])
    game.select_trump(game.bidder_id, 'hearts')
    
    bidder = game.players[game.bidder_id]
    
    # Odhoď 2 karty
    cards_to_discard = [bidder.hand[0].to_dict(), bidder.hand[1].to_dict()]
    result = game.exchange_talon(game.bidder_id, cards_to_discard)
    
    assert result['success'], "Výměna talonu by měla projít"
    assert len(bidder.hand) == 10, f"Po výměně by měl mít 10 karet, má {len(bidder.hand)}"
    assert game.phase == GamePhase.PLAYING, "Fáze by měla být PLAYING"
    assert len(game.talon_cards_discarded) == 2, \
        "Měly by být uloženy 2 odhozené karty (pro body)"
    
    print_info(f"Odhozené karty uloženy pro bodování: {len(game.talon_cards_discarded)}")
    print_success()


# ========== NOVÁ PRAVIDLA - SVATBY ==========

def test_marriage_declaration():
    """Test hlášení svatby (OPRAVENO v2.0)"""
    print_test("Hlášení svatby před zahráním karty")
    
    game = MariaGame()
    game.add_player('p1', 'Alice')
    game.add_player('p2', 'Bob')
    game.add_player('p3', 'Charlie')
    game.start_new_round()
    
    # Nastav testovací ruku s K+Q
    player_id = 'p1'
    game.players[player_id].hand = [
        Card('hearts', 'K'),
        Card('hearts', 'Q'),
        Card('hearts', 'A'),
        Card('spades', '7')
    ]
    
    game.phase = GamePhase.PLAYING
    game.current_player_position = 0
    game.trump_suit = 'hearts'
    
    # Hláška před zahráním karty
    result = game.declare_marriage(player_id, 'hearts')
    assert result['success'], "Hlášení svatby by mělo projít"
    assert result['points'] == 40, "Flék by měl mít 40 bodů"
    assert 'hearts' in game.players[player_id].declared_marriages, \
        "Svatba by měla být zaznamenána"
    
    print_info(f"Svatba hlášena, body: {result['points']}")
    print_success()

def test_marriage_must_play_card():
    """Test že po hlášení svatby musíš zahrát K nebo Q (NOVÉ v2.0)"""
    print_test("Musíš zahrát K/Q po hlášení svatby")
    
    game = MariaGame()
    game.add_player('p1', 'Alice')
    game.add_player('p2', 'Bob')
    game.add_player('p3', 'Charlie')
    game.start_new_round()
    
    player_id = 'p1'
    game.players[player_id].hand = [
        Card('hearts', 'K'),
        Card('hearts', 'Q'),
        Card('hearts', 'A'),
        Card('spades', '7')
    ]
    
    game.phase = GamePhase.PLAYING
    game.current_player_position = 0
    game.trump_suit = 'spades'
    
    # Hláška
    game.declare_marriage(player_id, 'hearts')
    
    # Pokus zahrát jinou kartu
    result = game.play_card(player_id, Card('hearts', 'A').to_dict())
    assert not result['success'], "Nemůžeš zahrát jinou kartu než K/Q z svatby"
    
    # Zahraj správnou kartu
    result = game.play_card(player_id, Card('hearts', 'K').to_dict())
    assert result['success'], "Musí projít zahraní K ze svatby"
    
    print_info("Validace funguje - musíš zahrát K nebo Q")
    print_success()


# ========== NOVÁ PRAVIDLA - HRANÍ KARET ==========

def test_card_play_rules():
    """Test pravidel hraní (OPRAVENO v2.0)"""
    print_test("Pravidla: Přiznat → Flek → Cokoliv")
    
    game = MariaGame()
    game.add_player('p1', 'Alice')
    game.add_player('p2', 'Bob')
    game.add_player('p3', 'Charlie')
    game.start_new_round()
    
    # Nastav testovací situaci
    game.phase = GamePhase.PLAYING
    game.trump_suit = 'spades'
    game.current_player_position = 0
    
    player = game.players['p1']
    player.hand = [
        Card('hearts', '7'),  # Má hearts
        Card('hearts', '8'),
        Card('spades', 'A'),  # Má trumf
        Card('diamonds', '9')
    ]
    
    # První hráč vynesl hearts
    game.current_trick = [('p0', Card('hearts', 'K'))]
    game.lead_suit = 'hearts'
    game.current_player_position = 0
    
    # 1. Musí přiznat barvu pokud ji má
    result = game._is_valid_play(player, Card('diamonds', '9'))
    assert not result, "Nemůže zahrát jinou barvu když má vynesenou"
    
    result = game._is_valid_play(player, Card('hearts', '7'))
    assert result, "Musí moci zahrát vynesenou barvu"
    
    # 2. Pokud nemá barvu, musí fleknout
    player.hand = [
        Card('spades', 'A'),  # Jen trumf
        Card('diamonds', '9')
    ]
    
    result = game._is_valid_play(player, Card('diamonds', '9'))
    assert not result, "Nemůže zahrát jinou když má trumf"
    
    result = game._is_valid_play(player, Card('spades', 'A'))
    assert result, "Musí moci zahrát trumf"
    
    # 3. Pokud nemá ani barvu ani trumf, může hrát cokoliv
    player.hand = [Card('diamonds', '9')]
    
    result = game._is_valid_play(player, Card('diamonds', '9'))
    assert result, "Může zahrát cokoliv když nemá ani barvu ani trumf"
    
    print_info("Všechna pravidla fungují správně")
    print_success()

def test_trick_winner():
    """Test určení vítěze štychu"""
    print_test("Určení vítěze štychu (trumf > barva)")
    
    game = MariaGame()
    game.add_player('p1', 'Alice')
    game.add_player('p2', 'Bob')
    game.add_player('p3', 'Charlie')
    
    game.trump_suit = 'spades'
    
    # Štych: Hearts K, Hearts A, Spades 7
    game.current_trick = [
        ('p1', Card('hearts', 'K')),
        ('p2', Card('hearts', 'A')),
        ('p3', Card('spades', '7'))  # Trumf
    ]
    
    winner = game._determine_trick_winner()
    assert winner == 'p3', "Trumfová sedma by měla vyhrát nad esy"
    
    # Štych bez trumfu
    game.current_trick = [
        ('p1', Card('hearts', 'K')),
        ('p2', Card('hearts', 'A')),
        ('p3', Card('hearts', '10'))
    ]
    
    winner = game._determine_trick_winner()
    assert winner == 'p2', "Eso by mělo vyhrát"
    
    print_success()


# ========== BODOVÁNÍ ==========

def test_talon_points_to_bidder():
    """Test že body z talonu jdou vítězi (OPRAVENO v2.0)"""
    print_test("Body z odhozených karet z talonu → vítěz")
    
    game = MariaGame()
    game.add_player('p1', 'Alice')
    game.add_player('p2', 'Bob')
    game.add_player('p3', 'Charlie')
    game.start_new_round()
    
    # Simuluj celou hru až po talon
    players_list = [pid for pid, p in sorted(game.players.items(), 
                                             key=lambda x: x[1].position)]
    game.place_bid(players_list[game.current_player_position], 110)
    game.pass_bid(players_list[game.current_player_position])
    game.pass_bid(players_list[game.current_player_position])
    game.select_trump(game.bidder_id, 'hearts')
    
    bidder = game.players[game.bidder_id]
    
    # Odhoď 2 cenné karty (Eso + Desítka = 21 bodů)
    ace = Card('hearts', 'A')
    ten = Card('hearts', '10')
    
    # Ujisti se, že má tyto karty
    if ace not in bidder.hand:
        bidder.hand.append(ace)
    if ten not in bidder.hand:
        bidder.hand.append(ten)
    
    cards_to_discard = [ace.to_dict(), ten.to_dict()]
    game.exchange_talon(game.bidder_id, cards_to_discard)
    
    # Zkontroluj že jsou uloženy
    assert len(game.talon_cards_discarded) == 2, "Měly by být uloženy 2 karty"
    talon_points = sum(c.get_value() for c in game.talon_cards_discarded)
    
    print_info(f"Body z odhozených karet: {talon_points}")
    assert talon_points == 21, f"Body by měly být 21, jsou {talon_points}"
    
    print_success()


# ========== SPECIÁLNÍ HRY ==========

def test_betl_game():
    """Test speciální hry Betl (NOVÉ v2.0)"""
    print_test("Betl - nesmí vzít ani jeden štych")
    
    game = MariaGame()
    game.add_player('p1', 'Alice')
    game.add_player('p2', 'Bob')
    game.add_player('p3', 'Charlie')
    game.start_new_round()
    
    # Licituj betl
    players_list = [pid for pid, p in sorted(game.players.items(), 
                                             key=lambda x: x[1].position)]
    result = game.place_bid(players_list[game.current_player_position], 0, 'betl')
    assert result['success'], "Betl příhoz by měl projít"
    
    game.pass_bid(players_list[game.current_player_position])
    game.pass_bid(players_list[game.current_player_position])
    
    # Betl nemá výběr trumfu ani talon
    assert game.phase == GamePhase.PLAYING, \
        "Betl by měl jít rovnou do hraní"
    assert game.trump_suit is None, "Betl nemá trumf"
    
    print_info("Betl správně přeskočil trumf a talon")
    print_success()


# ========== MAIN ==========

def run_all_tests():
    """Spusť všechny testy"""
    print(f"\n{TestColors.BOLD}{'='*60}{TestColors.RESET}")
    print(f"{TestColors.BOLD}🃏 MARIÁŠ v2.0 - KOMPLETNÍ TEST SUITE{TestColors.RESET}")
    print(f"{TestColors.BOLD}{'='*60}{TestColors.RESET}")
    print(f"{TestColors.YELLOW}Testování nových pravidel a oprav{TestColors.RESET}\n")
    
    tests = [
        # Základní testy
        ("Základy", [
            test_card_creation,
            test_card_strength,
            test_deck_creation,
            test_deck_dealing,
            test_game_initialization,
            test_add_players,
        ]),
        
        # Licitace
        ("Licitace", [
            test_game_start,
            test_bidding_validation,
            test_bidding_complete,
        ]),
        
        # NOVÉ - Trumf a Talon
        ("Trumf a Talon (NOVÉ v2.0)", [
            test_trump_selection,
            test_talon_exchange,
            test_talon_points_to_bidder,
        ]),
        
        # OPRAVENÉ - Svatby
        ("Svatby (OPRAVENO v2.0)", [
            test_marriage_declaration,
            test_marriage_must_play_card,
        ]),
        
        # OPRAVENÉ - Hraní karet
        ("Hraní karet (OPRAVENO v2.0)", [
            test_card_play_rules,
            test_trick_winner,
        ]),
        
        # Speciální hry
        ("Speciální hry (NOVÉ v2.0)", [
            test_betl_game,
        ]),
    ]
    
    total_passed = 0
    total_failed = 0
    
    for category, category_tests in tests:
        print(f"\n{TestColors.BOLD}📂 {category}{TestColors.RESET}")
        print("─" * 60)
        
        for test in category_tests:
            try:
                test()
                total_passed += 1
            except AssertionError as e:
                print_error(str(e))
                total_failed += 1
            except Exception as e:
                print_error(f"Neočekávaná chyba: {e}")
                total_failed += 1
    
    # Výsledky
    print(f"\n{TestColors.BOLD}{'='*60}{TestColors.RESET}")
    print(f"{TestColors.BOLD}📊 VÝSLEDKY{TestColors.RESET}")
    print(f"{'='*60}")
    
    success_rate = (total_passed / (total_passed + total_failed) * 100) if (total_passed + total_failed) > 0 else 0
    
    print(f"\n{TestColors.GREEN}✓ Úspěšné: {total_passed}{TestColors.RESET}")
    print(f"{TestColors.RED}✗ Neúspěšné: {total_failed}{TestColors.RESET}")
    print(f"{TestColors.BLUE}📈 Úspěšnost: {success_rate:.1f}%{TestColors.RESET}\n")
    
    print("="*60)
    
    if total_failed == 0:
        print(f"{TestColors.GREEN}{TestColors.BOLD}🎉 VŠECHNY TESTY PROŠLY!{TestColors.RESET}")
        print(f"{TestColors.GREEN}Kód je připraven k použití.{TestColors.RESET}\n")
        return 0
    else:
        print(f"{TestColors.RED}{TestColors.BOLD}⚠️  NĚKTERÉ TESTY SELHALY{TestColors.RESET}")
        print(f"{TestColors.RED}Oprav chyby a spusť testy znovu.{TestColors.RESET}\n")
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())