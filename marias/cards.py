"""Cards, deck handling and dealing.

A card is a two-character string ``<suit><rank>``:

* suits: ``h`` červené (hearts), ``l`` zelené (leaves), ``b`` kule (bells),
  ``a`` žaludy (acorns)
* ranks: ``7 8 9 X J Q K A`` where ``X`` is the ten, ``J`` the spodek and
  ``Q`` the svršek.

Plain strings keep the engine trivially serialisable and hashable.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence

Card = str

SUITS: tuple[str, ...] = ("h", "l", "b", "a")
RANKS: tuple[str, ...] = ("7", "8", "9", "X", "J", "Q", "K", "A")

HEARTS = "h"

#: Rank order (weakest first) in games with trumps: the ten ranks just below the ace.
ORDER_TRUMP_GAME = "789JQKXA"
#: Rank order (weakest first) in betl and durch: the ten keeps its natural place.
ORDER_PLAIN_GAME = "789XJQKA"

SUIT_NAMES_CS = {"h": "červené", "l": "zelené", "b": "kule", "a": "žaludy"}
RANK_NAMES_CS = {
    "7": "sedma",
    "8": "osma",
    "9": "devítka",
    "X": "desítka",
    "J": "spodek",
    "Q": "svršek",
    "K": "král",
    "A": "eso",
}

DECK_SIZE = 32
HAND_SIZE = 10
TALON_SIZE = 2

_ALL_CARDS: frozenset[Card] = frozenset(s + r for s in SUITS for r in RANKS)


def full_deck() -> list[Card]:
    """Return the 32 cards in a fixed canonical order."""
    return [s + r for s in SUITS for r in RANKS]


def is_card(value: object) -> bool:
    return isinstance(value, str) and value in _ALL_CARDS


def suit_of(card: Card) -> str:
    return card[0]


def rank_of(card: Card) -> str:
    return card[1]


def card_points(card: Card) -> int:
    """Aces and tens are worth 10 points; nothing else scores (ČSM general rules)."""
    return 10 if card[1] in ("A", "X") else 0


def is_sharp(card: Card) -> bool:
    """„Ostrá“ karta – an ace or a ten."""
    return card[1] in ("A", "X")


def strength(card: Card, *, plain: bool) -> int:
    """Strength of a card within its suit for the given kind of game."""
    order = ORDER_PLAIN_GAME if plain else ORDER_TRUMP_GAME
    return order.index(card[1])


def sort_hand(cards: Iterable[Card], *, plain: bool = False) -> list[Card]:
    """Sort by suit, then by descending strength."""
    order = ORDER_PLAIN_GAME if plain else ORDER_TRUMP_GAME
    return sorted(cards, key=lambda c: (SUITS.index(c[0]), -order.index(c[1])))


def card_name_cs(card: Card) -> str:
    """Czech name with the adjective agreeing in gender, e.g. „červená sedma“."""
    rank = RANK_NAMES_CS[card[1]]
    adjective = {"h": "červen", "l": "zelen", "b": "kulov", "a": "žaludov"}[card[0]]
    if card[1] == "A":
        return f"{adjective}é eso"
    if card[1] in ("7", "8", "9", "X"):
        return f"{adjective}á {rank}"
    return f"{adjective}ý {rank}"


def validate_deck(deck: Sequence[Card]) -> None:
    if len(deck) != DECK_SIZE or set(deck) != _ALL_CARDS:
        raise ValueError("deck must contain each of the 32 cards exactly once")


def shuffled_deck(rng: random.Random) -> list[Card]:
    deck = full_deck()
    rng.shuffle(deck)
    return deck


def cut_deck(deck: Sequence[Card], rng: random.Random) -> list[Card]:
    """Cut the deck: at least two cards must be lifted from the top or the bottom."""
    validate_deck(deck)
    position = rng.randint(2, DECK_SIZE - 2)
    return list(deck[position:]) + list(deck[:position])


def collect_deck(piles: Sequence[Sequence[Card]], rng: random.Random) -> list[Card]:
    """Re-assemble the deck after a hand without shuffling.

    Competition rules forbid shuffling: the dealer stacks the players' trick
    piles, unplayed cards and the talon in an order of his choice.  The order of
    the piles is therefore random, the order *inside* each pile is preserved.
    """
    order = [list(p) for p in piles if p]
    rng.shuffle(order)
    deck = [card for pile in order for card in pile]
    validate_deck(deck)
    return deck


def deal_cards(deck: Sequence[Card]) -> tuple[list[list[Card]], list[Card]]:
    """Deal 5-5-5, two cards to the talon, 5-5-5.  Player 0 is forhont."""
    validate_deck(deck)
    hands: list[list[Card]] = [[], [], []]
    position = 0
    for player in range(3):
        hands[player].extend(deck[position : position + 5])
        position += 5
    talon = list(deck[position : position + TALON_SIZE])
    position += TALON_SIZE
    for player in range(3):
        hands[player].extend(deck[position : position + 5])
        position += 5
    return hands, talon
