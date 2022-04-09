"""
Utility script that helps write transactions to a spreadsheet
"""
import csv
import os
import typing as T


class CsvLogger:
    def __init__(self, csv_file: str, header: T.List[str]) -> None:
        self.csv_file = csv_file
        self.file_obj = None
        self.csv_writer = None
        self.header = header
        self.col_map = {col.lower(): i for i, col in enumerate(header)}

    def write_header(self) -> None:
        if self.file_obj is None:
            raise Exception("attempting to write unopened csv file")

        self.csv_writer.writerow(self.header)

    def open(self) -> None:
        if self.file_obj is not None:
            raise Exception("opening already open csv file")
        if os.path.isfile(self.csv_file):
            self.file_obj = open(self.csv_file, "a")
        else:
            self.file_obj = open(self.csv_file, "w")
        self.csv_writer = csv.writer(self.file_obj)

    def close(self) -> None:
        if self.file_obj is None:
            raise Exception("closing already closed csv file")
        self.file_obj.close()

    def write(self, data: T.Dict[str, T.Any]) -> None:
        if self.file_obj is None:
            raise Exception("attempting to write unopened csv file")

        row = [None] * len(self.header)
        for k, v in data.items():
            inx = self.col_map.get(k, None)
            if inx is None:
                continue
            row[inx] = v
        self.csv_writer.writerow(row)
