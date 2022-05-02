import copy
import deepdiff
import gspread
import gspread_formatting as gsf
import json
import os
import time
import typing as T

from contextlib import contextmanager
from oauth2client.service_account import ServiceAccountCredentials

from crabada.crabada_web2_client import CrabadaWeb2Client
from utils import logger
from utils.config_types import UserConfig
from utils.email import Email, send_email
from utils.user import get_alias_from_user

INFO = """Crabada Bot Configuration

This is your Crabada Bot Configuration Spreadsheet

To use it, you can make changes to any cell that is highlighted in grey. The units
or choices for various options are showed in the title cell. Verification is very
rudimentary, so any unparsable configurations will just be overwritten by the last
validated config (i.e. the last one that was manually configured).

The bot will updated the config with whatever it's up-to-date config
is.

Disclaimer:

All investments, especially crypto, are highly speculative in nature and involve substantial
risk of loss. We encourage our investors to invest very carefully. We also encourage investors
to get personal advice from your professional investment advisor and to make independent
investigations before acting on information that we publish. We also release all responsibility
for any losses or opportunity costs associated with an incorrect configuration. We do not in any
way whatsoever warrant or guarantee the success of any action you take in reliance on our
statements or recommendations or configurations.
"""

FMT_TITLE = gsf.cellFormat(
    backgroundColor=gsf.color(0.7, 0.77, 0.87),
    textFormat=gsf.textFormat(bold=True, foregroundColor=gsf.color(0, 0, 0.54)),
    horizontalAlignment="LEFT",
)
FMT_FIELDS = gsf.cellFormat(
    backgroundColor=gsf.color(0.7, 0.77, 0.87),
    textFormat=gsf.textFormat(bold=True, foregroundColor=gsf.color(0, 0, 0.54)),
    horizontalAlignment="LEFT",
)
FMT_FIELDS_CENTER = gsf.cellFormat(
    backgroundColor=gsf.color(0.7, 0.77, 0.87),
    textFormat=gsf.textFormat(bold=True, foregroundColor=gsf.color(0, 0, 0.54)),
    horizontalAlignment="CENTER",
)
FMT_VALUES = gsf.cellFormat(
    backgroundColor=gsf.color(0.93, 0.93, 0.93),
    textFormat=gsf.textFormat(bold=False, foregroundColor=gsf.color(0, 0, 0)),
    horizontalAlignment="CENTER",
)
FMT_BLANK = gsf.cellFormat(
    backgroundColor=gsf.color(1, 1, 1),
    textFormat=gsf.textFormat(bold=False, foregroundColor=gsf.color(0, 0, 0)),
    horizontalAlignment="LEFT",
)
FMT_BLANK_CENTER = gsf.cellFormat(
    backgroundColor=gsf.color(1, 1, 1),
    textFormat=gsf.textFormat(bold=False, foregroundColor=gsf.color(0, 0, 0)),
    horizontalAlignment="CENTER",
)


class MineOption:
    MINE = "MINE"
    LOOT = "LOOT"


class Titles:
    MAX_GAS = "Max Gas (gwei)"
    MAX_REINFORCE = "Max Reinforcement (TUS)"
    REINFORCE_ENABLED = "Reinforcing Enabled (True/False)"
    TEAM_IDS = "Team ID"
    CRAB_IDS = "Reinforce Crab ID"
    DYNAMIC_OPTIONS = f"{MineOption.LOOT}/{MineOption.MINE}"


class ParseState:
    SEARCHING = 0
    TEAM_IDS = 1
    CRAB_IDS = 2


INPUT_VERIFY = {
    Titles.MAX_GAS: {
        "row": 4,
        "cast": float,
        "config_key": "max_gas_price_gwei",
    },
    Titles.MAX_REINFORCE: {
        "row": 5,
        "cast": float,
        "config_key": "max_reinforcement_price_tus",
    },
    Titles.REINFORCE_ENABLED: {
        "row": 6,
        "cast": bool,
        "config_key": "should_reinforce",
    },
}


