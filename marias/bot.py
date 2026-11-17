"""A simple computer player.

The bot follows the rules and applies a handful of common-sense heuristics so
that a table can be filled up or an absent player replaced.  It only ever looks
at the information its own seat is entitled to see.  It is not a strong
opponent – it is a stand-in until a human sits down.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Any

from .cards import HEARTS, SUITS, Card, full_deck, is_sharp, strength
from .contracts import LADDER, Contract, ContractType, Part
from .deal import Deal, Phase, RuleError
from .rules import betl_catching_cards, durch_suit_is_solid, winning_index

Action = dict[str, Any]


def choose_action(deal: Deal, player: int, rng: random.Random) -> Action:
    """Pick an action for ``player``, who must be on turn."""
    if deal.turn != player:
        raise ValueError("bot asked to act out of turn")
    if deal.phase is Phase.BIDDING:
        return _bid(deal, player)
    if deal.phase is Phase.TALON:
        return _talon(deal, player)
    if deal.phase is Phase.FLEK:
        return {"a": "flek", "parts": [p.value for p in _flek(deal, player)]}
    if deal.phase is Phase.PLAY:
        return {"a": "play", "card": _play(deal, player, rng), "announce": True}
    raise ValueError("the deal is over")


# --------------------------------------------------------------------- helpers


def _suit(hand: Sequence[Card], suit: str) -> list[Card]:
    return [c for c in hand if c[0] == suit]


def _side_aces(hand: Sequence[Card], trump: str | None) -> int:
    return sum(1 for c in hand if c[1] == "A" and c[0] != trump)


def _unseen(hand: Sequence[Card]) -> list[Card]:
    """Cards the bot cannot see; it has to assume any of them may be against it."""
    return [c for c in full_deck() if c not in hand]


def _betl_holes(hand: Sequence[Card]) -> list[Card]:
    return betl_catching_cards(hand, _unseen(hand))


def _durch_losers(hand: Sequence[Card]) -> list[Card]:
    """Cards in suits where a trick could be lost, weakest first."""
    losers: list[Card] = []
    for suit in SUITS:
        own = _suit(hand, suit)
        if not own:
            continue
        outstanding = [f"{suit}{r}" for r in "789XJQKA" if f"{suit}{r}" not in own]
        if not durch_suit_is_solid(own, outstanding):
            losers.extend(sorted(own, key=lambda c: strength(c, plain=True)))
    return losers


# --------------------------------------------------------------------- bidding


def _viability(hand: Sequence[Card], ctype: ContractType, trump: str | None, helper: str | None) -> float:
    """Rough chance (0-1) of making a contract with the best ten of ``hand``."""
    if ctype is ContractType.BETL:
        holes = len(_betl_holes(hand)) - max(0, len(hand) - 10)
        return {0: 0.9, 1: 0.35, 2: 0.1}.get(max(holes, 0), 0.02)
    if ctype is ContractType.DURCH:
        losers = len(_durch_losers(hand)) - max(0, len(hand) - 10)
        return 0.9 if losers <= 0 else 0.02

    assert trump is not None
    trumps = _suit(hand, trump)
    count = len(trumps)
    has_seven = f"{trump}7" in trumps
    has_ace = f"{trump}A" in trumps
    aces = _side_aces(hand, trump)

    sedma = 0.0
    if has_seven:
        sedma = {0: 0.0, 1: 0.0, 2: 0.03, 3: 0.12, 4: 0.4, 5: 0.7}.get(count, 0.9)
        if count == 4 and has_ace and aces >= 1:
            sedma += 0.12

    marriages = [s for s in SUITS if f"{s}K" in hand and f"{s}Q" in hand]
    sto = 0.03
    if marriages and count >= 5:
        sto = 0.3
        if trump in marriages and has_ace and aces >= 1:
            sto = 0.6 if count == 5 else 0.75

    if ctype is ContractType.SEDMA:
        return sedma
    if ctype is ContractType.STO:
        return sto
    if ctype is ContractType.STO_SEDMA:
        return min(sto, sedma) * 0.9

    assert helper is not None
    helpers = _suit(hand, helper)
    two_sevens = 0.01
    if has_seven and f"{helper}7" in helpers:
        total = count + len(helpers)
        if count >= 5 and len(helpers) >= 4:
            two_sevens = 0.6 if total >= 10 else 0.3
    if ctype is ContractType.DVE_SEDMY:
        return two_sevens
    return min(two_sevens, sto) * 0.8


def _candidates(hand: Sequence[Card], min_level: int) -> list[tuple[float, Contract]]:
    """Every contract that may legally be announced, with its estimated viability."""
    found: list[tuple[float, Contract]] = []
    for (ctype, red), level in LADDER.items():
        if level < min_level:
            continue
        if ctype in (ContractType.BETL, ContractType.DURCH):
            found.append((_viability(hand, ctype, None, None), Contract(ctype)))
            continue
        trumps = [HEARTS] if red else [s for s in SUITS if s != HEARTS]
        for trump in trumps:
            if ctype in (ContractType.SEDMA, ContractType.STO_SEDMA) and f"{trump}7" not in hand:
                continue
            if ctype in (ContractType.DVE_SEDMY, ContractType.DVE_SEDMY_STO):
                for helper in SUITS:
                    if helper != trump:
                        contract = Contract(ctype, trump, helper)
                        found.append((_viability(hand, ctype, trump, helper), contract))
            else:
                found.append((_viability(hand, ctype, trump, None), Contract(ctype, trump)))
    return found


def _best_contract(hand: Sequence[Card], min_level: int) -> tuple[float, Contract]:
    candidates = _candidates(hand, min_level)
    good = [c for c in candidates if c[0] >= 0.5]
    pool = good or candidates
    # Among good options prefer the cheapest; otherwise the most promising one.
    if good:
        return min(pool, key=lambda c: (c[1].level, -c[0]))
    return max(pool, key=lambda c: (c[0], -c[1].level))


def _max_level(hand: Sequence[Card]) -> int:
    """The highest step of the ladder the bot is prepared to hold."""
    levels = [c.level for v, c in _candidates(hand, 1) if v >= 0.5]
    return max(levels, default=0)


def _bid(deal: Deal, player: int) -> Action:
    willing = _max_level(deal.hands[player])
    if deal.bid_role == "answer":
        return {"a": "hold"} if willing >= deal.bid_level else {"a": "pass"}
    wanted = deal.bid_level + 1
    if willing >= wanted:
        return {"a": "bid", "level": wanted}
    return {"a": "pass"}


# ----------------------------------------------------------------------- talon


def _talon(deal: Deal, player: int) -> Action:
    hand = deal.hands[player]
    viability, contract = _best_contract(hand, deal.min_level)
    if deal.can_omyl and viability < 0.2:
        return {"a": "omyl"}
    return {
        "a": "declare",
        "contract": contract.type.value,
        "trump": contract.trump,
        "helper": contract.helper,
        "discard": _discards(hand, contract),
    }


def _discards(hand: Sequence[Card], contract: Contract) -> list[Card]:
    if contract.type is ContractType.BETL:
        holes = sorted(_betl_holes(hand), key=lambda c: -strength(c, plain=True))
        rest = sorted(
            (c for c in hand if c not in holes),
            key=lambda c: (len(_suit(hand, c[0])), -strength(c, plain=True)),
        )
        return (holes + rest)[:2]
    if contract.type is ContractType.DURCH:
        losers = _durch_losers(hand)
        rest = sorted((c for c in hand if c not in losers), key=lambda c: strength(c, plain=True))
        return (losers + rest)[:2]

    marriages = {s for s in SUITS if f"{s}K" in hand and f"{s}Q" in hand}
    keep_marriages = contract.counts_points

    def cost(card: Card) -> tuple[int, int, int, int]:
        long_suit = card[0] in (contract.trump, contract.helper)
        breaks = keep_marriages and card[0] in marriages and card[1] in ("K", "Q")
        return (int(long_suit), int(breaks), len(_suit(hand, card[0])), strength(card, plain=False))

    allowed = [c for c in hand if not is_sharp(c) and c not in contract.announced_sevens]
    return sorted(allowed, key=cost)[:2]


# ------------------------------------------------------------------------ flek


def _flek(deal: Deal, player: int) -> list[Part]:
    assert deal.contract is not None
    contract = deal.contract
    hand = deal.hands[player]
    trumps = _suit(hand, contract.trump) if contract.trump else []
    sharps = sum(1 for c in hand if is_sharp(c))
    chosen: list[Part] = []

    if player == deal.declarer:
        if deal.flek_stage == 2 and Part.HRA in deal.flek_available and sharps >= 5 and len(trumps) >= 5:
            chosen.append(Part.HRA)
        return chosen
    if deal.flek_stage != 1:
        return chosen

    for part in deal.flek_available:
        strong_sedma = len(trumps) >= 4 or (len(trumps) == 3 and sharps >= 4)
        if (part is Part.SEDMA and strong_sedma) or (part is Part.HRA and sharps >= 5):
            chosen.append(part)
        elif part is Part.STO:
            marriage = f"{contract.trump}K" in hand and f"{contract.trump}Q" in hand
            if marriage or (len(trumps) >= 4 and sharps >= 3):
                chosen.append(part)
        elif part is Part.DVE_SEDMY:
            helpers = _suit(hand, contract.helper) if contract.helper else []
            if len(helpers) >= 4 or len(trumps) >= 4:
                chosen.append(part)
    return chosen


# ------------------------------------------------------------------------ play


def _play(deal: Deal, player: int, rng: random.Random) -> Card:
    assert deal.contract is not None and deal.declarer is not None and deal.leader is not None
    legal = deal.legal_plays(player)
    if len(legal) == 1:
        return legal[0]
    contract = deal.contract
    plain = contract.plain
    trick = deal.trick
    is_declarer = player == deal.declarer

    def power(card: Card) -> int:
        return strength(card, plain=plain)

    def wins(card: Card) -> bool:
        return winning_index([*trick, card], contract.trump, plain=plain) == len(trick)

    lowest = min(legal, key=lambda c: (is_sharp(c) and not plain, c[0] == contract.trump, power(c)))

    if contract.type is ContractType.BETL:
        if is_declarer:
            # Stay below the trick whenever possible, shedding the highest safe card.
            safe = [c for c in legal if trick and not wins(c)]
            if safe:
                return max(safe, key=power)
            return min(legal, key=power)
        # Defenders lead and follow low to force the declarer to win.
        return min(legal, key=power)

    if contract.type is ContractType.DURCH:
        if is_declarer:
            return max(legal, key=power)
        winners = [c for c in legal if trick and wins(c)]
        if winners:
            return min(winners, key=power)
        # Throw away from the suit with the weakest top card, keep possible stoppers.
        return min(legal, key=lambda c: (max(power(x) for x in _suit(deal.hands[player], c[0])), power(c)))

    trump = contract.trump
    if not trick:
        side_aces = [c for c in legal if c[1] == "A" and c[0] != trump]
        trumps = sorted((c for c in legal if c[0] == trump), key=power, reverse=True)
        if is_declarer:
            if trumps and trumps[0][1] == "A":
                return trumps[0]
            if side_aces:
                return rng.choice(side_aces)
            if len(trumps) >= 3:
                return trumps[0]
            return lowest
        if side_aces:
            return rng.choice(side_aces)
        return lowest

    current = winning_index(trick, trump, plain=False)
    current_player = (deal.leader + current) % 3
    played_already = {(deal.leader + i) % 3 for i in range(len(trick))}
    partner_winning = not is_declarer and current_player != deal.declarer
    winners = [c for c in legal if wins(c)]

    if partner_winning and (deal.declarer in played_already):
        # „Mazat“: give the partner points when the trick is safe.
        sharp = [c for c in legal if is_sharp(c) and c[0] != trump]
        if sharp:
            return min(sharp, key=power)  # the ten before the ace
    if winners and not (partner_winning and len(trick) == 2):
        last_to_play = len(trick) == 2
        if last_to_play:
            return max(winners, key=lambda c: (is_sharp(c), -power(c)))
        top = max(winners, key=power)
        return top if top[1] == "A" else min(winners, key=power)
    return lowest


def fallback_action(deal: Deal, player: int) -> Action:
    """A move that is always legal, used if the regular choice is ever rejected."""
    if deal.phase is Phase.BIDDING:
        return {"a": "pass"}
    if deal.phase is Phase.FLEK:
        return {"a": "flek", "parts": []}
    if deal.phase is Phase.PLAY:
        return {"a": "play", "card": deal.legal_plays(player)[0], "announce": True}
    hand = deal.hands[player]
    for _viability, contract in sorted(_candidates(hand, deal.min_level), key=lambda c: c[1].level):
        for first in range(len(hand)):
            for second in range(first + 1, len(hand)):
                discard = [hand[first], hand[second]]
                try:
                    deal.check_declaration(player, contract, discard)
                except RuleError:
                    continue
                return {
                    "a": "declare",
                    "contract": contract.type.value,
                    "trump": contract.trump,
                    "helper": contract.helper,
                    "discard": discard,
                }
    raise RuntimeError("no legal declaration exists")  # pragma: no cover - rules guarantee one
