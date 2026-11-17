"""Trick-play rules: which cards may be played and who wins a trick.

ČSM general rules, obligations in this order:

1. *Ctít barvu* – follow the suit led.
2. *Přebíjet* – with the suit led in hand, play a card higher than the best
   card in the trick so far if you can.  If the trick has already been
   trumped, any card of the suit led will do.
3. *Trumfovat* – without the suit led you must play a trump, and overtrump a
   trump already in the trick if you can.
4. Otherwise any card may be discarded; it cannot win the trick.

In betl and durch there are no trumps; following suit and beating still apply.
An announced seven (trump seven, or the helper seven in dvě sedmy) may only be
played as the last card of its suit in hand.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from .cards import Card, strength


def winning_index(cards: Sequence[Card], trump: str | None, *, plain: bool) -> int:
    """Index of the card currently winning the (possibly incomplete) trick."""
    if not cards:
        raise ValueError("empty trick")
    best = 0
    for index in range(1, len(cards)):
        if _beats(cards[index], cards[best], trump, plain=plain):
            best = index
    return best


def _beats(card: Card, current: Card, trump: str | None, *, plain: bool) -> bool:
    """Does ``card`` (played later) beat ``current`` (the winning card so far)?"""
    if card[0] == current[0]:
        return strength(card, plain=plain) > strength(current, plain=plain)
    return trump is not None and card[0] == trump


def legal_cards(
    hand: Collection[Card],
    trick: Sequence[Card],
    trump: str | None,
    *,
    plain: bool,
    announced_sevens: Collection[Card] = (),
) -> list[Card]:
    """Cards from ``hand`` that may legally be played to ``trick``."""
    cards = list(hand)
    if not cards:
        return []

    if not trick:
        candidates = cards
    else:
        led_suit = trick[0][0]
        best = trick[winning_index(trick, trump, plain=plain)]
        same_suit = [c for c in cards if c[0] == led_suit]
        if same_suit:
            if best[0] == led_suit:
                higher = [c for c in same_suit if strength(c, plain=plain) > strength(best, plain=plain)]
                candidates = higher or same_suit
            else:
                # The trick was trumped: the suit must be followed, not beaten.
                candidates = same_suit
        elif trump is not None and any(c[0] == trump for c in cards):
            trumps = [c for c in cards if c[0] == trump]
            if best[0] == trump:
                higher = [c for c in trumps if strength(c, plain=plain) > strength(best, plain=plain)]
                candidates = higher or trumps
            else:
                candidates = trumps
        else:
            candidates = cards

    return _respect_announced_sevens(candidates, cards, announced_sevens)


def _respect_announced_sevens(
    candidates: list[Card], hand: list[Card], announced_sevens: Collection[Card]
) -> list[Card]:
    """An announced seven must stay in hand as the last card of its suit."""
    if not announced_sevens:
        return candidates
    allowed = []
    for card in candidates:
        if card in announced_sevens and any(c[0] == card[0] and c != card for c in hand):
            continue
        allowed.append(card)
    # A hand made up solely of locked sevens and their suit-mates always keeps a
    # playable card, but never leave the player without a move.
    return allowed or candidates
