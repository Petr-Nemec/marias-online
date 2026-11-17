import contextlib
import random

import pytest

from marias import bot
from marias.deal import Phase
from marias.table import (
    BETWEEN_DEALS_SECONDS,
    DISCONNECT_GRACE_SECONDS,
    KICK_REASON,
    LONG_DISCONNECT_REASON,
    TIMEOUTS_BEFORE_KICK,
    Table,
    TableError,
    TableOptions,
)

from .helpers import random_action


def make_table(seats=3, players=None, turn_seconds=60, seed=1):
    options = TableOptions(seats=seats, turn_seconds=turn_seconds)
    table = Table(id="ABCDEFGH", options=options, rng=random.Random(seed))
    players = seats if players is None else players
    for i in range(players):
        table.sit(f"p{i}", f"Hráč {i}", None, 0.0)
    return table


def ready_all(table, now=0.0):
    for seat in table.humans:
        table.set_ready(seat.player_id, now)


def drive(table, rng, now):
    """One random human move by whoever is on turn (bots are driven by tick)."""
    seat = table.seat_on_turn()
    role = table.role_of(seat.index)
    if seat.is_bot:
        table.tick(table.deadline)
        return
    with contextlib.suppress(TableError):  # random moves are sometimes illegal
        table.act(seat.player_id, random_action(table.deal, role, rng), now)


def test_options_are_validated():
    for bad in ({"seats": 5}, {"stake": 7}, {"turn_seconds": 5}, {"dealing": "magic"}):
        with pytest.raises(TableError):
            TableOptions(**bad)


def test_seating_rules():
    table = make_table(players=2)
    with pytest.raises(TableError):
        table.sit("x", "X", 0, 0.0)  # taken
    with pytest.raises(TableError):
        table.sit("x", "X", 7, 0.0)
    table.sit("x", "X", None, 0.0)
    assert table.full
    with pytest.raises(TableError):
        table.sit("y", "Y", None, 0.0)
    assert table.sit("x", "X", None, 0.0).index == 2  # sitting again is idempotent


def test_deal_starts_when_everyone_is_ready_and_rotates_dealer():
    table = make_table()
    table.set_ready("p0", 0.0)
    assert table.status == "waiting"
    ready_all(table)
    assert table.status == "playing" and table.deal_number == 1
    first_dealer = table.dealer
    assert table.role_seats[0] == (first_dealer + 1) % 3
    rng = random.Random(5)
    now = 0.0
    while table.status == "playing":
        now += 1
        drive(table, rng, now)
    assert table.status == "between"
    ready_all(table, now)
    assert table.dealer == (first_dealer + 1) % 3


def test_four_players_dealer_pauses_and_pays_as_defender():
    table = make_table(seats=4)
    ready_all(table)
    dealer = table.dealer
    assert dealer not in table.role_seats and len(set(table.role_seats)) == 3
    rng = random.Random(9)
    now = 0.0
    for _ in range(30):
        while table.status == "playing":
            now += 1
            drive(table, rng, now)
        assert sum(s.money for s in table.seats) == 0
        assert table.history[-1]["money"] == [s.money for s in table.seats]
        ready_all(table, now)


def test_settlement_is_zero_sum_over_many_deals():
    for seats in (3, 4):
        table = make_table(seats=seats, seed=seats)
        rng = random.Random(seats)
        now = 0.0
        ready_all(table)
        before = [0] * seats
        for _ in range(150):
            while table.status == "playing":
                now += 1
                drive(table, rng, now)
            result = table.deal.result
            declarer_seat = table.role_seats[result.declarer]
            for seat in table.seats:
                delta = seat.money - before[seat.index]
                if seat.index == declarer_seat:
                    assert delta == result.units * (seats - 1)
                else:
                    assert delta == -result.units
            before = [s.money for s in table.seats]
            assert sum(before) == 0
            ready_all(table, now)


def test_cut_dealing_reuses_the_cards_without_shuffling():
    table = make_table()
    ready_all(table)
    rng = random.Random(3)
    now = 0.0
    while table.status == "playing":
        now += 1
        drive(table, rng, now)
    collected = table._deck
    ready_all(table, now)
    deck = [c for h in table.deal.initial_hands for c in h] + list(table.deal.talon)
    assert sorted(deck) == sorted(collected)


def test_bots_fill_seats_and_play_by_themselves():
    table = make_table(players=1)
    table.add_bot(1, 0.0)
    table.add_bot(2, 0.0)
    with pytest.raises(TableError):
        table.add_bot(2, 0.0)
    ready_all(table)
    assert table.status == "playing"
    now = 0.0
    for _ in range(2000):
        if table.status != "playing":
            break
        seat = table.seat_on_turn()
        if seat.is_bot:
            now = table.deadline
            assert table.tick(now)
        else:
            role = table.role_of(seat.index)
            table.act(seat.player_id, bot.choose_action(table.deal, role, random.Random(0)), now)
    assert table.status == "between"
    with pytest.raises(TableError):
        table.remove_bot(0, now)
    table.remove_bot(1, now)
    assert table.status == "waiting"


