"""Inclusive CPU timings; rendering/GPU submission is measured by the GUI probe."""
from collections import defaultdict
from contextlib import contextmanager
from time import perf_counter


class Timings:
    def __init__(self):self.values=defaultdict(float);self.enabled=False

    @contextmanager
    def measure(self,name):
        if not self.enabled:
            yield;return
        start=perf_counter()
        try:yield
        finally:self.values[name]+=(perf_counter()-start)*1000

    def take(self):
        values=dict(self.values);self.values.clear();return values
