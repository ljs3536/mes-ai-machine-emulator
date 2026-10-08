from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    backend_url: str = "http://localhost:8000"
    machine_code: str = "MACHINE_A"
    machine_api_key: str = "dev-machine-key"

    telemetry_interval: float = 1.0
    """센서/진행현황 보고 주기(초)."""
    cycle_seconds: float = 0.6
    """부품 1개 가공 시간(초). 데모용으로 실제보다 빠르게 설정."""
    rated_rpm: float = 3000
    hours_per_second: float = 1 / 60
    """실제 1초 가동 시 누적 가동시간 증가량(시간). 노후도 연출용 가속 계수."""
    initial_operating_hours: float = 1200

    fault_mode: Literal["none", "bearing_overheat", "imbalance"] = "none"
    fault_after_seconds: float = 30
    """작업 시작 후 이 시간이 지나면 fault_mode 증상이 나타난다."""

    log_level: str = "INFO"
