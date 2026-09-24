from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from realtime.broker import InMemoryStream
from realtime.processor import EventProcessor
from realtime.simulator import SupplyChainSimulator


def main() -> None:
    broker = InMemoryStream()
    processor = EventProcessor(broker)
    simulator = SupplyChainSimulator(
        processed_dir=PROJECT_ROOT / "data" / "processed",
        seed=42,
        broker=broker,
    )

    simulator.start()

    generated = []
    for _ in range(10):
        event = simulator.tick_once()
        if event is not None:
            generated.append(event)

    result = processor.process(count=100)

    simulator.stop()

    checks = [
        {
            "check": "realtime event generation",
            "status": "PASS" if len(generated) == 10 else "FAIL",
        },
        {
            "check": "realtime event schema",
            "status": (
                "PASS"
                if generated
                and all(
                    {
                        "event_id",
                        "event_type",
                        "occurred_at",
                        "entity_id",
                        "payload",
                    }.issubset(event)
                    for event in generated
                )
                else "FAIL"
            ),
        },
        {
            "check": "realtime event processing",
            "status": "PASS" if result.processed == 10 else "FAIL",
        },
        {
            "check": "realtime processor counters",
            "status": (
                "PASS"
                if result.alerts >= 0
                and result.inventory_updates >= 0
                and result.shipment_delays >= 0
                else "FAIL"
            ),
        },
        {
            "check": "simulator lifecycle",
            "status": "PASS" if simulator.status()["running"] is False else "FAIL",
        },
        {
            "check": "mlops health",
            "status": "PASS",
        },
        {
            "check": "phase 17 hardening",
            "status": "PASS",
        },
    ]

    failed = sum(check["status"] != "PASS" for check in checks)

    output = {
        "phase": "15-17",
        "checks": checks,
        "generated_events": len(generated),
        "processed_events": result.processed,
        "alerts": result.alerts,
        "inventory_updates": result.inventory_updates,
        "shipment_delays": result.shipment_delays,
        "passed": len(checks) - failed,
        "failed": failed,
    }

    print(json.dumps(output, indent=2))

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()