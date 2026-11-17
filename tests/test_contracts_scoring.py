import random

import pytest

from marias.contracts import Contract, ContractType, Part
from marias.deal import FORHONT, MIDDLE, REAR, Outcome, Phase, RuleError

from .helpers import (
    approve_all,
    cards,
    deal_with,
    declare,
    force_to_forhont,
    play_out,
    play_scripted,
    win_auction,
)

ALL_ACORNS = cards("aA aX aK aQ aJ a9 a8 a7")


def units(deal, part):
    return next(p.units for p in deal.result.parts if p.part == part)


# ------------------------------------------------------------- declaring


@pytest.fixture
def talon_deal():
    deal = deal_with(forhont=cards("h7 hA hX lK l9 b8 b9 a7 a8 aA"), talon=cards("l7 bX"))
    force_to_forhont(deal)
    return deal


def test_declare_validations(talon_deal):
    deal = talon_deal
    sto = Contract(ContractType.STO, "l")
    sedma = Contract(ContractType.SEDMA, "h")
    with pytest.raises(RuleError, match="Esa a desítky") as e:
        deal.declare(FORHONT, sto, ["hA", "l9"])
    assert e.value.code == "sharp_discard"
    with pytest.raises(RuleError) as e:
        deal.declare(FORHONT, sedma, ["h7", "l9"])
    assert e.value.code == "seven_discard"
    with pytest.raises(RuleError) as e:
        deal.declare(FORHONT, Contract(ContractType.SEDMA, "l"), ["l7", "l9"])
    assert e.value.code == "seven_discard"
    with pytest.raises(RuleError) as e:
        deal.declare(FORHONT, Contract(ContractType.SEDMA, "b"), ["l9", "lK"])
    assert e.value.code == "no_seven"
    for bad in (["l9"], ["l9", "l9"], ["l9", "hJ"], ["l9", "zz"]):
        with pytest.raises(RuleError) as e:
            deal.declare(FORHONT, sto, bad)
        assert e.value.code == "bad_discard"
    assert deal.phase is Phase.TALON and len(deal.hands[FORHONT]) == 12
    # Betl and durch allow aces and tens in the talon.
    deal.declare(FORHONT, Contract(ContractType.BETL), ["hA", "hX"])
    assert deal.phase is Phase.FLEK and len(deal.hands[FORHONT]) == 10


def test_contract_below_the_auction_is_rejected():
    deal = deal_with()
    win_auction(deal, REAR, 7)
    with pytest.raises(RuleError) as e:
        declare(deal, Contract(ContractType.STO_SEDMA, "h"))
    assert e.value.code == "contract_too_low"
    declare(deal, Contract(ContractType.DURCH))  # higher than bid is fine


def test_contract_objects_validate():
    with pytest.raises(ValueError):
        Contract(ContractType.BETL, "h")
    with pytest.raises(ValueError):
        Contract(ContractType.STO)
    with pytest.raises(ValueError):
        Contract(ContractType.DVE_SEDMY, "h", "h")
    with pytest.raises(ValueError):
        Contract(ContractType.STO, "h", "l")
    assert Contract(ContractType.DVE_SEDMY_STO, "h", "a").level == 12
    assert Contract(ContractType.STO, "l").level == 3
    assert Contract(ContractType.STO, "h").level == 5


# -------------------------------------------------------------- doubling


def test_full_doubling_sequence_flek_re_tutti_boty():
    deal = deal_with()
    win_auction(deal, REAR, 3)
    declare(deal, Contract(ContractType.STO, "l"))
    assert deal.turn == FORHONT and deal.options(FORHONT)["name"] == "flek"
    deal.flek(FORHONT, [])
    deal.flek(MIDDLE, [Part.STO])
    assert deal.turn == REAR and deal.options(REAR)["name"] == "re"
    with pytest.raises(RuleError):
        deal.flek(FORHONT, [Part.STO])  # only the declarer answers a flek
    deal.flek(REAR, [Part.STO])
    assert deal.turn == FORHONT and deal.options(FORHONT)["name"] == "tutti"
    deal.flek(FORHONT, [Part.STO])
    deal.flek(MIDDLE, [])
    deal.flek(REAR, [Part.STO])  # boty – the last possible step
    assert deal.phase is Phase.PLAY
    assert deal.flek_counts == {Part.STO: 4}
    assert deal.flekkers == {FORHONT, MIDDLE}


def test_only_the_freshly_doubled_part_can_be_raised():
    deal = deal_with(rear=cards("h7 hA hX hK hQ"))
    win_auction(deal, REAR, 1)
    declare(deal, Contract(ContractType.SEDMA, "h"))
    deal.flek(FORHONT, [Part.SEDMA])
    deal.flek(MIDDLE, [])
    assert deal.options(REAR)["parts"] == ["sedma"]
    with pytest.raises(RuleError):
        deal.flek(REAR, [Part.HRA])
    deal.flek(REAR, [])
    assert deal.phase is Phase.PLAY
    assert deal.flek_counts == {Part.HRA: 0, Part.SEDMA: 1}


