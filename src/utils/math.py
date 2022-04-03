import typing as T


class Average:
    def __init__(self, value: T.Optional[T.Any] = None):
        self.init = value
        self.total = 0.0 if value is None else value
        self.count = 0 if value is None else 1

    def reset(self) -> None:
        self.total = 0.0 if self.init is None else self.init
        self.count = 0

    def update(self, value: float) -> None:
        self.total += value
        self.count += 1

    def get_avg(self) -> float:
        return self.total / self.count if self.count > 0 else self.total


if __name__ == "__main__":
    test_sequence = [1, 1, 1, 1, 1, 1]
    a = Average()
    assert a.get_avg() == 0.0, "avg incorrect"
    assert a.count == 0, "count wrong"

    for i in test_sequence:
        a.update(i)
    assert a.get_avg() == 1, "avg incorrect"
    assert a.count == len(test_sequence), "count wrong"

    a.reset()
    assert a.get_avg() == 0, "avg incorrect"
    assert a.count == 0, "count wrong"

    test_sequence = [1, 1, 1, 2, 2, 2]
    for i in test_sequence:
        a.update(i)
    assert a.get_avg() == 1.5, "avg incorrect"
    assert a.count == len(test_sequence), "count wrong"

    a = Average(2)
    assert a.get_avg() == 2, "avg incorrect"
    assert a.count == 1, "count wrong"

    a.update(1)
    for i in test_sequence:
        a.update(i)

    assert a.get_avg() == 1.5, "avg incorrect"
    assert a.count == len(test_sequence) + 2, "count wrong"
