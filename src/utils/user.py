from config_admin import ALIAS_POSTFIX
from utils import logger


def get_alias_from_user(user: str, verbose: bool = False) -> str:
    user_split = user.split(ALIAS_POSTFIX[0])

    if not user_split:
        return user

    if not user_split[-1].startswith(ALIAS_POSTFIX[1:]):
        return user

    alias = user_split[0]
    if verbose:
        logger.print_normal(f"\tmapping {user} -> {alias}")
    return alias


def clean_up_stats_for_user(log_dir: str, user: str) -> None:
    alias = get_alias_from_user(user)

    files_to_delete = []

    if alias == user:
        game_stats_file = logger.get_lifetime_game_stats(log_dir, alias.lower())
        files_to_delete.append(game_stats_file)

        game_stats_csv = game_stats_file.split(".")[0] + ".csv"
        files_to_delete.append(game_stats_csv)

    files_to_delete.append(get_config_file(log_dir, user))

    for user_file in files_to_delete:
        if not os.path.isfile(user_file):
            continue
        logger.print_warn(f"Removing inactive file: {user_file}...")
        os.remove(user_file)
