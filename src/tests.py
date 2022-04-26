import json
import math
import os

from crabada.miners_revenge import calc_miners_revenge
from crabada.types import CrabForLending
from utils import logger


def test_miners_revenge():
    expected_miners_revenge = 42.25
    this_dir = os.path.dirname(os.path.realpath(__file__))
    mine_file = os.path.join(this_dir, "crabada", "test_mines", "example_mine.json")
    with open(mine_file, "r") as infile:
        mine = json.load(infile)["result"]

    miners_revenge = calc_miners_revenge(mine, is_looting=False, additional_crabs=[], verbose=True)
    assert math.isclose(
        expected_miners_revenge, miners_revenge, abs_tol=0.01
    ), f"Expected: {expected_miners_revenge} Actual: {miners_revenge}"

    miners_revenge = calc_miners_revenge(mine, is_looting=True, additional_crabs=[], verbose=True)
    assert math.isclose(
        expected_miners_revenge, miners_revenge, abs_tol=0.01
    ), f"Expected: {expected_miners_revenge} Actual: {miners_revenge}"

    expected_miners_revenge = 37.15
    mine_file = os.path.join(this_dir, "crabada", "test_mines", "example_mine1.json")
    with open(mine_file, "r") as infile:
        mine = json.load(infile)["result"]

    miners_revenge = calc_miners_revenge(mine, is_looting=False, additional_crabs=[], verbose=True)
    assert math.isclose(
        expected_miners_revenge, miners_revenge, abs_tol=0.01
    ), f"Expected: {expected_miners_revenge} Actual: {miners_revenge}"

    mine_file = os.path.join(this_dir, "crabada", "test_mines", "example_mine2.json")
    with open(mine_file, "r") as infile:
        mine = json.load(infile)["result"]
    additional_crab = [
        CrabForLending(
            {
                "crabada_id": 7985,
                "crabada_class": 3,
                "photo": "7985.png",
                "hp": 113,
                "speed": 29,
                "armor": 27,
                "damage": 58,
                "critical": 42,
                "is_origin": 0,
                "is_genesis": 0,
                "legend_number": 0,
            }
        )
    ]

    miners_revenge = calc_miners_revenge(
        mine, is_looting=False, additional_crabs=additional_crab, verbose=True
    )
    assert math.isclose(
        expected_miners_revenge, miners_revenge, abs_tol=0.01
    ), f"Expected: {expected_miners_revenge} Actual: {miners_revenge}"

    mine_file = os.path.join(this_dir, "crabada", "test_mines", "example_mine3.json")
    with open(mine_file, "r") as infile:
        mine = json.load(infile)["result"]

    additional_crab = [
        CrabForLending(
            {
                "crabada_id": 73896,
                "crabada_class": 4,
                "photo": "73896.png",
                "hp": 148,
                "speed": 27,
                "armor": 35,
                "damage": 54,
                "critical": 39,
                "is_origin": 0,
                "is_genesis": 0,
                "legend_number": 0,
            }
        )
    ]

    miners_revenge = calc_miners_revenge(
        mine, is_looting=True, additional_crabs=additional_crab, verbose=True
    )
    assert math.isclose(
        expected_miners_revenge, miners_revenge, abs_tol=0.01
    ), f"Expected: {expected_miners_revenge} Actual: {miners_revenge}"


if __name__ == "__main__":
    test_miners_revenge()
