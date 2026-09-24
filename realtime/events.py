from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import uuid

EVENT_TYPES = (
    'new_order','inventory_update','shipment_dispatch','shipment_delay',
    'supplier_delay','warehouse_capacity_change','stockout_warning'
)

@dataclass(frozen=True)
class SupplyEvent:
    event_id: str
    event_type: str
    occurred_at: str
    entity_id: str
    payload: dict

    @classmethod
    def create(cls, event_type: str, entity_id: str, payload: dict, occurred_at: datetime | None = None) -> 'SupplyEvent':
        if event_type not in EVENT_TYPES:
            raise ValueError(f'Unsupported event_type: {event_type}')
        dt = occurred_at or datetime.now(timezone.utc)
        return cls(str(uuid.uuid4()), event_type, dt.isoformat(), str(entity_id), payload)

    def to_dict(self) -> dict:
        return asdict(self)