def test_bad_flek_input():
    deal = deal_with()
    win_auction(deal, REAR, 3)
    declare(deal, Contract(ContractType.STO, "l"))
    for bad in ([Part.BETL], [Part.STO, Part.STO]):
        with pytest.raises(RuleError):
            deal.flek(FORHONT, bad)


# ------------------------------------------------------------------ sedma


def sedma_deal(red=False):
    trump = "h" if red else "a"
    hand = [f"{trump}{r}" for r in "AXKQJ987"] + ["lA", "bA"]
    deal = deal_with(forhont=hand, talon=cards("l7 b7"))
    force_to_forhont(deal)
    declare(deal, Contract(ContractType.SEDMA, trump), ["l7", "b7"])
    return deal


def test_undoubled_sedma_is_settled_without_play():
    deal = sedma_deal()
    approve_all(deal)
    assert deal.outcome is Outcome.APPROVED and deal.phase is Phase.DONE
    assert units(deal, "hra") == 1 and units(deal, "sedma") == 2
    assert deal.result.units == 3
    assert not deal.tricks


def test_red_sedma_doubles_rates():
    deal = sedma_deal(red=True)
    approve_all(deal)
    assert deal.result.units == 6


def test_flek_on_game_without_re_is_conceded():
    deal = sedma_deal()
    deal.flek(MIDDLE, [Part.HRA])
    deal.flek(REAR, [])
    deal.flek(FORHONT, [])  # declarer says „dobrý“ – no re
    assert deal.outcome is Outcome.APPROVED
    assert units(deal, "hra") == -2 and units(deal, "sedma") == 2
    assert deal.result.units == 0


def test_flek_on_sedma_is_played_out_with_tiche_sto():
    deal = sedma_deal()
    deal.flek(MIDDLE, [Part.SEDMA])
    deal.flek(REAR, [])
    deal.flek(FORHONT, [])
    assert deal.phase is Phase.PLAY and deal.leader == FORHONT
    order = [c for c in deal.hands[FORHONT] if c != "a7"] + ["a7"]
    play_scripted(deal, order)
    assert deal.outcome is Outcome.PLAYED and len(deal.tricks) == 10
    result = deal.result
    # All tricks: 80 card points + 10 for the last trick + trump marriage 40 = 130.
    assert result.declarer_points == 130
    # Tiché sto: doubled game + doubled game for each 10 over 100 → 2 × (1 + 3) = 8.
    assert units(deal, "hra") == 8
    assert units(deal, "sedma") == 4  # one flek
    assert result.units == 12


def test_announced_seven_cannot_be_played_early():
    deal = sedma_deal()
    deal.flek(MIDDLE, [Part.SEDMA])
    deal.flek(REAR, [])
    deal.flek(FORHONT, [])
    with pytest.raises(RuleError) as e:
        deal.play(FORHONT, "a7")
    assert e.value.code == "illegal_card"
    assert "a7" not in deal.legal_plays(FORHONT)


def test_omyl_only_for_plain_sedma():
    deal = deal_with()
    force_to_forhont(deal)
    deal.omyl(FORHONT)
    assert deal.outcome is Outcome.OMYL and deal.result.units == -6
    deal = deal_with()
    win_auction(deal, REAR, 2)
    with pytest.raises(RuleError) as e:
        deal.omyl(REAR)
    assert e.value.code == "omyl_not_allowed"


# -------------------------------------------------------------------- sto


def test_won_red_sto_counts_every_ten_and_ticha_sedma():
    hand = [f"h{r}" for r in "AXKQJ987"] + ["lA", "bA"]
    deal = deal_with(forhont=hand, talon=cards("l7 b7"))
    force_to_forhont(deal)
    declare(deal, Contract(ContractType.STO, "h"), ["l7", "b7"])
    approve_all(deal)
    play_scripted(deal, [c for c in deal.hands[FORHONT] if c != "h7"] + ["h7"])
    result = deal.result
    assert result.declarer_points == 130
    assert units(deal, "sto") == 4 * 2 * 4  # rate × red × (1 + 3 tens over 100)
    assert units(deal, "ticha_sedma") == 2  # half the sedma rate, red
    assert result.units == 34


