import copy
import deepdiff
import gspread
import gspread_formatting as gsf
import json
import os
import typing as T

from oauth2client.service_account import ServiceAccountCredentials

from utils import logger
from utils.config_types import UserConfig
from utils.email import Email, send_email
from utils.user import get_alias_from_user

INFO = """Crabada Bot Configuration

This is your Crabada Bot Configuration Spreadsheet

To use it, you can make changes to any cell that is highlighted in yellow. The units
or choices for various options are showed in the title cell. Verification is very
rudimentary, so any unparsable configurations will just be overwritten by the default
config (i.e. the last one that was manually configured).

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

    def __init__(
        self,
        user: str,
        config: UserConfig,
        send_email_accounts: T.List[Email],
        dry_run: bool = False,
    ):
        self.config = config
        self.user = user
        self.alias = get_alias_from_user(user)

        self.send_email_accounts = send_email_accounts

        self.dry_run = dry_run

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

    def check_for_updated_config(self) -> UserConfig:
        worksheet = self.sheet.get_worksheet(1)
        new_config = copy.deepcopy(self.config)

        for label, info in INPUT_VERIFY.items():
            data = worksheet.row_values(info["row"])
            if len(data) < 2:
                logger.print_warn(f"parsing config, row too short!")
                continue

            if label in data[0]:
                try:
                    new_config[info["config_key"]] = info["cast"](data[1])
                except:
                    logger.print_fail(
                        f"Failed to convert {label} value to config setting. Value: {data[1]}"
                    )
                    return self.config

        row = self.DYNAMIC_ROWS_START
        try:
            data = worksheet.row_values(row)
            print(data)
        except:
            logger.print_fail(f"Failed to read team id row")
            return self.config

        if Titles.TEAM_IDS not in data[0] or Titles.DYNAMIC_OPTIONS not in data[1]:
            logger.print_fail(
                f"Sheet formatting is majorly incorrect, abandoning any attempt to parse"
            )
            return self.config

        team_count = {
            MineOption.MINE: 0,
            MineOption.LOOT: 0,
        }

        row += 1
        for row in range(row, row + self.MAX_TEAMS):
            try:
                data = worksheet.row_values(row)
                print(data)
            except:
                break

            if len(data) < 2:
                continue

            if Titles.CRAB_IDS in data[0]:
                break

            try:
                team_id = int(data[0])
            except:
                logger.print_fail(
                    f"Failed to convert team id value to config setting. Value: {data[0]}"
                )
                continue

            if MineOption.MINE in data[1]:
                team_count[MineOption.MINE] += 1
                new_config["mining_teams"][team_id] = int(team_count[MineOption.MINE] / 7)
            elif MineOption.LOOT in data[1]:
                team_count[MineOption.LOOT] += 1
                new_config["looting_teams"][team_id] = 10
            else:
                logger.print_warn(f"Team ID did not have valid option: {data[1]}")

        try:
            data = worksheet.row_values(row)
        except:
            logger.print_fail(f"Failed to read crab id row")
            return self.config

        if Titles.CRAB_IDS not in data[0] or Titles.DYNAMIC_OPTIONS not in data[1]:
            logger.print_fail(
                f"Sheet formatting is majorly incorrect, abandoning any attempt to parse"
            )
            return self.config

        crab_count = {
            MineOption.MINE: 0,
            MineOption.LOOT: 0,
        }
        group = 0

        row += 1
        for row in range(row, row + self.MAX_CRABS):
            try:
                data = worksheet.row_values(row)
                print(data)
            except:
                break

            if len(data) < 2:
                continue

            if not data[0] or not data[1]:
                logger.print_warn("No data to parse")
                break

            try:
                crab_id = int(data[0])
            except:
                logger.print_fail(
                    f"Failed to convert crab id value to config setting. Value: {data[0]}"
                )
                continue

            if MineOption.MINE in data[1]:
                crab_count[MineOption.MINE] += 1
                if crab_count[MineOption.MINE] % 2 == 0:
                    group += 1
                new_config["reinforcing_crabs"][crab_id] = group
            elif MineOption.LOOT in data[1]:
                crab_count[MineOption.LOOT] += 1
                new_config["looting_teams"][crab_id] = 10
            else:
                logger.print_warn(f"Crab ID did not have valid option: {data[1]}")

        logger.print_normal(json.dumps(new_config, indent=4))
        return new_config

    def _write_updated_config_worksheet(self, worksheet: T.Any, rows: int, cols: int) -> None:
        cell_list = worksheet.range(1, 1, rows, cols)
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

        cell_values.extend(get_full_row(["Team ID", Titles.DYNAMIC_OPTIONS]))

        num_teams = len(self.config["mining_teams"]) + len(self.config["looting_teams"])
        num_crabs = len(self.config["reinforcing_crabs"])

        values = []
        for team, _ in self.config["mining_teams"].items():
            game_type = MineOption.MINE
            cell_values.extend(get_full_row([team, game_type]))

        for team, _ in self.config["looting_teams"].items():
            game_type = MineOption.LOOT
            cell_values.extend(get_full_row([team, game_type]))

        cell_values.extend(get_full_row([]))
        cell_values.extend(get_full_row([]))

        cell_values.extend(get_full_row(["Reinforce Crab ID", Titles.DYNAMIC_OPTIONS]))
        for crab, group in self.config["reinforcing_crabs"].items():
            game_type = MineOption.MINE if group < 10 else MineOption.LOOT
            cell_values.extend(get_full_row([crab, game_type]))

        for _ in range(self.BUFFER_ROWS):
            cell_values.extend(get_full_row([]))

        logger.print_normal(f"Added {len(cell_values)} cells, expecting {len(cell_list)}")
        assert len(cell_values) == len(cell_list), "Cell/value mismatch"

        for i, val in enumerate(cell_values):
            cell_list[i].value = val
        worksheet.update_cells(cell_list)

        fmt_title = gsf.cellFormat(
            backgroundColor=gsf.color(0.7, 0.77, 0.87),
            textFormat=gsf.textFormat(bold=True, foregroundColor=gsf.color(0, 0, 0.54)),
            horizontalAlignment="LEFT",
        )
        fmt_fields = gsf.cellFormat(
            backgroundColor=gsf.color(0.7, 0.77, 0.87),
            textFormat=gsf.textFormat(bold=True, foregroundColor=gsf.color(0, 0, 0.54)),
            horizontalAlignment="LEFT",
        )
        fmt_values = gsf.cellFormat(
            backgroundColor=gsf.color(0.93, 0.93, 0.93),
            textFormat=gsf.textFormat(bold=False, foregroundColor=gsf.color(0, 0, 0)),
            horizontalAlignment="CENTER",
        )
        fmt_blank = gsf.cellFormat(
            backgroundColor=gsf.color(1, 1, 1),
            textFormat=gsf.textFormat(bold=False, foregroundColor=gsf.color(0, 0, 0)),
            horizontalAlignment="LEFT",
        )

        team_ranges = [(f"A{i}:B{i}", fmt_values) for i in range(10, 10 + num_teams)]
        reinforce_row = 9 + 3 + num_teams
        crab_ranges = [
            (f"A{i}:B{i}", fmt_values)
            for i in range(reinforce_row + 1, reinforce_row + 1 + num_crabs)
        ]

        gsf.set_column_width(worksheet, "A", 250)
        gsf.format_cell_ranges(
            worksheet,
            [
                ("A1", fmt_title),
                ("2:3", fmt_blank),
                ("A4", fmt_fields),
                ("B4", fmt_values),
                ("A5", fmt_fields),
                ("B5", fmt_values),
                ("A6", fmt_fields),
                ("B6", fmt_values),
                ("7:8", fmt_blank),
                ("A9:B9", fmt_fields),
                (f"{reinforce_row - 2}:{reinforce_row - 1}", fmt_blank),
                (f"{reinforce_row}", fmt_fields),
            ]
            + team_ranges
            + crab_ranges,
        )

    def _create_sheet_if_needed(self) -> None:
        if self.sheet is not None:
            return

        logger.print_normal(f"Searching for spreadsheet: {self.sheet_title}")
        sheets = self.client.openall()
        for sheet in sheets:
            if sheet.title == self.sheet_title:
                self.sheet = self.client.open(self.sheet_title)

        if self.sheet is not None:
            return

        logger.print_normal(f"Creating spreadsheet: {self.sheet_title}")

        self.sheet = self.client.create(self.sheet_title)
        self._create_info_worksheet()
        self._create_config_worksheet()
        self._share_sheet()

    def _delete_sheet(self) -> None:
        sheets = self.client.openall()
        for sheet in sheets:
            if sheet.title == self.sheet_title:
                logger.print_warn(f"Deleting spreadsheet: {self.sheet_title}")
                self.client.del_spreadsheet(sheet.id)

    def _share_sheet(self) -> None:
        logger.print_ok(f"Sharing config with {self.config['email']}...")
        self.sheet.share(
            self.config["email"],
            perm_type="user",
            role="writer",
            notify=True,
            email_message="Here is your Crabada Bot Configuration",
        )

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
        rows, cols = self._get_rows_cols()

        worksheet = self.sheet.add_worksheet(
            title=f"{self.user} Config", rows=str(rows), cols=str(cols)
        )
        worksheet.clear()

        logger.print_normal(f"Creating config worksheet")

        self._write_updated_config_worksheet(worksheet, rows, cols)

    def _create_info_worksheet(self) -> None:
        logger.print_normal(f"Creating info worksheet")

        worksheet = self.sheet.get_worksheet(0)
        worksheet.update_title("Info")
        message = INFO.splitlines()
        message_cells = worksheet.range(1, 1, len(message), 1)
        for i, line in enumerate(message):
            message_cells[i].value = line
        worksheet.update_cells(message_cells)

        fmt = gsf.cellFormat(
            backgroundColor=gsf.color(0.7, 0.77, 0.87),
            textFormat=gsf.textFormat(bold=True, foregroundColor=gsf.color(0, 0, 0.54)),
            horizontalAlignment="LEFT",
        )
        gsf.format_cell_ranges(worksheet, [("A1:F1", fmt), ("A13:F13", fmt)])

    def _get_save_config(self) -> T.Dict[T.Any, T.Any]:
        save_config = copy.deepcopy(self.config)
        for dont_save_key in [
            "crabada_key",
            "address",
            "commission_percent_per_mine",
            "discord_handle",
        ]:
            del save_config[dont_save_key]
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
        content = self._get_email_config()

        if self.dry_run or not self._did_config_change():
            return

        logger.print_warn(f"Config changed for {self.alias}, sending config email...")

        email_message = f"Hello {self.alias}!\n\n"
        email_message += "Here is your updated bot configuration:\n\n"
        email_message += content

        send_email(
            self.send_email_accounts,
            self.config["email"],
            f"\U0001F980 Crabada Bot Config Change Notification",
            email_message,
        )
