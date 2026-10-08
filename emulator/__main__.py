import logging

from .client import GatewayClient
from .config import Settings
from .machine import MachineEmulator


def main() -> None:
    settings = Settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format=f"%(asctime)s %(levelname)s [{settings.machine_code}] %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    client = GatewayClient(settings)
    try:
        MachineEmulator(settings, client).run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


if __name__ == "__main__":
    main()