def test_two_missed_turns_remove_the_player():
    table = make_table(turn_seconds=30)
    ready_all(table)
    victim = table.seat_on_turn()
    victim_id = victim.player_id
    now = 0.0
    missed = 0
    for _ in range(200):
        if table.seat_of(victim_id) is None or table.status != "playing":
            break
        seat = table.seat_on_turn()
        now = table.deadline
        if seat is victim:
            table.tick(now)  # the victim lets his clock run out
            missed += 1
        else:
            role = table.role_of(seat.index)
            table.act(seat.player_id, bot.choose_action(table.deal, role, random.Random(0)), now)
    assert missed == TIMEOUTS_BEFORE_KICK
    assert table.seat_of(victim_id) is None
    assert table.departures == [(victim_id, KICK_REASON)]
    if table.status == "playing":
        assert victim.is_bot  # a computer finishes the hand


def test_acting_resets_the_missed_turn_counter():
    table = make_table(turn_seconds=30)
    ready_all(table)
    seat = table.seat_on_turn()
    table.tick(table.deadline)
    assert seat.timeouts == 1
    for _ in range(100):
        on_turn = table.seat_on_turn()
        if on_turn is seat or on_turn is None:
            break
        role = table.role_of(on_turn.index)
        table.act(on_turn.player_id, bot.choose_action(table.deal, role, random.Random(0)), 0.0)
    if table.seat_on_turn() is seat:
        role = table.role_of(seat.index)
        table.act(seat.player_id, bot.choose_action(table.deal, role, random.Random(0)), 0.0)
        assert seat.timeouts == 0


def test_disconnected_player_is_not_counted_as_missing_turns():
    table = make_table(turn_seconds=30)
    ready_all(table)
    seat = table.seat_on_turn()
    table.set_connected(seat.player_id, False, 0.0)
    table.tick(table.deadline)
    assert seat.timeouts == 0 and table.seat_of(seat.player_id) is seat


def test_leaving_mid_deal_hands_the_cards_to_a_bot():
    table = make_table()
    ready_all(table)
    leaver = table.seats[table.role_seats[1]]
    table.leave(leaver.player_id, 0.0)
    assert leaver.is_bot and leaver.player_id is None
    now = 0.0
    rng = random.Random(1)
    while table.status == "playing":
        now += 1
        drive(table, rng, now)
    assert table.status == "between"


def test_disconnected_players_are_freed_after_grace_period():
    table = make_table()
    table.set_connected("p1", False, 10.0)
    assert not table.sweep(10.0 + DISCONNECT_GRACE_SECONDS - 1)
    assert table.sweep(10.0 + DISCONNECT_GRACE_SECONDS + 1)
    assert table.seat_of("p1") is None
    assert table.departures == [("p1", LONG_DISCONNECT_REASON)]


def test_next_deal_starts_automatically_after_pause():
    table = make_table(players=1)
    table.add_bot(1, 0.0)
    table.add_bot(2, 0.0)
    ready_all(table)
    now = 0.0
    while table.status == "playing":
        seat = table.seat_on_turn()
        now = table.deadline or now
        if seat.is_bot:
            table.tick(now)
        else:
            role = table.role_of(seat.index)
            table.act(seat.player_id, bot.choose_action(table.deal, role, random.Random(0)), now)
    assert table.status == "between"
    assert table.tick(now + BETWEEN_DEALS_SECONDS + 1)
    assert table.status == "playing" and table.deal_number == 2


def test_snapshot_hides_other_hands_and_talon():
    table = make_table()
    table.watch("spy", 0.0)
    ready_all(table)
    deal = table.deal
    for player_id in ("p0", "p1", "p2", "spy"):
        snap = table.snapshot(player_id, 0.0)
        view = snap["deal"]
        seat = table.seat_of(player_id)
        if seat is None:
            assert view["hand"] is None
        else:
            assert view["hand"] == deal.hands[table.role_of(seat.index)]
        assert "reveal" not in view
        text = repr(snap)
        for card in deal.talon:
            # A talon card may only appear as part of the viewer's own hand.
            if view["hand"] is None or card not in view["hand"]:
                assert f"'{card}'" not in text.replace(repr(view["hand"]), "")


def test_chat_requires_presence():
    table = make_table()
    with pytest.raises(TableError):
        table.chat("stranger", "X", "ahoj", 0.0)
    table.chat("p0", "Hráč 0", "ahoj", 0.0)
    assert table.log[-1]["text"] == "ahoj" and table.log[-1]["kind"] == "chat"


def test_illegal_human_actions_are_reported():
    table = make_table()
    ready_all(table)
    seat = table.seat_on_turn()
    other = next(s for s in table.seats if s is not seat)
    with pytest.raises(TableError) as e:
        table.act(other.player_id, {"a": "pass"}, 0.0)
    assert e.value.code == "not_your_turn"
    with pytest.raises(TableError):
        table.act(seat.player_id, {"a": "explode"}, 0.0)
    with pytest.raises(TableError):
        table.act("nobody", {"a": "pass"}, 0.0)
    assert table.deal.phase is Phase.BIDDING
