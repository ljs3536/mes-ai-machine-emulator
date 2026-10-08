import logging
import random
import time

import httpx

from .client import GatewayClient, Job
from .config import Settings
from .sensors import SensorModel

log = logging.getLogger("emulator")


class MachineEmulator:
    """한 대의 CNC 설비.

    매 주기마다 센서값과 생산수량을 MES에 보고하고, 응답으로 받은 작업(job)을 수행한다.
    MES가 작업을 내려주지 않으면(정지/HOLD) 즉시 가공을 멈춘다.
    """

    def __init__(self, settings: Settings, client: GatewayClient, rng: random.Random | None = None):
        self.s = settings
        self.client = client
        self.rng = rng or random.Random()
        self.sensors = SensorModel(settings, self.rng)
        self.job: Job | None = None
        self.produced = 0
        self._part_progress = 0.0

    def advance(self, dt: float) -> None:
        running = self.job is not None
        self.sensors.step(dt, running)
        if not running:
            return
        cycle = self.s.cycle_seconds * self.rng.uniform(0.9, 1.1)
        self._part_progress += dt / cycle
        made = int(self._part_progress)
        if made:
            self._part_progress -= made
            self.produced = min(self.job.quantity, self.produced + made)

    def _finish_if_done(self) -> None:
        if self.job is None or self.produced < self.job.quantity:
            return
        res = self.client.complete(self.job.work_order_id, self.produced)
        if res.is_success or res.status_code in (404, 409):
            log.info("작업 완료 보고 %s → HTTP %s", self.job.wo_no, res.status_code)
            self.job = None
        else:
            res.raise_for_status()

    def _sync(self) -> None:
        job_id = self.job.work_order_id if self.job else None
        result = self.client.heartbeat(
            job_id,
            self.produced if self.job else None,
            [r.as_dict() for r in self.sensors.read()],
        )
        assigned = result.job
        if assigned is None:
            if self.job is not None:
                log.warning("MES가 작업을 회수함 (%s, 설비 %s) - 가공 중단", self.job.wo_no, result.machine_status)
            self.job = None
        elif self.job is None or assigned.work_order_id != self.job.work_order_id:
            self.job = assigned
            self.produced = assigned.produced_qty
            self._part_progress = 0.0
            log.info(
                "작업 수신 %s · %s %d/%dea · LOT %s",
                assigned.wo_no, assigned.product_name, self.produced, assigned.quantity, assigned.lot_no,
            )

    def tick(self, dt: float) -> None:
        self.advance(dt)
        self._finish_if_done()
        self._sync()

    def run_forever(self) -> None:
        log.info("%s 에뮬레이터 시작 → %s (fault=%s)", self.s.machine_code, self.s.backend_url, self.s.fault_mode)
        last = time.monotonic()
        backoff = self.s.telemetry_interval
        while True:
            now = time.monotonic()
            try:
                self.tick(now - last)
                backoff = self.s.telemetry_interval
                if self.job:
                    log.debug("진행 %s %d/%d", self.job.wo_no, self.produced, self.job.quantity)
            except httpx.HTTPError as e:
                log.warning("MES 연결 실패: %s (%.0fs 후 재시도)", e, backoff)
                backoff = min(backoff * 2, 30)
            last = now
            time.sleep(backoff)
