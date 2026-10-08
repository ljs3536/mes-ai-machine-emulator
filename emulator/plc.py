"""CNC 설비 PLC 로직 + Modbus TCP 서버."""

import logging
import random

from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

from . import registers as reg
from .registers import Command, PlcState

log = logging.getLogger("emulator.plc")


class Plc:
    def __init__(self, cycle_seconds: float, rng: random.Random | None = None):
        self.cycle_seconds = cycle_seconds
        self.rng = rng or random.Random()
        self.state = PlcState.IDLE
        self.job_id = 0
        self.target_qty = 0
        self.produced_qty = 0
        self.alarm_code = 0
        self.spindle_rpm = 0
        self.heartbeat = 0
        self.ack_seq = 0
        self._part_progress = 0.0

    @property
    def running(self) -> bool:
        return self.state == PlcState.RUNNING

    def execute(self, command: int, job_id: int, target_qty: int, start_qty: int) -> None:
        if command == Command.START:
            if target_qty <= 0 or job_id <= 0:
                log.warning("START 무시: job=%s target=%s", job_id, target_qty)
                return
            resumed = job_id == self.job_id and self.state == PlcState.STOPPED
            self.job_id, self.target_qty = job_id, target_qty
            self.produced_qty = max(self.produced_qty if resumed else 0, min(start_qty, target_qty))
            self._part_progress = 0.0
            self.state = PlcState.RUNNING
            log.info("START job=%d %d/%d", job_id, self.produced_qty, target_qty)
        elif command == Command.STOP:
            if self.state == PlcState.RUNNING:
                self.state = PlcState.STOPPED
                log.info("STOP job=%d at %d/%d", self.job_id, self.produced_qty, self.target_qty)
        elif command == Command.RESET:
            self.state = PlcState.IDLE
            self.job_id = self.target_qty = self.produced_qty = 0
            self.alarm_code = 0
            log.info("RESET")

    def step(self, dt: float, rpm: float) -> None:
        self.heartbeat = (self.heartbeat + 1) & 0xFFFF
        self.spindle_rpm = int(max(0, min(rpm, 0xFFFF)))
        if self.state != PlcState.RUNNING:
            return
        self._part_progress += dt / (self.cycle_seconds * self.rng.uniform(0.9, 1.1))
        made = int(self._part_progress)
        if made:
            self._part_progress -= made
            self.produced_qty = min(self.target_qty, self.produced_qty + made)
        if self.produced_qty >= self.target_qty:
            self.state = PlcState.COMPLETE
            log.info("COMPLETE job=%d %d/%d", self.job_id, self.produced_qty, self.target_qty)

    def status_words(self) -> list[int]:
        return [
            int(self.state),
            *reg.split_u32(self.job_id),
            self.produced_qty,
            self.target_qty,
            self.alarm_code,
            self.spindle_rpm,
            self.heartbeat,
            self.ack_seq,
        ]

    async def on_request(self, func_code, start_address, address, count, registers, values):
        """pymodbus SimDevice action: 요청마다 상태 블록을 최신화하고, 명령 블록 쓰기를 처리한다."""
        base = reg.ST_STATE - start_address
        registers[base : base + reg.ST_BLOCK_SIZE] = self.status_words()

        if values and address <= reg.CMD_SEQ < address + len(values):
            cmd = registers[reg.CMD_CODE - start_address : reg.CMD_BLOCK_SIZE - start_address]
            cmd[address - reg.CMD_CODE : address - reg.CMD_CODE + len(values)] = values
            seq = cmd[reg.CMD_SEQ]
            if seq != self.ack_seq:
                self.execute(
                    cmd[reg.CMD_CODE],
                    reg.join_u32(cmd[reg.CMD_JOB_ID_HI], cmd[reg.CMD_JOB_ID_LO]),
                    cmd[reg.CMD_TARGET_QTY],
                    cmd[reg.CMD_START_QTY],
                )
                self.ack_seq = seq
                registers[base : base + reg.ST_BLOCK_SIZE] = self.status_words()
        return None


def build_server(plc: Plc, host: str, port: int, device_id: int) -> ModbusTcpServer:
    device = SimDevice(
        device_id,
        simdata=[SimData(0, count=reg.REGISTER_COUNT, values=0, datatype=DataType.REGISTERS)],
        action=plc.on_request,
    )
    return ModbusTcpServer(device, address=(host, port))
