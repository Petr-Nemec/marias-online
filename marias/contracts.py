"""Contracts, the bidding ladder and the tariff of licitovaný mariáš (ČSM 2014)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .cards import HEARTS, SUITS


class ContractType(StrEnum):
    SEDMA = "sedma"  # hra a sedma
    STO = "sto"
    STO_SEDMA = "sto_sedma"
    BETL = "betl"
    DURCH = "durch"
    DVE_SEDMY = "dve_sedmy"
    DVE_SEDMY_STO = "dve_sedmy_sto"


class Part(StrEnum):
    """Separately doubled and separately evaluated components of a contract."""

    HRA = "hra"
    SEDMA = "sedma"
    STO = "sto"
    BETL = "betl"
    DURCH = "durch"
    DVE_SEDMY = "dve_sedmy"


CONTRACT_PARTS: dict[ContractType, tuple[Part, ...]] = {
    ContractType.SEDMA: (Part.HRA, Part.SEDMA),
    ContractType.STO: (Part.STO,),
    ContractType.STO_SEDMA: (Part.STO, Part.SEDMA),
    ContractType.BETL: (Part.BETL,),
    ContractType.DURCH: (Part.DURCH,),
    ContractType.DVE_SEDMY: (Part.DVE_SEDMY,),
    ContractType.DVE_SEDMY_STO: (Part.DVE_SEDMY, Part.STO),
}

#: Licitační žebříček: (contract, red trumps) -> step 1..12.
LADDER: dict[tuple[ContractType, bool], int] = {
    (ContractType.SEDMA, False): 1,
    (ContractType.SEDMA, True): 2,
    (ContractType.STO, False): 3,
    (ContractType.STO_SEDMA, False): 4,
    (ContractType.STO, True): 5,
    (ContractType.STO_SEDMA, True): 6,
    (ContractType.BETL, False): 7,
    (ContractType.DURCH, False): 8,
    (ContractType.DVE_SEDMY, False): 9,
    (ContractType.DVE_SEDMY_STO, False): 10,
    (ContractType.DVE_SEDMY, True): 11,
    (ContractType.DVE_SEDMY_STO, True): 12,
}

MIN_LEVEL = 1
MAX_LEVEL = 12

LEVEL_NAMES_CS: dict[int, str] = {
    1: "Sedma",
    2: "Sedma červená",
    3: "Sto",
    4: "Sto a sedma",
    5: "Sto červených",
    6: "Sto a sedma červených",
    7: "Betl",
    8: "Durch",
    9: "Dvě sedmy",
    10: "Dvě sedmy a sto",
    11: "Dvě sedmy, červená trumf",
    12: "Dvě sedmy, červená trumf, a sto",
}

PART_NAMES_CS: dict[Part, str] = {
    Part.HRA: "hra",
    Part.SEDMA: "sedma",
    Part.STO: "sto",
    Part.BETL: "betl",
    Part.DURCH: "durch",
    Part.DVE_SEDMY: "dvě sedmy",
}

#: Accusative forms, used after „flek na …“.
PART_NAMES_ACC_CS: dict[Part, str] = {
    Part.HRA: "hru",
    Part.SEDMA: "sedmu",
    Part.STO: "sto",
    Part.BETL: "betl",
    Part.DURCH: "durch",
    Part.DVE_SEDMY: "dvě sedmy",
}

#: Sazebník – multiples of the base stake (0,20 Kč in competition play).
RATE_UNITS: dict[Part, int] = {
    Part.HRA: 1,
    Part.SEDMA: 2,
    Part.STO: 4,
    Part.BETL: 15,
    Part.DURCH: 30,
    Part.DVE_SEDMY: 40,
}
TICHA_SEDMA_UNITS = 1  # half of the announced sedma
OMYL_UNITS = 6  # doubled game + doubled sedma
LIMIT_UNITS = 500
RAISED_LIMIT_UNITS = 750
MAX_FLEKS = 4  # flek, re, tutti, boty

FLEK_NAMES_CS = ("flek", "re", "tutti", "boty")

NO_TRUMP_TYPES = frozenset({ContractType.BETL, ContractType.DURCH})
TWO_SEVENS_TYPES = frozenset({ContractType.DVE_SEDMY, ContractType.DVE_SEDMY_STO})
#: Contracts in which card points and hlášky matter.
POINT_TYPES = frozenset(
    {
        ContractType.SEDMA,
        ContractType.STO,
        ContractType.STO_SEDMA,
        ContractType.DVE_SEDMY_STO,
    }
)


@dataclass(frozen=True)
class Contract:
    type: ContractType
    trump: str | None = None
    helper: str | None = None

    def __post_init__(self) -> None:
        if self.type in NO_TRUMP_TYPES:
            if self.trump is not None or self.helper is not None:
                raise ValueError("betl and durch have no trump suit")
            return
        if self.trump not in SUITS:
            raise ValueError("a trump suit is required")
        if self.type in TWO_SEVENS_TYPES:
            if self.helper not in SUITS or self.helper == self.trump:
                raise ValueError("dvě sedmy need a helper suit different from trumps")
        elif self.helper is not None:
            raise ValueError("only dvě sedmy have a helper suit")

    @property
    def red(self) -> bool:
        return self.trump == HEARTS

    @property
    def plain(self) -> bool:
        """True for betl and durch (no trumps, natural rank of the ten)."""
        return self.type in NO_TRUMP_TYPES

    @property
    def level(self) -> int:
        return LADDER[(self.type, self.red)]

    @property
    def parts(self) -> tuple[Part, ...]:
        return CONTRACT_PARTS[self.type]

    @property
    def counts_points(self) -> bool:
        return self.type in POINT_TYPES

    @property
    def announced_sevens(self) -> tuple[str, ...]:
        """Cards bound by the rules for an announced seven."""
        if self.type in (ContractType.SEDMA, ContractType.STO_SEDMA):
            return (f"{self.trump}7",)
        if self.type in TWO_SEVENS_TYPES:
            return (f"{self.trump}7", f"{self.helper}7")
        return ()

    @property
    def name_cs(self) -> str:
        return LEVEL_NAMES_CS[self.level]

    def to_dict(self) -> dict[str, object]:
        return {
            "type": self.type.value,
            "trump": self.trump,
            "helper": self.helper,
            "level": self.level,
            "red": self.red,
            "name": self.name_cs,
            "parts": [p.value for p in self.parts],
        }


def ladder_table() -> list[dict[str, object]]:
    """The ladder in a form convenient for clients."""
    return [
        {"level": level, "type": ctype.value, "red": red, "name": LEVEL_NAMES_CS[level]}
        for (ctype, red), level in sorted(LADDER.items(), key=lambda item: item[1])
    ]
