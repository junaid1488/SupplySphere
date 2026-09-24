from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import pandas as pd
from realtime.events import SupplyEvent
from realtime.broker import InMemoryStream, EventBroker

@dataclass
class SimulationState:
    running: bool = False
    tick: int = 0
    processed: int = 0
    started_at: str | None = None
    last_event_at: str | None = None
    alerts: int = 0
    inventory_updates: int = 0
    shipments_delayed: int = 0

class SupplyChainSimulator:
    def __init__(self, processed_dir: str | Path = 'data/processed', seed: int = 42, broker: EventBroker | None = None):
        self.root = Path(processed_dir); self.rng = random.Random(seed); self.broker = broker or InMemoryStream(); self.state = SimulationState()
        self._products = self._load_ids('stockout_predictions.csv','product_id',20)
        self._warehouses = self._load_ids('warehouses.csv','warehouse_id',12)
        self._orders = self._load_ids('delivery_risk_predictions.csv','order_id',30)
    def _load_ids(self, file: str, col: str, n: int) -> list[str]:
        p=self.root/file
        if p.exists():
            df=pd.read_csv(p); return df[col].dropna().astype(str).drop_duplicates().head(n).tolist() if col in df else []
        return []
    def start(self):
        self.state.running=True
        self.state.started_at=self.state.started_at or datetime.now(timezone.utc).isoformat()
        return self.status()
    def pause(self): self.state.running=False; return self.status()
    def stop(self): self.state.running=False; return self.status()
    def status(self): return self.state.__dict__.copy()
    def tick_once(self) -> dict | None:
        if not self.state.running: return None
        now=datetime.now(timezone.utc)
        choices=[]
        if self._orders: choices.append(('new_order',self.rng.choice(self._orders)))
        if self._products and self._warehouses: choices.append(('inventory_update',self.rng.choice(self._products)+'@'+self.rng.choice(self._warehouses)))
        if self._orders: choices += [('shipment_dispatch',self.rng.choice(self._orders)),('shipment_delay',self.rng.choice(self._orders))]
        if self._warehouses: choices.append(('warehouse_capacity_change',self.rng.choice(self._warehouses)))
        event_type, entity = self.rng.choice(choices or [('new_order','demo-order')])
        payload={'simulation_tick':self.state.tick+1}
        if event_type=='inventory_update': payload.update(delta_units=self.rng.randint(-8,12))
        elif event_type=='shipment_delay': payload.update(delay_hours=self.rng.randint(2,48))
        elif event_type=='warehouse_capacity_change': payload.update(delta_capacity=self.rng.randint(-20,20))
        event=SupplyEvent.create(event_type,entity,payload,now).to_dict()
        self.broker.publish(event); self.state.tick+=1; self.state.processed+=1; self.state.last_event_at=now.isoformat()
        self.state.inventory_updates += event_type=='inventory_update'; self.state.shipments_delayed += event_type=='shipment_delay'; self.state.alerts += event_type in ('shipment_delay','stockout_warning','supplier_delay')
        return event
