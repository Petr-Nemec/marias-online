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
