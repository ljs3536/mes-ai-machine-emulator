"""설비에 부착된 IoT 센서. PLC와 독립적으로 MQTT 브로커에 직접 publish 한다."""

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt

from .config import Settings
from .sensors import Reading

log = logging.getLogger("emulator.sensors")


class SensorPublisher:
    def __init__(self, settings: Settings):
        self.topic = f"{settings.mqtt_topic_prefix}/machines/{settings.machine_code}/sensors"
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"sensor-{settings.machine_code.lower()}",
        )
        self.client.on_connect = lambda *_: log.info("MQTT 연결됨 → %s", self.topic)
        self.client.on_disconnect = lambda *_: log.warning("MQTT 연결 끊김, 재연결 대기")
        self.client.reconnect_delay_set(1, 30)
        self.client.connect_async(settings.mqtt_host, settings.mqtt_port, keepalive=30)
        self.client.loop_start()

    def publish(self, readings: list[Reading]) -> None:
        if not self.client.is_connected():
            return
        payload = {
            "ts": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="milliseconds"),
            "values": [r.as_dict() for r in readings],
        }
        self.client.publish(self.topic, json.dumps(payload), qos=0)

    def close(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()
