import random

import pytest

from marias.cards import (
    card_name_cs,
    collect_deck,
    cut_deck,
    deal_cards,
    full_deck,
    shuffled_deck,
    sort_hand,
    validate_deck,
)
from marias.rules import legal_cards, winning_index

from .helpers import cards


def test_deck_has_32_unique_cards():
    deck = full_deck()
    assert len(deck) == 32 and len(set(deck)) == 32


def test_deal_is_5_5_5_2_5_5_5_starting_with_forhont():
    deck = full_deck()
    hands, talon = deal_cards(deck)
    assert hands[0] == deck[0:5] + deck[17:22]
    assert hands[1] == deck[5:10] + deck[22:27]
    assert hands[2] == deck[10:15] + deck[27:32]
    assert talon == deck[15:17]


def test_invalid_deck_is_rejected():
    with pytest.raises(ValueError):
        validate_deck(full_deck()[:-1])
    with pytest.raises(ValueError):
        deal_cards(["h7"] * 32)


def test_cut_keeps_cyclic_order_and_lifts_at_least_two_cards():
    rng = random.Random(3)
    deck = shuffled_deck(rng)
    for _ in range(200):
        cut = cut_deck(deck, rng)
        position = cut.index(deck[0])
        assert cut[position:] + cut[:position] == deck
        assert 2 <= position <= 30


def test_collect_keeps_piles_intact():
    rng = random.Random(5)
    deck = full_deck()
    piles = [deck[0:9], deck[9:20], [], deck[20:32]]
    collected = collect_deck(piles, rng)
    validate_deck(collected)
    text = " ".join(collected)
    for pile in piles:
        if pile:
            assert " ".join(pile) in text


def test_sorting_puts_ten_below_ace_only_in_trump_games():
    assert sort_hand(cards("hK hX hA h9")) == cards("hA hX hK h9")
    assert sort_hand(cards("hK hX hA h9"), plain=True) == cards("hA hK hX h9")


def test_czech_card_names_agree_in_gender():
    assert card_name_cs("h7") == "červená sedma"
    assert card_name_cs("lK") == "zelený král"
    assert card_name_cs("bA") == "kulové eso"
    assert card_name_cs("aQ") == "žaludový svršek"


# --------------------------------------------------------------------- tricks


def test_trick_winner_highest_of_led_suit():
    assert winning_index(cards("lK lX l9"), "h", plain=False) == 1  # ten beats king
    assert winning_index(cards("lK lX l9"), None, plain=True) == 0  # natural order


def test_trump_beats_led_suit_and_higher_trump_beats_lower():
    assert winning_index(cards("lA h7 lX"), "h", plain=False) == 1
    assert winning_index(cards("lA h7 h8"), "h", plain=False) == 2


def test_off_suit_discard_never_wins():
    assert winning_index(cards("l7 bA aA"), "h", plain=False) == 0
    assert winning_index(cards("l7 bA aA"), None, plain=True) == 0


# ------------------------------------------------------------ legal responses


def legal(hand, trick, trump="h", plain=False, sevens=()):
    return sorted(legal_cards(cards(hand), cards(trick), trump, plain=plain, announced_sevens=sevens))


def test_any_card_may_be_led():
    assert legal("l7 hA b9", "") == sorted(cards("l7 hA b9"))


def test_must_follow_suit():
    assert legal("l7 hA b9", "l8") == ["l7"]


def test_must_beat_when_possible():
    assert legal("l7 lK lA b9", "l9") == ["lA", "lK"]
    assert legal("l7 l8 b9", "l9") == ["l7", "l8"]  # cannot beat: any card of the suit


def test_ten_beats_king_in_trump_games_only():
    assert legal("lX l7", "lK") == ["lX"]
    assert legal("lX l7", "lK", trump=None, plain=True) == ["l7", "lX"]


def test_no_need_to_beat_a_trumped_trick():
    # Leaves led, second hand trumped; third hand holds higher leaves but need not play them.
    assert legal("l7 lA", "l9 h7") == ["l7", "lA"]


def test_void_in_suit_must_trump():
    assert legal("h7 hK b9", "l9") == ["h7", "hK"]


def test_must_overtrump_when_possible():
    assert legal("h7 hK b9", "l9 h9") == ["hK"]
    assert legal("h7 h8 b9", "l9 h9") == ["h7", "h8"]  # cannot overtrump: any trump


def test_trump_led_must_be_beaten():
    assert legal("h7 hK b9", "h9") == ["hK"]


def test_no_suit_no_trump_any_card():
    assert legal("b9 a7", "l9") == ["a7", "b9"]


def test_betl_and_durch_have_no_trumps_but_keep_following_and_beating():
    assert legal("l7 lJ h9", "lX", trump=None, plain=True) == ["lJ"]  # jack beats ten
    assert legal("h9 hA", "lX", trump=None, plain=True) == ["h9", "hA"]


def test_announced_seven_is_played_last_of_its_suit():
    assert legal("h7 h8 b9", "", sevens=("h7",)) == ["b9", "h8"]
    assert legal("h7 h8", "h9", sevens=("h7",)) == ["h8"]
    assert legal("h7 b9", "", sevens=("h7",)) == ["b9", "h7"]  # last trump: may be led
    assert legal("h7 b9", "l9", sevens=("h7",)) == ["h7"]  # forced to trump with it
    assert legal("h7 b7 b8", "", sevens=("h7", "b7")) == ["b8", "h7"]
