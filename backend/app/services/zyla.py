import os
import re
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional
import httpx
from dotenv import load_dotenv

from app.services.scraper import compute_original_expiry_date

load_dotenv()

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

def format_date(dt_str: Optional[str]) -> Optional[str]:
    if not dt_str:
        return None
    dt_str = str(dt_str).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            d = datetime.strptime(dt_str, fmt)
            return f"{d.day} {d.strftime('%B')}, {d.year}"
        except Exception:
            pass
    return dt_str

def format_mfg(dt_str: Optional[str]) -> Optional[str]:
    if not dt_str:
        return None
    dt_str = str(dt_str).strip()
    try:
        if "-" in dt_str and len(dt_str) >= 7:
            parts = dt_str.split("-")
            y, m = int(parts[0]), int(parts[1])
            if 1 <= m <= 12:
                return f"{MONTH_NAMES[m - 1]}-{y}"
        if "/" in dt_str:
            parts = dt_str.split("/")
            m, y = int(parts[0]), int(parts[1])
            if 1 <= m <= 12:
                return f"{MONTH_NAMES[m - 1]}-{y}"
    except Exception:
        pass
    return dt_str

def format_expiry(dt_str: Optional[str]) -> Optional[str]:
    if not dt_str:
        return None
    dt_str = str(dt_str).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d-%b-%Y"):
        try:
            d = datetime.strptime(dt_str, fmt)
            return d.strftime("%d-%b-%Y")
        except Exception:
            pass
    return dt_str

def determine_status(expiry_str: Optional[str]) -> Optional[str]:
    if not expiry_str:
        return None
    try:
        exp_date = datetime.strptime(expiry_str, "%d-%b-%Y").date()
        today = date.today()
        days_left = (exp_date - today).days
        if days_left < 0:
            return "Expired"
        elif days_left <= 30:
            return "Expiring Soon"
        else:
            return "Active"
    except Exception:
        return "Active"