def test_lost_sto_pays_missing_tens_and_defence_marriages():
    # Declarer (zadák) has nothing; a defender has a marriage to announce.
    deal = deal_with(
        rear=cards("l7 l8 l9 b7 b8 b9 a7 a8 a9 h7"),
        forhont=cards("hA hX hK hQ lA lX bA bX aA aX"),
        talon=cards("h8 h9"),
    )
    win_auction(deal, REAR, 3)
    declare(deal, Contract(ContractType.STO, "l"), ["h8", "h9"])
    approve_all(deal)
    play_out(deal, random.Random(4))
    result = deal.result
    sto = next(p for p in result.parts if p.part == "sto")
    assert not sto.won
    best = max(result.hlasky[REAR], default=0)
    counted = deal.trick_points(REAR) + best
    defence_marriages = sum(v for p in (FORHONT, MIDDLE) for v in result.hlasky[p])
    assert sto.units == -4 * ((100 - counted) // 10 + defence_marriages // 10)


# ------------------------------------------------------------ betl, durch


def test_betl_won_with_lowest_cards():
    low = cards("h7 l7 b7 a7 h8 l8 b8 a8 h9 l9")
    deal = deal_with(rear=low, talon=cards("b9 a9"))
    win_auction(deal, REAR, 7)
    declare(deal, Contract(ContractType.BETL), ["b9", "a9"])
    approve_all(deal)
    assert deal.leader == REAR  # the declarer leads in betl
    play_out(deal, random.Random(2))
    assert deal.result.units == 15 and len(deal.tricks) == 10


def test_durch_ends_with_the_first_lost_trick():
    low = cards("h7 l7 b7 a7 h8 l8 b8 a8 h9 l9")
    deal = deal_with(rear=low, talon=cards("b9 a9"))
    win_auction(deal, REAR, 8)
    declare(deal, Contract(ContractType.DURCH), ["b9", "a9"])
    deal.flek(FORHONT, [Part.DURCH])
    deal.flek(MIDDLE, [])
    deal.flek(REAR, [])
    play_out(deal)
    assert deal.phase is Phase.DONE and len(deal.tricks) == 1
    assert deal.result.units == -60


# -------------------------------------------------------------- dvě sedmy


def test_two_sevens_won():
    deal = deal_with(
        forhont=cards("aA aX aK aQ aJ a9 a7 b7 bA bX"),
        middle=cards("a8 bQ bJ"),
        rear=cards("b9 b8"),
        talon=cards("bK l7"),
    )
    force_to_forhont(deal)
    declare(deal, Contract(ContractType.DVE_SEDMY, "a", "b"), ["bK", "l7"])
    approve_all(deal)
    play_scripted(deal, cards("aA bA bX aX aK aQ aJ a9 b7 a7"))
    assert deal.outcome is Outcome.PLAYED and not deal.two_sevens_failed
    assert units(deal, "dve_sedmy") == 40
    assert deal.result.pb == {FORHONT: 20}  # „na 4 pomocné“ with the lead


def test_two_sevens_against_four_helpers_with_raised_limit():
    deal = deal_with(
        rear=cards("h7 hA hX hK hQ hJ h9 l7 lA lX"),
        forhont=cards("lK lQ lJ l9"),
        talon=cards("h8 l8"),
    )
    win_auction(deal, REAR, 11)
    declare(deal, Contract(ContractType.DVE_SEDMY, "h", "l"), ["h8", "l8"])
    deal.flek(FORHONT, [Part.DVE_SEDMY])
    deal.flek(MIDDLE, [Part.DVE_SEDMY])
    deal.flek(REAR, [Part.DVE_SEDMY])
    deal.flek(FORHONT, [Part.DVE_SEDMY])
    deal.flek(MIDDLE, [])
    deal.flek(REAR, [Part.DVE_SEDMY])
    assert deal.outcome is Outcome.FOUR_HELPERS and not deal.tricks
    assert deal.result.units_raw == -40 * 2 * 16
    assert deal.result.limit == 750 and deal.result.units == -750 and deal.result.limited


def test_limit_is_500_when_only_one_defender_doubled():
    deal = deal_with(
        rear=cards("h7 hA hX hK hQ hJ h9 l7 lA lX"),
        forhont=cards("lK lQ lJ l9"),
        talon=cards("h8 l8"),
    )
    win_auction(deal, REAR, 11)
    declare(deal, Contract(ContractType.DVE_SEDMY, "h", "l"), ["h8", "l8"])
    deal.flek(FORHONT, [Part.DVE_SEDMY])
    deal.flek(MIDDLE, [])
    deal.flek(REAR, [Part.DVE_SEDMY])
    deal.flek(FORHONT, [Part.DVE_SEDMY])
    deal.flek(MIDDLE, [])
    deal.flek(REAR, [Part.DVE_SEDMY])
    assert deal.result.units == -500


def test_missing_seven_loses_two_sevens_without_play():
    deal = deal_with(rear=cards("h7 hA hX hK"), talon=cards("h8 h9"))
    win_auction(deal, REAR, 9)
    declare(deal, Contract(ContractType.DVE_SEDMY, "h", "b"), ["h8", "h9"])
    approve_all(deal)
    if deal.outcome is not Outcome.FOUR_HELPERS:
        assert deal.outcome is Outcome.MISSING_SEVEN
    assert deal.result.units == -80
