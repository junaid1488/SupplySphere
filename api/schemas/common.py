from pydantic import BaseModel, Field
from typing import Any

class Page(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)

class OptimizationRequest(BaseModel):
    product_id: str | None = None
    horizon_days: int = Field(default=7, ge=1, le=90)

class SearchItem(BaseModel):
    type: str
    id: str
    label: str
    status: str | None = None
    risk_level: str | None = None
