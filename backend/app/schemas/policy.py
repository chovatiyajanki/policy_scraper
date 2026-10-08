from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field

class PolicyScrapeRequest(BaseModel):
    registration_number: str = Field(..., description="Indian Vehicle Registration Number, e.g. XX00XX0000")
    force_refresh: bool = Field(False, description="Bypass cache and force a live scrape")

class PolicyUpdateRequest(BaseModel):
    policy_expiry_date: Optional[str] = Field(None, description="Formatted expiry date, e.g. 14-Oct-2026")
    policy_status: Optional[str] = Field(None, description="Active, Expiring Soon, or Expired")
    vehicle_type: Optional[str] = Field(None, description="Private or Commercial")


class PolicyResponse(BaseModel):
    id: int
    registration_number: str
    maker_model: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    variant: Optional[str] = None
    vehicle_type: Optional[str] = None
    registration_date: Optional[str] = None
    manufacturing_month: Optional[str] = None
    registration_year: Optional[int] = None
    fuel_type: Optional[str] = None
    policy_expiry_date: Optional[str] = None
    policy_status: Optional[str] = None
    owner_name: Optional[str] = None
    rto_code: Optional[str] = None
    rto_name: Optional[str] = None
    engine_cc: Optional[int] = None
    color: Optional[str] = None
    seating_capacity: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PolicyListResponse(BaseModel):
    items: List[PolicyResponse]
    total: int
