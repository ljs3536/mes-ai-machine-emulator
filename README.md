# MES AI Machine Emulator

가공 공장 CNC 설비(Machine A/B)를 흉내 내는 Python 에뮬레이터.
[mes-ai-backend](https://github.com/ljs3536/mes-ai-backend)의 설비 게이트웨이 API와 통신하며
작업지시 수신 → 가공 진행현황/센서값 보고 → 완료 보고까지 수행합니다.

## 동작

```
┌──────────────┐  POST /api/gateway/machines/{code}/heartbeat   ┌─────────────┐
│  Emulator    │ ─── 센서값 + 진행수량(producedQty) ──────────────▶ │  MES Backend│
│ (MACHINE_A)  │ ◀── 지금 수행할 작업(job) 또는 null ──────────────── │             │
│              │  POST .../complete (수량 다 채우면)                 │             │
└──────────────┘ ───────────────────────────────────────────────▶ └─────────────┘
```

1. 작업자가 MES에서 작업 시작 → 설비 `RUN`, 작업지시 `IN_PROGRESS`
2. 다음 heartbeat 응답으로 job을 받아 가공 시작 (`CYCLE_SECONDS`마다 1개)
3. 매 `TELEMETRY_INTERVAL`초마다 센서값과 누적 생산수량 보고
4. 수량을 다 채우면 `complete` → 작업지시 `COMPLETED`, LOT `PROCESSED`(가공완료·검사대기), 설비 `IDLE`
5. MES에서 설비를 정지(STOP/HOLD)하면 다음 응답에서 job이 사라지고 즉시 가공 중단

에뮬레이터는 MES를 당겨오는(pull) 방식이라 백엔드가 설비 주소를 몰라도 되고,
재시작해도 `producedQty`를 MES에서 받아 이어서 가공합니다.

## 센서

| 코드 | 단위 | 모델 |
| --- | --- | --- |
| `SPINDLE_RPM` | rpm | 가동 시 `RATED_RPM`으로 램프업 |
| `SPINDLE_TEMP` | °C | 회전수·부하를 1차 지연으로 추종 |
| `VIBRATION` | mm/s | 회전수 × 노후도(누적 가동시간) |
| `SPINDLE_LOAD` | % | 가공 부하 (주기적 변동) |
| `OPERATING_HOURS` | h | 가동 중 누적 (`HOURS_PER_SECOND`로 가속) |

센서는 `emulator/sensors.py`의 `SensorModel.read()`에 항목을 추가하면 백엔드 수정 없이 저장됩니다
(백엔드는 `code/value/unit` 형태로 저장).

### 이상 주입 (AI 학습/검증용)

- `FAULT_MODE=bearing_overheat`: 작업 시작 `FAULT_AFTER_SECONDS` 후 주축 온도가 85℃ 이상으로 상승, 진동 증가
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
docker run -e BACKEND_URL=http://<backend>:8000 -e MACHINE_CODE=MACHINE_B factory-mes/machine-emulator
```

설비 한 대 = 프로세스(컨테이너) 하나입니다. Kubernetes에서는 설비별 Deployment(또는 StatefulSet)로 배포합니다.
