"""Helpers for building deals with known cards and driving them to a given point."""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence

from marias.cards import SUITS, Card, full_deck
from marias.contracts import LADDER, Contract, ContractType, Part
from marias.deal import Deal, Phase


def cards(text: str) -> list[Card]:
    """Parse ``"h7 hA lK"`` into a list of cards."""
    return text.split()


def stack_deck(
    forhont: Iterable[Card] = (),
    middle: Iterable[Card] = (),
    rear: Iterable[Card] = (),
    talon: Iterable[Card] = (),
) -> list[Card]:
    """A deck that deals the given cards to the given places; the rest is filled in."""
    wanted = [list(forhont), list(middle), list(rear)]
    talon = list(talon)
    used = {c for group in (*wanted, talon) for c in group}
    assert len(used) == sum(len(g) for g in (*wanted, talon)), "duplicate cards requested"
    spare = [c for c in full_deck() if c not in used]
    hands = [group + [spare.pop() for _ in range(10 - len(group))] for group in wanted]
    talon = talon + [spare.pop() for _ in range(2 - len(talon))]
    assert not spare
    deck: list[Card] = []
    for hand in hands:
        deck += hand[:5]
    deck += talon
    for hand in hands:
        deck += hand[5:]
    return deck


def deal_with(**places: Iterable[Card]) -> Deal:
    return Deal(stack_deck(**places))


def win_auction(deal: Deal, winner: int, level: int = 1) -> None:
    """Run the auction so that ``winner`` takes the talon at ``level``."""
    if winner == 2:  # zadák bids, both others give up
        deal.bid(2, level)
        deal.pass_bid(0)
        deal.pass_bid(1)
    elif winner == 0:  # forhont holds, the others give up
        deal.bid(2, level)
        deal.hold(0)
        deal.pass_bid(2)
        deal.pass_bid(1)
    else:  # the middle player overbids forhont after zadák's pass
        deal.pass_bid(2)
        deal.bid(1, level)
        deal.pass_bid(0)
    assert deal.phase is Phase.TALON and deal.declarer == winner and deal.min_level == level


def legal_discards(deal: Deal, contract: Contract) -> list[Card]:
    hand = deal.hands[deal.declarer]  # type: ignore[index]
    allowed = [c for c in hand if (contract.plain or c[1] not in "AX") and c not in contract.announced_sevens]
    side = [c for c in allowed if c[0] not in (contract.trump, contract.helper)]
    return (side + [c for c in allowed if c not in side])[:2]


def declare(deal: Deal, contract: Contract, discards: Sequence[Card] | None = None) -> None:
    assert deal.declarer is not None
    deal.declare(deal.declarer, contract, discards or legal_discards(deal, contract))


def approve_all(deal: Deal) -> None:
    """Everybody says „dobrý“ until the doubling is over."""
    while deal.phase is Phase.FLEK:
        assert deal.turn is not None
        deal.flek(deal.turn, [])


def play_out(deal: Deal, rng: random.Random | None = None) -> None:
    """Finish the play with random legal cards."""
    rng = rng or random.Random(0)
    while deal.phase is Phase.PLAY:
        assert deal.turn is not None
        deal.play(deal.turn, rng.choice(deal.legal_plays(deal.turn)))


def random_action(deal: Deal, role: int, rng: random.Random) -> dict:
    """A random action that is *usually* legal – used for fuzzing."""
    options = deal.options(role)
    assert options is not None
    kind = options["kind"]
    if kind == "bid":
        if options["role"] == "answer":
            return {"a": "hold"} if rng.random() < 0.5 else {"a": "pass"}
        if options["can_bid"] and rng.random() < 0.45:
            top = min(12, options["min_level"] + rng.choice([0, 0, 0, 1, 2, 5]))
            return {"a": "bid", "level": rng.randint(options["min_level"], top)}
        return {"a": "pass"}
    if kind == "talon":
        if options["can_omyl"] and rng.random() < 0.1:
            return {"a": "omyl"}
        hand = deal.hands[role]
        choices = [(k, v) for k, v in LADDER.items() if v >= options["min_level"]]
        (ctype, red), _ = rng.choice(choices)
        trump = helper = None
        if ctype not in (ContractType.BETL, ContractType.DURCH):
            suits = ["h"] if red else [s for s in SUITS if s != "h"]
            if ctype in (ContractType.SEDMA, ContractType.STO_SEDMA) and rng.random() < 0.9:
                suits = [s for s in suits if f"{s}7" in hand] or suits  # mostly sensible
            trump = rng.choice(suits)
            if ctype in (ContractType.DVE_SEDMY, ContractType.DVE_SEDMY_STO):
                helper = rng.choice([s for s in SUITS if s != trump])
        return {
            "a": "declare",
            "contract": ctype.value,
            "trump": trump,
            "helper": helper,
            "discard": rng.sample(hand, 2),
        }
    if kind == "flek":
        return {"a": "flek", "parts": [p for p in options["parts"] if rng.random() < 0.4]}
    return {"a": "play", "card": rng.choice(options["cards"]), "announce": rng.random() < 0.9}


__all__ = [
    "Contract",
    "ContractType",
    "Part",
    "approve_all",
    "cards",
    "deal_with",
    "declare",
    "legal_discards",
    "play_out",
    "random_action",
    "stack_deck",
    "win_auction",
]


def play_scripted(deal: Deal, declarer_order: Sequence[Card], rng: random.Random | None = None) -> None:
    """The declarer plays cards in the given order; defenders play random legal cards."""
    rng = rng or random.Random(1)
    order = list(declarer_order)
    while deal.phase is Phase.PLAY:
        player = deal.turn
        assert player is not None
        if player == deal.declarer:
            legal = deal.legal_plays(player)
            card = next(c for c in order if c in legal)
            order.remove(card)
        else:
            card = rng.choice(deal.legal_plays(player))
        deal.play(player, card)


def force_to_forhont(deal: Deal) -> None:
    """Nobody bids: forhont takes the talon and must play."""
    deal.pass_bid(2)
    deal.pass_bid(1)
