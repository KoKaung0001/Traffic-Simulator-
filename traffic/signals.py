from dataclasses import dataclass

PHASES = ('NS green', 'NS amber', 'All red → EW', 'EW green', 'EW amber', 'All red → NS')


@dataclass
class Signals:
    index: int = 0
    elapsed: float = 0.0
    active_green: float = 30.0
    requested_green: float = 30.0
    override: float | None = None

    @property
    def phase(self):
        return PHASES[self.index]

    @property
    def duration(self):
        return self.active_green if self.index in (0, 3) else (3.0 if self.index in (1, 4) else 1.0)

    @property
    def remaining(self):
        return max(0.0, self.duration - self.elapsed)

    def request(self, seconds):
        self.requested_green = max(5.0, min(120.0, float(seconds)))

    def light(self, approach):
        group = 0 if approach in ('N', 'S') else 3
        return 'green' if self.index == group else ('amber' if self.index == group + 1 else 'red')

    def step(self, dt):
        self.elapsed += dt
        while self.elapsed + 1e-9 >= self.duration:
            self.elapsed = max(0.0, self.elapsed - self.duration)
            self.index = (self.index + 1) % 6
            if self.index in (0, 3):
                self.active_green = self.requested_green
