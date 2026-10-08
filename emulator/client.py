from dataclasses import dataclass

import httpx

from .config import Settings


@dataclass
class Job:
    work_order_id: int
    wo_no: str
    product_name: str
    quantity: int
    produced_qty: int
    lot_no: str

    @classmethod
    def from_api(cls, data: dict) -> "Job":
        return cls(
            work_order_id=data["workOrderId"],
            wo_no=data["woNo"],
            product_name=data["productName"],
            quantity=data["quantity"],
            produced_qty=data["producedQty"],
            lot_no=data["lotNo"],
        )


@dataclass
class HeartbeatResult:
    machine_status: str
    job: Job | None


class GatewayClient:
    """MES backend의 /api/gateway/machines/{code} 연동 클라이언트."""

    def __init__(self, settings: Settings):
        self._http = httpx.Client(
            base_url=f"{settings.backend_url.rstrip('/')}/api/gateway/machines/{settings.machine_code}",
            headers={"x-machine-key": settings.machine_api_key},
            timeout=5.0,
        )

    def heartbeat(self, work_order_id: int | None, produced_qty: int | None, sensors: list[dict]) -> HeartbeatResult:
        res = self._http.post(
            "/heartbeat",
            json={"workOrderId": work_order_id, "producedQty": produced_qty, "sensors": sensors},
        )
        res.raise_for_status()
        data = res.json()
        return HeartbeatResult(
            machine_status=data["machineStatus"],
            job=Job.from_api(data["job"]) if data["job"] else None,
        )

    def complete(self, work_order_id: int, produced_qty: int) -> httpx.Response:
        return self._http.post("/complete", json={"workOrderId": work_order_id, "producedQty": produced_qty})

    def close(self) -> None:
        self._http.close()
