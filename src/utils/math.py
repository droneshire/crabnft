import typing as T


class Average:
    def __init__(self, value=0.0):
        self.total = value
        self.count = 0

    def reset(self) -> None:
        self.total = 0.0
        self.count = 0

    def update(self, value: float) -> None:
        self.total += value
        self.count += 1

    def get_avg(self) -> float:
        return self.total / self.count if self.count > 0 else self.total
