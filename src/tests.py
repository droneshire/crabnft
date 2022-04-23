import json
import os

from crabada.miners_revenge import calc_miners_revenge
from utils import logger


def test_miners_revenge():
    expected_miners_revenge = 42.25
    this_dir = os.path.dirname(os.path.realpath(__file__))
    mine_file = os.path.join(this_dir, "crabada", "example_mine.json")
    with open(mine_file, "r") as infile:
        mine = json.load(infile)["result"]

    miners_revenge = calc_miners_revenge(mine)
    assert (
        expected_miners_revenge == miners_revenge
    ), f"Expected: {expected_miners_revenge} Actual: {miners_revenge}"


if __name__ == "__main__":
    test_miners_revenge()