class ConfigManager:
    GSHEETS_SCOPE = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]
    BUFFER_ROWS = 20
    DYNAMIC_ROWS_START = 9
    MAX_TEAMS = 50
    MAX_CRABS = 20
    CONFIG_UPDATE_TIME = 60.0 * 5.0

    def __init__(
        self,
        user: str,
        config: UserConfig,
        send_email_accounts: T.List[Email],
        allow_sheets_config: bool = False,
        dry_run: bool = False,
    ):
        self.config = config
        self.user = user
        self.alias = get_alias_from_user(user)
        self.allow_sheets_config = allow_sheets_config

        self.crabada_w2 = CrabadaWeb2Client()
        self.team_composition = self.crabada_w2.get_team_compositions(self.config["address"])
        self.crab_classes = self.crabada_w2.get_crab_classes(self.config["address"])
        self.send_email_accounts = send_email_accounts

        self.dry_run = dry_run
        self.last_config_update_time = 0.0

        self.backoff = 0.0
        self.google_api_success = False
        self.last_action_allowed_time = 0.0

        this_dir = os.path.dirname(os.path.realpath(__file__))
        creds_dir = os.path.dirname(this_dir)
        credentials = os.path.join(creds_dir, "credentials.json")
        with open(credentials, "r") as infile:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                json.load(infile), scopes=self.GSHEETS_SCOPE
            )
        self.client = gspread.authorize(creds)
        self.sheet = None
        self.sheet_title = f"{self.alias.upper()} Crabada Bot Config"

    def init(self) -> None:
        self._print_out_config()
        self._send_email_config_if_needed()
        self._save_config()
        self._create_sheet_if_needed()

    def check_for_config_updates(self) -> None:
        if self.dry_run or not self.allow_sheets_config:
            return

        now = time.time()

        if now - self.last_config_update_time < self.CONFIG_UPDATE_TIME:
            return

        self.last_config_update_time = now

        logger.print_normal("Checking for gsheet config update")
        updated_config = self.read_sheets_config()

        if updated_config is None:
            logger.print_warn("Incorrect sheet config, writing with current config...")
            self.write_sheets_config()
            self._save_config()
            return

        config_diff = deepdiff.DeepDiff(self.config, updated_config)
        if not config_diff:
            return

        logger.print_ok("Detected updated config, saving changes...")
        self.config = copy.deepcopy(updated_config)
        logger.print_normal(json.dumps(self.config, indent=4))
        logger.print_normal(f"{config_diff}")
        self.write_sheets_config()
        self._save_config()
        self._send_email_config()

    def write_sheets_config(self) -> None:
        rows, cols = self._get_rows_cols()

        if self.sheet is None:
            return

        with self._google_api_action():
            worksheet = self.sheet.get_worksheet(1)
            worksheet.clear()
            gsf.format_cell_ranges(worksheet, [("1:{rows}", FMT_BLANK)])

        if not self.google_api_success:
            logger.print_warn("failed to get and clear worksheet 1")
            return

        logger.print_normal(f"Updating config worksheet")

        self._write_updated_config_worksheet(worksheet, rows, cols)

    def _check_to_see_if_action(self, create_sheet_if_needed: bool=True) -> bool:
        now = time.time()
        if now - self.last_action_allowed_time < self.backoff:
            logger.print_normal(f"Waiting to take action due to config manager backoff")
            return False

        if self.dry_run:
            return False

        if not self.allow_sheets_config:
            return False

        if self.sheet is None and create_sheet_if_needed:
            self._create_sheet_if_needed()
            return False

        self.last_action_allowed_time = now

        return True

    @contextmanager
    def _google_api_action(self) -> T.Iterator[None]:
        self.google_api_success = False
        try:
            yield
            self.backoff = 0
            self.google_api_success = True
        except KeyboardInterrupt:
            raise
        except:
            logger.print_fail(f"failure to google api call")
            self.backoff = self.backoff * 2

    def _get_empty_new_config(self) -> UserConfig:
        new_config = copy.deepcopy(self.config)

        delete_keys = ["mining_teams", "looting_teams", "reinforcing_crabs"]
        delete_keys.extend([v["config_key"] for _, v in INPUT_VERIFY.items()])
        for del_key in delete_keys:
            del new_config[del_key]
            if isinstance(self.config[del_key], dict):
                new_config[del_key] = {}
            if isinstance(self.config[del_key], bool):
                new_config[del_key] = False
            if isinstance(self.config[del_key], int):
                new_config[del_key] = 0
            if isinstance(self.config[del_key], float):
                new_config[del_key] = 0.0
        return new_config

    def read_sheets_config(self) -> T.Optional[UserConfig]:
        if not self._check_to_see_if_action():
            return self.config

        with self._google_api_action():
            worksheet = self.sheet.get_worksheet(1)

        if not self.google_api_success:
            return self.config

        new_config = self._get_empty_new_config()
        rows, cols = self._get_rows_cols()
        chr_end = chr(ord("A") + cols)
        cell_range = f"A1:{chr_end}{rows}"

        with self._google_api_action():
            cell_values = worksheet.get(cell_range)
            self.backoff = 0

        if not self.google_api_success:
            logger.print_warn(f"Failed to get cell values!")
            return self.config

        if len(cell_values) < self.DYNAMIC_ROWS_START:
            return None

        count = {
            "teams": {
                MineOption.MINE: 0,
                MineOption.LOOT: 0,
            },
            "crabs": {
                MineOption.MINE: 0,
                MineOption.LOOT: 0,
            },
        }

        parse_state = ParseState.SEARCHING

        for i in range(len(cell_values)):
            data = cell_values[i]

            if len(data) < 2:
                continue

            if not data[0] or not data[1]:
                logger.print_warn("No data to parse")
                continue

            if Titles.TEAM_IDS in data[0] and Titles.DYNAMIC_OPTIONS in data[1]:
                parse_state = ParseState.TEAM_IDS
                continue

            if Titles.CRAB_IDS in data[0] and Titles.DYNAMIC_OPTIONS in data[1]:
                parse_state = ParseState.CRAB_IDS
                group = 0
                continue

            if parse_state == ParseState.TEAM_IDS:
                try:
                    team_id = int(data[0])
                except:
                    logger.print_fail(
                        f"Failed to convert team id to config setting. Value: {data[0]}"
                    )
                    return None

                if MineOption.MINE in data[1]:
                    count["teams"][MineOption.MINE] += 1
                    new_config["mining_teams"][team_id] = int(count["teams"][MineOption.MINE] / 6)
                elif MineOption.LOOT in data[1]:
                    count["teams"][MineOption.LOOT] += 1
                    new_config["looting_teams"][team_id] = 10
                else:
                    logger.print_warn(f"Team ID did not have valid option: {data[1]}")

            elif parse_state == ParseState.CRAB_IDS:
                try:
                    crab_id = int(data[0])
                except:
                    logger.print_fail(
                        f"Failed to convert crab id to config setting. Value: {data[0]}"
                    )
                    return None

                if MineOption.MINE in data[1]:
                    count["crabs"][MineOption.MINE] += 1
                    if count["crabs"][MineOption.MINE] % 2 == 0:
                        group += 1
                    new_config["reinforcing_crabs"][crab_id] = group
                elif MineOption.LOOT in data[1]:
                    count["crabs"][MineOption.LOOT] += 1
                    new_config["reinforcing_crabs"][crab_id] = 10
                else:
                    logger.print_warn(f"Crab ID did not have valid option: {data[1]}")
            else:
                for label, info in INPUT_VERIFY.items():
                    if label not in data[0]:
                        continue

                    try:
                        new_config[info["config_key"]] = info["cast"](data[1])
                    except:
                        logger.print_fail(
                            f"Failed to convert {label} value to config setting. Value: {data[1]}"
                        )
                        return None
        return new_config

    def _write_updated_config_worksheet(self, worksheet: T.Any, rows: int, cols: int) -> None:
        if not self._check_to_see_if_action():
            return self.config

        with self._google_api_action():
            cell_list = worksheet.range(1, 1, rows, cols)

        if not self.google_api_success:
            logger.print_warn(f"failed to get range")
            return

        logger.print_normal(f"Allocating {rows} rows and {cols} columns")

        def get_full_row(values: T.List[T.Any]) -> T.List[T.Any]:
            row = []
            row.extend(values)
            row.extend([""] * (cols - len(values)))
            return row

        cell_values = get_full_row([f"{self.user.upper()} Bot Configuration"])

        # blank rows
        cell_values.extend(get_full_row([]))
        cell_values.extend(get_full_row([]))

        cell_values.extend(get_full_row([Titles.MAX_GAS, self.config["max_gas_price_gwei"]]))
        cell_values.extend(
            get_full_row([Titles.MAX_REINFORCE, self.config["max_reinforcement_price_tus"]])
        )
        cell_values.extend(
            get_full_row([Titles.REINFORCE_ENABLED, self.config["should_reinforce"]])
        )

        # blank rows
        cell_values.extend(get_full_row([]))
        cell_values.extend(get_full_row([]))

        cell_values.extend(get_full_row(["Team ID", Titles.DYNAMIC_OPTIONS, "Composition"]))

        num_teams = len(self.config["mining_teams"]) + len(self.config["looting_teams"])
        num_crabs = len(self.config["reinforcing_crabs"])

        values = []
        for team, _ in self.config["mining_teams"].items():
            game_type = MineOption.MINE
            composition = self.team_composition.get(team, self._get_team_composition(team))
            cell_values.extend(get_full_row([team, game_type, composition]))

        for team, _ in self.config["looting_teams"].items():
            game_type = MineOption.LOOT
            composition = self.team_composition.get(team, self._get_team_composition(team))
            cell_values.extend(get_full_row([team, game_type, composition]))

        cell_values.extend(get_full_row([]))
        cell_values.extend(get_full_row([]))

        cell_values.extend(get_full_row(["Reinforce Crab ID", Titles.DYNAMIC_OPTIONS, "Class"]))
        for crab, group in self.config["reinforcing_crabs"].items():
            game_type = MineOption.MINE if group < 10 else MineOption.LOOT
            crab_class = self.crab_classes.get(crab, self._get_crab_class(crab))
            cell_values.extend(get_full_row([crab, game_type, crab_class]))

        for _ in range(self.BUFFER_ROWS):
            cell_values.extend(get_full_row([]))

        logger.print_normal(f"Added {len(cell_values)} cells, expecting {len(cell_list)}")
        assert len(cell_values) == len(cell_list), "Cell/value mismatch"

        for i, val in enumerate(cell_values):
            cell_list[i].value = val

        with self._google_api_action():
            worksheet.update_cells(cell_list)

        if not self.google_api_success:
            logger.print_warn("failed to update sheet cells")
            return

        team_ranges = [(f"A{i}:B{i}", FMT_VALUES) for i in range(10, 10 + num_teams)]
        team_ranges.extend([(f"C{i}", FMT_BLANK_CENTER) for i in range(10, 10 + num_teams)])

        reinforce_row = 9 + 3 + num_teams
        crab_ranges = [
            (f"A{i}:B{i}", FMT_VALUES)
            for i in range(reinforce_row + 1, reinforce_row + 1 + num_crabs)
        ]
        crab_ranges.extend([
            (f"C{i}", FMT_BLANK_CENTER)
            for i in range(reinforce_row + 1, reinforce_row + 1 + num_crabs)
        ])

        gsf.set_column_width(worksheet, "A", 250)
        gsf.set_column_width(worksheet, "C", 250)
        gsf.format_cell_ranges(
            worksheet,
            [
                ("A1", FMT_TITLE),
                ("2:3", FMT_BLANK),
                ("A4", FMT_FIELDS),
                ("B4", FMT_VALUES),
                ("A5", FMT_FIELDS),
                ("B5", FMT_VALUES),
                ("A6", FMT_FIELDS),
                ("B6", FMT_VALUES),
                ("7:8", FMT_BLANK),
                ("A9:C9", FMT_FIELDS_CENTER),
                (f"{reinforce_row - 2}:{reinforce_row - 1}", FMT_BLANK),
                (f"A{reinforce_row}:C{reinforce_row}", FMT_FIELDS_CENTER),
            ]
            + team_ranges
            + crab_ranges,
        )

    def _create_sheet_if_needed(self) -> None:
        if not self._check_to_see_if_action(create_sheet_if_needed=False):
            return

        logger.print_normal(f"Searching for spreadsheet: {self.sheet_title}")
        with self._google_api_action():
            sheets = self.client.openall()
            for sheet in sheets:
                if sheet.title == self.sheet_title:
                    self.sheet = self.client.open(self.sheet_title)
                    logger.print_ok_blue_arrow(f"Found sheet: {self.sheet_title}")

        if not self.google_api_success:
            logger.print_warn("failed to open sheet")
            return

        if self.sheet is not None:
            return

        logger.print_normal(f"Creating spreadsheet: {self.sheet_title}\n")

        self.sheet = self.client.create(self.sheet_title)
        self._create_info_worksheet()
        self._create_config_worksheet()
        self._share_sheet()

    def _delete_sheet(self) -> None:
        if not self._check_to_see_if_action():
            return self.config

        with self._google_api_action():
            sheets = self.client.openall()

        if not self.google_api_success:
            return

        for sheet in sheets:
            if sheet.title == self.sheet_title:
                logger.print_warn(f"Deleting spreadsheet: {self.sheet_title}")
                with self._google_api_action():
                    self.client.del_spreadsheet(sheet.id)

    def _share_sheet(self) -> None:
        if not self._check_to_see_if_action():
            return self.config

        logger.print_ok(f"Sharing config with {self.config['email']}...")
        with self._google_api_action():
            self.sheet.share(
                self.config["email"],
                perm_type="user",
                role="writer",
                notify=True,
                email_message="Here is your Crabada Bot Configuration",
            )
            for email in self.send_email_accounts:
                self.sheet.share(
                    email["address"],
                    perm_type="user",
                    role="writer",
                    notify=True,
                    email_message=f"Here is {self.user}'s Crabada Bot Configuration",
                )
        if not self.google_api_success:
            self.sheet = None

    def _get_rows_cols(self) -> T.Tuple[int, int]:
        rows = 1  # title
        rows += 2  # blank lines
        rows += 3  # data
        rows += 2  # blank lines
        rows += 1  # title

        assert self.DYNAMIC_ROWS_START == rows, "row mismatch"

        rows += len(self.config["mining_teams"])
        rows += len(self.config["looting_teams"])
        rows += 2  # blank lines
        rows += 1  # title
        rows += len(self.config["reinforcing_crabs"])
        rows += self.BUFFER_ROWS  # room for expansion

        cols = 4
        return rows, cols

    def _create_config_worksheet(self) -> None:
        if not self._check_to_see_if_action():
            return self.config

        rows, cols = self._get_rows_cols()

        with self._google_api_action():
            worksheet = self.sheet.add_worksheet(
                title=f"{self.user} Config", rows=str(rows), cols=str(cols)
            )
            worksheet.clear()

        if not self.google_api_success:
            self.sheet = None
            return

        logger.print_normal(f"Creating config worksheet")

        self._write_updated_config_worksheet(worksheet, rows, cols)

    def _create_info_worksheet(self) -> None:
        if not self._check_to_see_if_action():
            return self.config

        logger.print_normal(f"Creating info worksheet")

        with self._google_api_action():
            worksheet = self.sheet.get_worksheet(0)
            worksheet.update_title("Info")

        if not self.google_api_success:
            self.sheet = None
            return

        message = INFO.splitlines()
        message_cells = worksheet.range(1, 1, len(message), 1)
        for i, line in enumerate(message):
            message_cells[i].value = line
        worksheet.update_cells(message_cells)

        gsf.format_cell_ranges(worksheet, [("A1:F1", FMT_TITLE), ("A13:F13", FMT_TITLE)])

    def _get_team_composition(self, team: int) -> str:
        self.team_composition = {}
        self.team_composition = self.crabada_w2.get_team_compositions(self.config["address"])
        return self.team_composition.get(team, "UNKNOWN")

    def _get_crab_class(self, crab: int) -> str:
        self.crab_classes = {}
        self.crab_classes = self.crabada_w2.get_crab_classes(self.config["address"])
        return self.crab_classes.get(crab, "UNKNOWN")

    def _get_save_config(self) -> T.Dict[T.Any, T.Any]:
        save_config = copy.deepcopy(self.config)
        return json.loads(json.dumps(save_config))

    def _save_config(self) -> None:
        if self.dry_run:
            return

        config = self._get_save_config()
        log_dir = logger.get_logging_dir()
        config_file = os.path.join(logger.get_logging_dir(), f"{self.user.lower()}_config.json")
        with open(config_file, "w") as outfile:
            json.dump(config, outfile, indent=4)

    def _load_config(self) -> T.Dict[T.Any, T.Any]:
        log_dir = logger.get_logging_dir()
        config_file = os.path.join(logger.get_logging_dir(), f"{self.user.lower()}_config.json")
        try:
            with open(config_file, "r") as infile:
                return json.load(infile)
        except:
            return {}

    def _get_email_config(self) -> str:
        content = ""
        for config_key, value in self._get_save_config().items():
            new_value = value

            if config_key in [
                "crabada_key",
                "address",
                "commission_percent_per_mine",
                "discord_handle",
                "get_sms_updates",
                "get_sms_updates_loots",
                "get_sms_updates_alerts",
                "get_email_updates",
                "sms_number",
                "email",
                "group",
            ]:
                continue

            if isinstance(value, T.List):
                new_value = "\n\t".join([str(v) for v in value])

            if isinstance(value, T.Dict):
                new_value = ""
                for k, v in value.items():
                    new_value += f"{k}: {str(v)}\n"

            if isinstance(value, bool):
                new_value = str(value)

            content += f"{config_key.upper()}:\n{new_value}\n\n"
        return content

    def _did_config_change(self) -> bool:
        current = self._get_save_config()
        old = self._load_config()

        diff = deepdiff.DeepDiff(old, current)
        if diff:
            logger.print_normal(f"{diff}")
            return True
        return False

    def _print_out_config(self) -> None:
        logger.print_bold(f"{self.user} Configuration\n")
        for config_item, value in self.config.items():
            if config_item == "crabada_key":
                continue
            logger.print_normal(f"\t{config_item}: {value}")
        logger.print_normal("")

    def _send_email_config_if_needed(self) -> None:
        if self.dry_run or not self._did_config_change():
            return

        logger.print_warn(f"Config changed for {self.alias}, sending config email...")
        self._send_email_config()

    def _send_email_config(self) -> None:
        if not self.config["get_email_updates"]:
            return

        content = self._get_email_config()

        email_message = f"Hello {self.alias}!\n\n"
        email_message += "Here is your updated bot configuration:\n\n"
        email_message += content

        send_email(
            self.send_email_accounts,
            self.config["email"],
            f"\U0001F980 Crabada Bot Config Change Notification",
            email_message,
        )
