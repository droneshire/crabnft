import gspread
import gspread_formatting as gsf
import time
import typing as T

from contextlib import contextmanager
from oauth2client.service_account import ServiceAccountCredentials

from utils import logger

SHARE_MESSAGE = """
I'd like to share a document with you!
"""


class GoogleSheets:
    DEFAULT_BACKOFF = 10.0

    def __init__(self, title: str, credential_file: str, share_email: str):
        self.title = title
        self.gspread_client = gspread.service_account(filename=credential_file)
        self.share_email = share_email
        self.sheet = None

        self.google_api_success = False

        with open(credentials, "r") as infile:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                json.load(infile), scopes=self.GSHEETS_SCOPE
            )
        self.client = gspread.authorize(creds)
        self.sheet = None
        self.sheet_title = title

        self.backoff = self.DEFAULT_BACKOFF
        self.last_fail_time = time.time()

    def create(self) -> None:
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

        with self._google_api_action():
            self.sheet = self.client.create(self.sheet_title)

        if not self.google_api_success:
            self.sheet = None
            return

    def share_sheet(self) -> None:
        if not self._can_interact_with_api():
            return

        logger.print_ok(f"Sharing config with {self.share_email}...")
        with self._google_api_action():
            self.sheet.share(
                self.share_email,
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

    def read_row(self, row: int, worksheet_inx: int = 0) -> T.List[T.Any]:
        with self._google_api_action():
            worksheet = self.sheet.get_worksheet(worksheet_inx)
        if not self.google_api_success:
            return []
        return worksheet.row_values(row)

    def read_column(self, column: int, worksheet_inx: int = 0) -> T.List[T.Any]:
        with self._google_api_action():
            worksheet = self.sheet.get_worksheet(worksheet_inx)
        if not self.google_api_success:
            return []
        return worksheet.col_values(column)

    def read_range(self, ranges: str, worksheet_inx: int = 0) -> T.List[T.List[T.Any]]:
        worksheet = self.sheet.get_worksheet(worksheet_inx)
        if not self.google_api_success:
            return []
        return worksheet.batch_get(ranges)

    def write(self, cell_range: str, value: T.Any, worksheet_inx: int = 0) -> None:
        worksheet = self.sheet.get_worksheet(worksheet_inx)
        with self._google_api_action():
            if ":" in cell_range:
                assert isinstance(value, list), "value not a range"
                data = [{"range": cell_range, "values": value}]
                print(data)
                worksheet.batch_update(data)
            else:
                worksheet.update(cell_range, value)


    def format(
        self, cell_range_format: T.List[T.Any], worksheet_inx: int = 0
    ) -> None:
        worksheet = self.sheet.get_worksheet(worksheet_inx)
        with self._google_api_action():
            gsf.format_cell_ranges(worksheet, cell_range_format)

    def _can_interact_with_api(self, verify_sheets: bool=False) -> bool:
        now = time.time()

        if self.dry_run:
            return False

        if not self.allow_sheets_config:
            return False

        if now - self.last_fail_time < self.backoff:
            wait_time_end = self.last_fail_time + self.backoff
            wait_time_left = wait_time_end - now
            wait_pretty_seconds = get_pretty_seconds(int(wait_time_left))
            logger.print_warn(
                f"Waiting to take action for {wait_pretty_seconds} due to config manager backoff"
            )
            return False

        if check_sheets_none and self.sheet is None:
            return False

        return True

    @contextmanager
    def _google_api_action(self) -> T.Iterator[None]:
        self.google_api_success = False
        try:
            yield
            self.backoff = self.DEFAULT_BACKOFF
            self.google_api_success = True
            logger.print_normal(f"Resetting backoff to {self.DEFAULT_BACKOFF}")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            now = time.time()
            self.backoff = max(self.backoff * 2, (now - self.last_fail_time) * 2)
            self.last_fail_time = now
            logger.print_fail(
                f"failure to google api call, updating backoff to {self.backoff} seconds and fail time to {self.last_fail_time}"
            )
