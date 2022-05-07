from config import ALIAS_POSTFIX, USERS
from utils import logger

BETA_TEST_LIST = list(USERS.keys())


def get_alias_from_user(user: str) -> str:
    user_split = user.split(ALIAS_POSTFIX[0])

    if not user_split:
        return user

    if not user_split[-1].startswith(ALIAS_POSTFIX[1:]):
        return user

    alias = user_split[0]
    logger.print_normal(f"\tmapping {user} -> {alias}")
    return alias
