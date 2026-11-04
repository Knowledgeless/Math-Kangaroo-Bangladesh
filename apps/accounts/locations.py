import json
from functools import lru_cache
from pathlib import Path
from typing import TypedDict


class DistrictLocation(TypedDict):
    name: str
    upazilas: list[str]


class DivisionLocation(TypedDict):
    name: str
    districts: list[DistrictLocation]


@lru_cache(maxsize=1)
def get_bangladesh_locations() -> list[DivisionLocation]:
    location_file = (
        Path(__file__).resolve().parents[2]
        / "static"
        / "data"
        / "bangladesh-locations.json"
    )
    with location_file.open(encoding="utf-8") as file:
        return json.load(file)["divisions"]
