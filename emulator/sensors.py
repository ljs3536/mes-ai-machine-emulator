"""CNC 설비 센서 물리 모델 (단순화).

가동 여부에 따라 주축 RPM/부하가 오르내리고, 온도는 1차 지연으로 따라가며,
진동은 회전수와 누적 가동시간(노후도)에 비례한다. fault_mode로 이상 증상을 주입할 수 있다.
"""

import math
import random
from dataclasses import dataclass

from .config import Settings

AMBIENT_C = 24.0


@dataclass
class Reading:
    code: str
    value: float
    unit: str

    def as_dict(self) -> dict:
        return {"code": self.code, "value": round(self.value, 3), "unit": self.unit}


class SensorModel:
    def __init__(self, settings: Settings, rng: random.Random | None = None):
        self.s = settings
        self.rng = rng or random.Random()
        self.rpm = 0.0
        self.load = 0.0
        self.temp = AMBIENT_C + 2
        self.operating_hours = settings.initial_operating_hours
        self.vibration = 0.2
        self.run_seconds = 0.0

    def _noise(self, scale: float) -> float:
        return self.rng.gauss(0, scale)

    def step(self, dt: float, running: bool) -> None:
        s = self.s
        target_rpm = s.rated_rpm if running else 0.0
        self.rpm += (target_rpm - self.rpm) * min(1.0, dt * 1.5)
        target_load = 55.0 + 10 * math.sin(self.run_seconds / 7) if running else 0.0
        self.load += (target_load - self.load) * min(1.0, dt * 2)

        fault = running and s.fault_mode != "none" and self.run_seconds >= s.fault_after_seconds
        fault_level = min(1.0, (self.run_seconds - s.fault_after_seconds) / 30) if fault else 0.0

        heat_target = AMBIENT_C + 0.008 * self.rpm + 0.25 * self.load
        if s.fault_mode == "bearing_overheat":
            heat_target += 45 * fault_level
        self.temp += (heat_target - self.temp) * min(1.0, dt / 20)

        wear = 1 + max(0.0, self.operating_hours - 1000) / 5000
        base_vib = 0.15 + (self.rpm / max(s.rated_rpm, 1)) * 1.8 * wear
        if s.fault_mode == "imbalance":
            base_vib *= 1 + 3 * fault_level
        elif s.fault_mode == "bearing_overheat":
            base_vib *= 1 + 0.8 * fault_level
        self.vibration = max(0.05, base_vib + self._noise(0.08 * wear))

        if running:
            self.run_seconds += dt
            self.operating_hours += dt * s.hours_per_second
        else:
            self.run_seconds = 0.0

    def read(self) -> list[Reading]:
        return [
            Reading("SPINDLE_RPM", max(0.0, self.rpm + self._noise(5 if self.rpm > 1 else 0)), "rpm"),
            Reading("SPINDLE_TEMP", self.temp + self._noise(0.15), "°C"),
            Reading("VIBRATION", self.vibration, "mm/s"),
            Reading("SPINDLE_LOAD", max(0.0, self.load + self._noise(1.5 if self.load > 1 else 0)), "%"),
            Reading("OPERATING_HOURS", self.operating_hours, "h"),
        ]
