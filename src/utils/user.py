from config import ALIAS_POSTFIX
from utils import logger

BETA_TEST_LIST = [
    "ROSS",
    "TEMPLARE",
    "MASH",
    "MASH2",
    "BIGMOE",
    "ALMUGU",
    "SOOFKAY",
    "KING_WING",
]


def get_alias_from_user(user: str) -> str:
    user_split = user.split(ALIAS_POSTFIX[0])

    if not user_split:
        return user

    if not user_split[-1].startswith(ALIAS_POSTFIX[1:]):
        return user

    alias = user_split[0]
    logger.print_warn(f"mapping {user} -> {alias}")
    return alias
