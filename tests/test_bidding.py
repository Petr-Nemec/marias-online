import pytest

from marias.deal import FORHONT, MIDDLE, REAR, Phase, RuleError

from .helpers import deal_with


def test_zadak_opens_against_forhont():
    deal = deal_with()
    assert deal.turn == REAR
    assert deal.options(REAR) == {
        "kind": "bid",
        "role": "ask",
        "min_level": 1,
        "max_level": 12,
        "can_bid": True,
    }
    assert deal.options(FORHONT) is None


def test_everyone_passes_forhont_must_play_at_least_sedma():
    deal = deal_with()
    deal.pass_bid(REAR)
    assert deal.turn == MIDDLE and deal.bid_role == "ask"
    deal.pass_bid(MIDDLE)
    assert deal.phase is Phase.TALON
    assert (deal.declarer, deal.min_level, deal.forced) == (FORHONT, 1, True)
    assert len(deal.hands[FORHONT]) == 12
    assert deal.can_omyl


def test_forhont_holds_and_wins_when_both_others_give_up():
    deal = deal_with()
    deal.bid(REAR, 1)
    assert deal.turn == FORHONT and deal.options(FORHONT) == {"kind": "bid", "role": "answer", "level": 1}
    deal.hold(FORHONT)
    deal.bid(REAR, 3)
    deal.hold(FORHONT)
    deal.pass_bid(REAR)
    # The middle player steps in as the asker and has to go higher than the held step.
    assert deal.turn == MIDDLE and deal.bid_role == "ask"
    with pytest.raises(RuleError) as error:
        deal.bid(MIDDLE, 3)
    assert error.value.code == "bid_too_low"
    deal.pass_bid(MIDDLE)
    assert (deal.declarer, deal.min_level, deal.forced) == (FORHONT, 3, False)
    assert not deal.can_omyl


def test_middle_inherits_priority_when_forhont_gives_up():
    deal = deal_with()
    deal.bid(REAR, 1)
    deal.hold(FORHONT)
    deal.bid(REAR, 3)
    deal.pass_bid(FORHONT)
    # „Ale já ano“ – the middle player only needs to hold the same step.
    assert deal.turn == MIDDLE and deal.bid_role == "answer"
    deal.hold(MIDDLE)
    assert deal.turn == REAR
    deal.bid(REAR, 7)
    deal.pass_bid(MIDDLE)
    assert (deal.declarer, deal.min_level) == (REAR, 7)


def test_middle_holding_wins_when_zadak_stops():
    deal = deal_with()
    deal.bid(REAR, 2)
    deal.pass_bid(FORHONT)
    deal.hold(MIDDLE)
    deal.pass_bid(REAR)
    assert (deal.declarer, deal.min_level) == (MIDDLE, 2)


def test_middle_overbids_forhont_after_zadak_passes():
    deal = deal_with()
    deal.pass_bid(REAR)
    deal.bid(MIDDLE, 1)
    deal.hold(FORHONT)
    deal.bid(MIDDLE, 8)  # steps may be skipped
    deal.pass_bid(FORHONT)
    assert (deal.declarer, deal.min_level) == (MIDDLE, 8)


def test_zadak_wins_when_both_give_up():
    deal = deal_with()
    deal.bid(REAR, 9)
    deal.pass_bid(FORHONT)
    deal.pass_bid(MIDDLE)
    assert (deal.declarer, deal.min_level) == (REAR, 9)
    assert sorted(deal.hands[REAR]) == sorted([*deal.initial_hands[REAR], *deal.talon])


def test_top_step_can_only_be_held_or_passed():
    deal = deal_with()
    deal.bid(REAR, 12)
    deal.hold(FORHONT)
    assert deal.options(REAR)["can_bid"] is False
    with pytest.raises(RuleError):
        deal.bid(REAR, 12)
    deal.pass_bid(REAR)
    deal.pass_bid(MIDDLE)
    assert (deal.declarer, deal.min_level) == (FORHONT, 12)


@pytest.mark.parametrize("level", [0, 13, -1, True, "3", None, 2.0])
def test_invalid_levels_are_rejected(level):
    deal = deal_with()
    with pytest.raises(RuleError):
        deal.bid(REAR, level)
    assert deal.bid_level == 0 and deal.turn == REAR


def test_wrong_player_and_wrong_role_are_rejected():
    deal = deal_with()
    with pytest.raises(RuleError) as error:
        deal.bid(FORHONT, 1)
    assert error.value.code == "not_your_turn"
    with pytest.raises(RuleError):
        deal.hold(REAR)  # the asker cannot „hold“
    deal.bid(REAR, 1)
    with pytest.raises(RuleError):
        deal.bid(FORHONT, 2)  # the holder only answers
    with pytest.raises(RuleError):
        deal.play(FORHONT, deal.hands[FORHONT][0])
