"""
Utility script that helps write transactions to a spreadsheet
"""
import csv
import os
import typing as T


class CsvLogger:
    def __init__(self, csv_file: str, header: T.List[str], dry_run=False) -> None:
        self.csv_file = csv_file
        self.file_obj = None
        self.csv_writer = None
        self.header = header
        self.col_map = {col.lower(): i for i, col in enumerate(header)}
        self.dry_run = dry_run

    def open(self) -> None:
        if self.dry_run:
            return

        if self.file_obj is not None:
            raise Exception("opening already open csv file")
        self._write_header_if_needed()
        self.file_obj = open(self.csv_file, "a")
        self.csv_writer = csv.writer(self.file_obj)

    def close(self) -> None:
        if self.dry_run:
            return

        if self.file_obj is None:
            raise Exception("closing already closed csv file")
        self.file_obj.close()
        self.file_obj = None

    def write(self, data: T.Dict[str, T.Any]) -> None:
        if self.dry_run:
            return

        if self.file_obj is None:
            raise Exception("attempting to write unopened csv file")

        row = [None] * len(self.header)
        for k, v in data.items():
            inx = self.col_map.get(k, None)
            if inx is None:
                continue
            row[inx] = v
        self.csv_writer.writerow(row)

    def _write_header_if_needed(self) -> None:
        if self.dry_run:
            return

        reader = []
        if os.path.isfile(self.csv_file):
            with open(self.csv_file) as infile:
                reader = list(csv.reader(infile))

        with open(self.csv_file, "w") as outfile:
            writer = csv.writer(outfile)

            if len(reader) == 0:
                writer.writerow(self.header)
                return

            if len([i for i in reader[0] if i in self.header]) != len(self.header):
                reader.insert(0, self.header)
                for row in reader:
                    writer.writerow(row)
