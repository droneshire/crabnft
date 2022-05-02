import time
import typing as T

from utils import logger
from utils.general import get_pretty_seconds


class CircuitBreaker:
    def __init__(self, min_delta: float, backoff: float = 1.0):
        self.backoff = backoff
        self.start_time = 0.0
        self.min_delta = min_delta

    def start(self):
        self.start_time = time.time()

    def trip(self):
        logger.print_fail_arrow(f"Trigger tripped!")
        time.sleep(self.backoff)
        self.backoff = self.backoff * 2

    def reset(self):
        self.backoff = 1.0

    def end(self):
        now = time.time()

        logger.print_bold(f"Start->End: {get_pretty_seconds(int(now - self.start_time))}")

        if now - self.start_time < self.min_delta:
            self.trip()
        else:
            self.reset()
