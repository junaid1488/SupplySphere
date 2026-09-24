from __future__ import annotations
from dataclasses import dataclass
from realtime.broker import EventBroker

@dataclass
class ProcessorResult:
    processed: int
    alerts: int
    inventory_updates: int
    shipment_delays: int

class EventProcessor:
    def __init__(self, broker: EventBroker): self.broker=broker
    def process(self, count: int=100) -> ProcessorResult:
        events=self.broker.consume(count); alerts=sum(e['event_type'] in {'shipment_delay','supplier_delay','stockout_warning'} for e in events)
        inventory=sum(e['event_type']=='inventory_update' for e in events); delays=sum(e['event_type']=='shipment_delay' for e in events)
        return ProcessorResult(len(events),alerts,inventory,delays)
