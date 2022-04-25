import gspread
import typing as T

from utils import logger


class GoogleSheets:
    def __init__(self, title: str, credential_file: str):
        self.title = title
        self.gspread_client = gspread.service_account(filename=credential_file)

        self.sheet = None
        sheets = self.gspread_client.openall()
        if not sheets:
            self.sheet = self.create(title)
        else:
            for sheet in sheets:
                if sheet.title == title:
                    self.sheet = self.gspread_client.open(title)

    def create(self, title: str) -> None:
        self.sheet = self.gspread_client.create(title)

    def read_row(self, row: int, worksheet_inx: int = 0) -> T.List[T.Any]:
        worksheet = self.sheet.get_worksheet(worksheet_inx)
        return worksheet.row_values(row)

    def read_column(self, column: int, worksheet_inx: int = 0) -> None:
        worksheet = self.sheet.get_worksheet(worksheet_inx)
        return worksheet.col_values(column)

    def write(self, cell_range: str, value: T.Any, worksheet_inx: int = 0) -> None:
        worksheet = self.sheet.get_worksheet(worksheet_inx)
        if ":" in cell_range:
            assert isinstance(value, list), "value not a range"
            worksheet.batch_update({"range": cell_range, "values": value})
        else:
            worksheet.update(cell, value)
