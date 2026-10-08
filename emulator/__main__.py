"""가공 설비 PLC 에뮬레이터.

현재 기능:
- Modbus TCP로 작업 시작, 정지, 진행 수량을 받는 PLC를 흉내 냄
- 사이클마다 생산 수량을 올리고, 설정된 고장 모드를 주입
- 스핀들 회전수 같은 스칼라 상태를 MQTT로 발행
진동 파형 PIEZO는 sensor-emulator가 담당한다.
"""

import asyncio
import logging
import time

from .config import Settings
from .plc import Plc, build_server
from .sensors import SensorModel
from .sensors_mqtt import SensorPublisher

TICK_SECONDS = 0.1


async def run(settings: Settings) -> None:
    plc = Plc(settings.cycle_seconds)
    sensors = SensorModel(settings)
    publisher = SensorPublisher(settings)
    server = build_server(plc, settings.modbus_host, settings.modbus_port, settings.modbus_device_id)
    server_task = asyncio.create_task(server.serve_forever())
    logging.getLogger("emulator").info(
        "%s PLC Modbus TCP %s:%d · 센서 MQTT %s:%d (fault=%s)",
        settings.machine_code, settings.modbus_host, settings.modbus_port,
        settings.mqtt_host, settings.mqtt_port, settings.fault_mode,
    )

    last = time.monotonic()
    next_publish = last
    try:
        while not server_task.done():
            await asyncio.sleep(TICK_SECONDS)
            now = time.monotonic()
            dt, last = now - last, now
            sensors.step(dt, plc.running)
            plc.step(dt, sensors.rpm)
            if now >= next_publish:
                publisher.publish(sensors.read())
                next_publish = now + settings.sensor_interval
    finally:
        publisher.close()
        await server.shutdown()


def main() -> None:
    settings = Settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format=f"%(asctime)s %(levelname)s [{settings.machine_code}] %(name)s %(message)s",
    )
    logging.getLogger("pymodbus").setLevel(logging.ERROR)
    try:
        asyncio.run(run(settings))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
