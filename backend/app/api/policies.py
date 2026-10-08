import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from app.database import get_db
from app.models.policy import VehiclePolicy
from app.schemas.policy import PolicyScrapeRequest, PolicyResponse, PolicyListResponse, PolicyUpdateRequest
from app.services.scraper import scrape_vehicle_policy, determine_policy_status
from app.services.zyla import fetch_vehicle_from_zyla

router = APIRouter(prefix="/api/policies", tags=["Vehicle Policies"])

@router.post("/scrape", response_model=PolicyResponse)
async def scrape_and_save_policy(
    request: PolicyScrapeRequest,
    db: Session = Depends(get_db)
):
    cleaned_reg = re.sub(r'[^A-Za-z0-9]', '', request.registration_number).upper()
    if not cleaned_reg or len(cleaned_reg) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vehicle registration number. Please enter a valid Indian car plate, e.g. XX00XX0000."
        )

    # Check cache if not forcing refresh
    if not request.force_refresh:
        existing = db.query(VehiclePolicy).filter(VehiclePolicy.registration_number == cleaned_reg).first()
        if existing:
            return existing

    # Fetch vehicle data: Prioritize PolicyBazaar live scraper for authentic quote & expiry date
    scraped = None
    try:
        print(f"[Policy API] Fetching via PolicyBazaar live scraper for {cleaned_reg}")
        scraped = await scrape_vehicle_policy(cleaned_reg)
    except Exception as e:
        print(f"[Policy API] Scraper error, attempting fallback: {e}")

    # Fallback to Zyla API Hub if primary scraper encountered an error
    if not scraped:
        try:
            scraped = await fetch_vehicle_from_zyla(cleaned_reg)
            if scraped:
                print(f"[Policy API] Successfully fetched vehicle specs via Zyla API for {cleaned_reg}")
        except Exception as e:
            print(f"[Policy API] Zyla API fallback error: {e}")

    if not scraped:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve vehicle policy details for '{cleaned_reg}'. Please check the registration number."
        )

    # Upsert to database
    policy = db.query(VehiclePolicy).filter(VehiclePolicy.registration_number == cleaned_reg).first()
    if not policy:
        policy = VehiclePolicy(**scraped)
        db.add(policy)
    else:
        for key, value in scraped.items():
            setattr(policy, key, value)

    db.commit()
    db.refresh(policy)
    return policy

@router.get("", response_model=PolicyListResponse)
def list_policies(
    search: Optional[str] = Query(None, description="Search by car number, model, owner, or city"),
    vehicle_type: Optional[str] = Query(None, description="Filter by Private or Commercial"),
    fuel_type: Optional[str] = Query(None, description="Filter by fuel type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = db.query(VehiclePolicy)

    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            or_(
                VehiclePolicy.registration_number.ilike(search_filter),
                VehiclePolicy.vehicle_model.ilike(search_filter),
                VehiclePolicy.maker_model.ilike(search_filter),
                VehiclePolicy.owner_name.ilike(search_filter),
                VehiclePolicy.rto_name.ilike(search_filter)
            )
        )

    if vehicle_type:
        query = query.filter(VehiclePolicy.vehicle_type == vehicle_type)

    if fuel_type:
        query = query.filter(VehiclePolicy.fuel_type == fuel_type)

    total = query.count()
    items = query.order_by(desc(VehiclePolicy.created_at)).offset(offset).limit(limit).all()

    return {"items": items, "total": total}

@router.get("/{identifier}", response_model=PolicyResponse)
def get_policy(
    identifier: str,
    db: Session = Depends(get_db)
):
    # Try by numeric id first, then by registration number
    if identifier.isdigit():
        policy = db.query(VehiclePolicy).filter(VehiclePolicy.id == int(identifier)).first()
    else:
        cleaned = re.sub(r'[^A-Za-z0-9]', '', identifier).upper()
        policy = db.query(VehiclePolicy).filter(VehiclePolicy.registration_number == cleaned).first()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle policy with identifier '{identifier}' not found."
        )
    return policy

@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db)
):
    policy = db.query(VehiclePolicy).filter(VehiclePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle policy with ID {policy_id} not found."
        )
    db.delete(policy)
    db.commit()
    return None

@router.patch("/{policy_id}", response_model=PolicyResponse)
def update_policy(
    policy_id: int,
    request: PolicyUpdateRequest,
    db: Session = Depends(get_db)
):
    policy = db.query(VehiclePolicy).filter(VehiclePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle policy with ID {policy_id} not found."
        )
    if request.policy_expiry_date is not None:
        policy.policy_expiry_date = request.policy_expiry_date
        if request.policy_status is None:
            policy.policy_status = determine_policy_status(request.policy_expiry_date)
    if request.policy_status is not None:
        policy.policy_status = request.policy_status
    if request.vehicle_type is not None:
        policy.vehicle_type = request.vehicle_type

    db.commit()
    db.refresh(policy)
    return policy
