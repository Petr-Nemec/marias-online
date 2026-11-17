from marias.premium import _combine
from marias.rules import betl_catching_cards, durch_suit_is_solid

from .helpers import cards


def test_without_lead_only_the_best_criterion_uses_the_higher_value():
    criteria = [("a", 10, 12), ("b", 18, 24), ("c", 8, 8)]
    assert _combine(criteria, with_lead=True) == [("a", 10), ("b", 18), ("c", 8)]
    assert _combine(criteria, with_lead=False) == [("a", 10), ("b (bez výnosu)", 24), ("c", 8)]
    assert _combine([], with_lead=False) == []


def test_betl_catching_cards():
    # A card is catching when the defence holds a lower card of its suit.
    assert betl_catching_cards(cards("h7 h8 h9"), cards("hX hA")) == []
    assert betl_catching_cards(cards("h7 hA"), cards("h8")) == ["hA"]
    assert betl_catching_cards(cards("h8"), cards("h7")) == ["h8"]
    # Must-beat: the defence leads h8 and the declarer has to go over it with h9.
    assert betl_catching_cards(cards("h7 h9"), cards("h8")) == ["h9"]
    assert betl_catching_cards(cards("h7 hA"), []) == []  # nothing outstanding
    assert betl_catching_cards(cards("hA"), cards("l7")) == []


def test_durch_solid_suits():
    assert durch_suit_is_solid(cards("hA hK hQ"), cards("h7 h8 h9 hX hJ"))
    assert not durch_suit_is_solid(cards("hA hQ"), cards("hK h7"))
    assert durch_suit_is_solid(cards("hA hQ"), cards("hK"))  # a single king falls under the ace
    assert durch_suit_is_solid(cards("hA"), [])


# --------------------------------------------------- discarding never gains PB

from marias.contracts import Contract, ContractType  # noqa: E402
from marias.deal import MIDDLE, REAR, Outcome  # noqa: E402

from .helpers import approve_all, deal_with, play_scripted, win_auction  # noqa: E402


def test_betl_ace_discarded_earns_nothing():
    # The catching ace goes to the talon: the betl is easier, and no PB for it.
    deal = deal_with(
        rear=cards("h7 h8 h9 l7 l8 l9 b7 b8 a7 a8"),
        middle=cards("hX"),
        talon=cards("hA b9"),
    )
    win_auction(deal, REAR, 7)
    deal.declare(REAR, Contract(ContractType.BETL), ["hA", "b9"])
    approve_all(deal)
    assert deal.result.units == 15
    assert deal.result.pb == {}


def test_durch_weakened_by_a_discard_earns_nothing():
    # With hK the hearts are solid; discarding hK makes them unsafe, which must not pay.
    deal = deal_with(
        middle=cards("hA hQ lA lK lQ lJ lX l9 l8 l7"),
        forhont=cards("hJ"),
        rear=cards("h7 h8 h9 hX"),
        talon=cards("hK aA"),
    )
    win_auction(deal, MIDDLE, 8)
    deal.declare(MIDDLE, Contract(ContractType.DURCH), ["hK", "aA"])
    approve_all(deal)
    if deal.outcome is not Outcome.LAID_DOWN:
        play_scripted(deal, cards("hA hQ lA lK lQ lJ lX l9 l8 l7"))
    assert deal.result.units == 30
    assert deal.result.pb == {}
