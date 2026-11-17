"""Randomised whole-deal runs: every state reached must keep the game invariants."""

import contextlib
import random

import pytest

from marias import bot
from marias.cards import shuffled_deck
from marias.contracts import Contract, ContractType, Part
from marias.deal import Deal, Outcome, Phase, RuleError

from .helpers import random_action


def apply(deal: Deal, player: int, action: dict) -> None:
    kind = action["a"]
    if kind == "bid":
        deal.bid(player, action["level"])
    elif kind == "hold":
        deal.hold(player)
    elif kind == "pass":
        deal.pass_bid(player)
    elif kind == "omyl":
        deal.omyl(player)
    elif kind == "declare":
        contract = Contract(ContractType(action["contract"]), action["trump"], action["helper"])
        deal.declare(player, contract, action["discard"])
    elif kind == "flek":
        deal.flek(player, [Part(p) for p in action["parts"]])
    else:
        deal.play(player, action["card"], announce=action.get("announce", True))


def snapshot(deal: Deal) -> tuple:
    return (deal.phase, deal.turn, [list(h) for h in deal.hands], list(deal.trick), len(deal.events))


def check_invariants(deal: Deal) -> None:
    located = [c for h in deal.hands for c in h] + [c for t in deal.tricks for c in t.cards]
    located += deal.trick + list(deal.discards)
    if deal.declarer is None:
        located += list(deal.talon)
    assert sorted(located) == sorted(set(located)) and len(located) == 32
    if deal.phase is Phase.PLAY:
        sizes = [len(h) for h in deal.hands]
        assert max(sizes) - min(sizes) <= 1
        assert deal.legal_plays(deal.turn)


@pytest.mark.parametrize("policy", ["random", "bot"])
def test_thousands_of_deals(policy):
    rng = random.Random(2026)
    outcomes = set()
    for _ in range(2500):
        deal = Deal(shuffled_deck(rng))
        for _step in range(300):
            if deal.phase is Phase.DONE:
                break
            player = deal.turn
            if policy == "bot":
                action = bot.choose_action(deal, player, rng)
            else:
                action = random_action(deal, player, rng)
            # Random actions are not always legal; a rejected one must change nothing.
            with contextlib.suppress(RuleError):
                apply(deal, player, action)
            check_invariants(deal)
        assert deal.phase is Phase.DONE
        result = deal.result
        assert abs(result.units) <= result.limit
        assert result.units == max(-result.limit, min(result.limit, sum(p.units for p in result.parts)))
        if deal.outcome is Outcome.PLAYED and deal.contract.counts_points and len(deal.tricks) == 10:
            assert sum(deal.trick_points(p) for p in range(3)) == 90
        outcomes.add(deal.outcome)
        # The view must always be JSON-friendly for every seat.
        for seat in (0, 1, 2, None):
            deal.view(seat)
    assert Outcome.PLAYED in outcomes


def test_rejected_actions_leave_the_state_unchanged():
    rng = random.Random(11)
    for _ in range(300):
        deal = Deal(shuffled_deck(rng))
        while deal.phase is not Phase.DONE:
            player = deal.turn
            action = random_action(deal, player, rng)
            before = snapshot(deal)
            try:
                apply(deal, player, action)
            except RuleError:
                assert snapshot(deal) == before
