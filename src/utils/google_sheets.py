import typing as T

from googleapiclient.discovery import build
from google.oauth2 import service_account

from utils import logger

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]


class GoogleSheets:
    def __init__(self, title: str, credential_file: str, email: str, role: str):
        self.title = title
        self.email = email
        self.role = role
        self.sheet_id = self._create()

        credentials = service_account.Credentials.from_service_account_file(
            credential_file, scopes=SCOPES
        )
        self.sheets = build("sheets", "v4", credentials=credentials)
        self.drive = build("drive", "v3", credentials=credentials)

    def _create(self):
        spreadsheet_details = {"properties": {"title": self.title}}
        sheet = (
            self.sheets.spreadsheets()
            .create(body=spreadsheet_details, fields="spreadsheetId")
            .execute()
        )
        self.sheet_id = sheet.get("spreadsheetId")
        logger.print_normal(f"Created Google spreadsheet with id {self.sheet_id}")
        permissions = {"type": "user", "role": self.role, "emailAddress": self.email}
        self.drive.permissions().create(fileId=self.sheet_id, body=permissions).execute()

    def read_range(self, rd_range: str) -> T.List[T.Any]:
        result = (
            spreadsheet_service.spreadsheets()
            .values()
            .get(spreadsheetId=sheetId, range=rd_range)
            .execute()
        )
        rows = result.get("values", [])
        logger.print_normal(f"{len(rows)} rows retrieved")
        return rows

    def write_range(self, wr_range: str, values: T.List[T.Any]) -> None:
        body = {"values": values}
        result = (
            spreadsheet_service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.sheet_id,
                range=wr_range,
                valueInputOption="USER_ENTERED",
                body=body,
            )
            .execute()
        )
        logger.print_normal(f"{result.get('updatedCells')} cells updated")

    def read_ranges(self, rd_ranges: T.List[str]) -> T.List[T.Any]:
        result = (
            spreadsheet_service.spreadsheets()
            .values()
            .batchGet(spreadsheetId=self.sheet_id, ranges=rd_ranges)
            .execute()
        )
        ranges = result.get("valueRanges", [])
        logger.print_normal(f"{len(ranges)} ranges retrieved")
        return ranges

    def write_ranges(self, data: T.List[T.Dict[str, T.List[T.Any]]]) -> None:
        body = {"valueInputOption": "USER_ENTERED", "data": data}
        result = (
            spreadsheet_service.spreadsheets()
            .values()
            .batchUpdate(spreadsheetId=self.sheet_id, body=body)
            .execute()
        )
        logger.print_normal(f"{result.get('updatedCells')} cells updated")