async def fetch_vehicle_from_zyla(reg_no: str) -> Optional[Dict[str, Any]]:
    """
    Fetches vehicle RC and policy details from Zyla API Hub.
    Uses ZYLA_API_KEY and ZYLA_API_URL from environment variables.
    """
    api_key = os.getenv("ZYLA_API_KEY", "").strip()
    endpoint_url = os.getenv("ZYLA_API_URL", "").strip()

    if not api_key:
        print("[Zyla API] ZYLA_API_KEY not configured in .env")
        return None

    cleaned_reg = re.sub(r'[^A-Za-z0-9]', '', reg_no).upper()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Candidate URLs if custom endpoint is not explicitly defined in .env
    candidate_urls = []
    if endpoint_url:
        candidate_urls.append(endpoint_url)
    else:
        # Default Zyla endpoints for India vehicle verification
        candidate_urls.extend([
            f"https://zylalabs.com/api/1597/indian+vehicle+rc+details+api/1247/get+rc+details?registration_number={cleaned_reg}",
            f"https://zylalabs.com/api/2667/vehicle+rc+verification+api/2712/get+details?rc_number={cleaned_reg}",
            f"https://zylalabs.com/api/3602/india+vehicle+details+api/4054/vehicle+details?reg_num={cleaned_reg}",
            f"https://zylalabs.com/api/4123/rc+verification+api/4988/get+details?reg_no={cleaned_reg}",
            f"https://zylalabs.com/api/2884/indian+vehicle+info+api/3001/get+rc?plate={cleaned_reg}",
            f"https://zylalabs.com/api/2012/vahan+rc+verification+api/1789/details?vehicle_num={cleaned_reg}",
            f"https://zylalabs.com/api/2311/rto+vehicle+information+api/2199/rc+search?reg_no={cleaned_reg}",
            f"https://zylalabs.com/api/vehicle-rc-verification/get-details?rc_number={cleaned_reg}",
            f"https://zylalabs.com/api/v1/vehicle/rc-details?rc_number={cleaned_reg}"
        ])

    async with httpx.AsyncClient(timeout=15.0) as client:
        for url in candidate_urls:
            try:
                print(f"[Zyla API] Querying: {url}")
                # Try GET with query parameters
                sep = "&" if "?" in url else "?"
                target_url = url if ("rc_number" in url or "registration" in url) else f"{url}{sep}rc_number={cleaned_reg}"
                
                resp = await client.get(target_url, headers=headers)
                
                # If GET returns 405 Method Not Allowed, try POST with JSON body
                if resp.status_code == 405:
                    post_url = url.split("?")[0]
                    payload = {"rc_number": cleaned_reg, "registration_number": cleaned_reg}
                    resp = await client.post(post_url, headers=headers, json=payload)

                print(f"[Zyla API] Response status: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    # Unwrap standard wrapper structures (data, response, result)
                    if isinstance(data, dict):
                        inner = data.get("data") or data.get("result") or data.get("response") or data
                        if isinstance(inner, dict):
                            return parse_zyla_response(inner, cleaned_reg)
                else:
                    print(f"[Zyla API] Non-200 response ({resp.status_code}): {resp.text[:200]}")

            except Exception as e:
                print(f"[Zyla API] Error querying {url}: {e}")

    return None

def parse_zyla_response(data: Dict[str, Any], reg_no: str) -> Dict[str, Any]:
    """
    Parses and standardizes the payload returned by Zyla API into the application's format.
    """
    maker_model = (
        data.get("maker_model")
        or data.get("model")
        or data.get("vehicle_model")
        or data.get("model_name")
        or data.get("maker_description")
    )
    vehicle_make = (
        data.get("vehicle_make")
        or data.get("make")
        or data.get("make_name")
        or data.get("maker_name")
    )
    vehicle_model = (
        data.get("vehicle_model")
        or data.get("model")
        or data.get("model_name")
        or maker_model
    )
    variant = (
        data.get("variant")
        or data.get("variant_name")
        or data.get("version")
    )
    
    # Dates
    reg_date_raw = data.get("registration_date") or data.get("reg_date") or data.get("date_of_registration")
    mfg_date_raw = data.get("manufacturing_date") or data.get("mfg_date") or data.get("manufacturing_year")
    
    reg_date = format_date(reg_date_raw)
    mfg_month = format_mfg(mfg_date_raw)
    
    reg_year_raw = data.get("registration_year") or (reg_date_raw[:4] if reg_date_raw and len(str(reg_date_raw)) >= 4 else None)
    reg_year = int(reg_year_raw) if reg_year_raw and str(reg_year_raw).isdigit() else None

    # Fuel & Vehicle class
    fuel_type = data.get("fuel_type") or data.get("fuel_descr") or data.get("type_of_fuel")
    v_class = str(data.get("vehicle_class") or data.get("class") or "").lower()
    if any(k in v_class for k in ["commercial", "taxi", "transport", "goods"]):
        vehicle_type = "Commercial"
    elif v_class:
        vehicle_type = "Private"
    else:
        vehicle_type = "Private"

    # Insurance Expiry
    insurance_raw = (
        data.get("insurance_upto")
        or data.get("insurance_expiry_date")
        or data.get("insurance_valid_upto")
        or data.get("policy_expiry_date")
        or data.get("insurance_details", {}).get("expiry_date")
        or data.get("insurance_detail", {}).get("expiry_date")
    )
    
    expiry_formatted = compute_original_expiry_date(reg_date_raw or reg_date, insurance_raw)
    policy_status = determine_status(expiry_formatted)

    # Technical specs
    engine_cc_raw = data.get("cubic_capacity") or data.get("cc") or data.get("engine_capacity")
    engine_cc = int(engine_cc_raw) if engine_cc_raw and str(engine_cc_raw).isdigit() else None

    return {
        "registration_number": reg_no,
        "maker_model": maker_model,
        "vehicle_make": vehicle_make,
        "vehicle_model": vehicle_model,
        "variant": variant,
        "vehicle_type": vehicle_type,
        "registration_date": reg_date,
        "manufacturing_month": mfg_month,
        "registration_year": reg_year,
        "fuel_type": fuel_type,
        "policy_expiry_date": expiry_formatted,
        "policy_status": policy_status,
        "owner_name": data.get("owner_name") or data.get("registered_owner") or data.get("owner"),
        "rto_code": data.get("rto_code") or data.get("rto"),
        "rto_name": data.get("rto_name") or data.get("registering_authority"),
        "engine_cc": engine_cc,
        "color": data.get("color") or data.get("colour"),
        "seating_capacity": str(data.get("seating_capacity")) if data.get("seating_capacity") else None,
        "raw_data": data
    }
