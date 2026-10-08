# MES AI Machine Emulator

가공 공장 CNC 설비(Machine A/B)를 흉내 내는 Python 에뮬레이터. 설비 한 대 = 프로세스(컨테이너) 하나입니다.

- PLC: Modbus TCP 서버. [mes-ai-edge-gateway](https://github.com/ljs3536/mes-ai-edge-gateway)가 명령을 쓰고 상태를 읽습니다.
- 센서: MQTT로 `mes/machines/{code}/sensors`에 직접 발행합니다. [mes-ai-backend](https://github.com/ljs3536/mes-ai-backend)와 AI가 구독합니다.

```
Edge Gateway ──Modbus TCP(:5020)──▶ PLC (emulator/plc.py)
                                      │ 가동 여부/회전수
                                      ▼
                                    센서 모델 ──MQTT──▶ mes/machines/{code}/sensors
```

## Modbus 레지스터 맵 (Holding Register, unit id 1)

명령 블록 (게이트웨이가 0~5를 한 번에 씀, `CMD_SEQ`가 바뀌면 실행):

| 주소 | 이름 | 설명 |
| --- | --- | --- |
| 0 | `CMD_CODE` | 0 NONE, 1 START, 2 STOP, 3 RESET |
| 1-2 | `JOB_ID` | 작업지시 ID (u32, hi/lo) |
| 3 | `TARGET_QTY` | 목표 수량 |
| 4 | `START_QTY` | 이어서 가공할 시작 수량 |
| 5 | `CMD_SEQ` | 명령 일련번호 |

상태 블록 (읽기):

| 주소 | 이름 | 설명 |
| --- | --- | --- |
| 100 | `STATE` | 0 IDLE, 1 RUNNING, 2 STOPPED, 3 COMPLETE, 4 ALARM |
| 101-102 | `JOB_ID` | 현재 작업 (u32) |
| 103 | `PRODUCED` | 생산 수량 |
| 104 | `TARGET` | 목표 수량 |
| 105 | `ALARM` | 알람 코드 |
| 106 | `RPM` | 주축 회전수 |
| 107 | `HEARTBEAT` | 매 주기 증가 |
| 108 | `ACK_SEQ` | 마지막으로 실행한 `CMD_SEQ` |

`registers.py`는 게이트웨이 저장소와 동일한 파일을 공유합니다(변경 시 양쪽 반영).

PLC는 `START` 후 `CYCLE_SECONDS`마다 1개씩 생산하고 목표 수량에 도달하면 `COMPLETE`로 멈춥니다.
작업지시 상태는 모르며, 판단은 MES/게이트웨이가 합니다.

## 센서

| 코드 | 단위 | 모델 |
| --- | --- | --- |
| `SPINDLE_RPM` | rpm | 가동 시 `RATED_RPM`으로 램프업 |
| `SPINDLE_TEMP` | °C | 회전수·부하를 1차 지연으로 추종 |
| `VIBRATION` | mm/s | 회전수 × 노후도(누적 가동시간) |
| `SPINDLE_LOAD` | % | 가공 부하 (주기적 변동) |
| `OPERATING_HOURS` | h | 가동 중 누적 (`HOURS_PER_SECOND`로 가속) |

메시지: `{"ts": "...+09:00", "values": [{"code": "SPINDLE_TEMP", "value": 61.2, "unit": "°C"}, ...]}` (QoS 0, `SENSOR_INTERVAL`초마다).
`emulator/sensors.py`의 `SensorModel.read()`에 항목을 추가하면 백엔드 수정 없이 저장됩니다.

### 이상 주입 (AI 학습/검증용)

- `FAULT_MODE=bearing_overheat`: 가동 `FAULT_AFTER_SECONDS` 후 주축 온도가 85℃ 이상으로 상승, 진동 증가
- `FAULT_MODE=imbalance`: 진동 최대 4배 증가

## 실행

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m emulator
```

컨테이너:

```bash
docker build -t factory-mes/machine-emulator .
docker run -p 5020:5020 -e MACHINE_CODE=MACHINE_B -e MQTT_HOST=<broker> factory-mes/machine-emulator
```
