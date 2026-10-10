import sys
import asyncio
import re
import json
import time
from datetime import datetime, date
from typing import Dict, Any, Optional, Tuple
import httpx
import urllib.parse

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

INSURER_MAP = {
    1: "Bajaj Allianz General Insurance",
    2: "ICICI Lombard General Insurance",
    3: "New India Assurance",
    4: "National Insurance",
    5: "HDFC ERGO General Insurance",
    6: "Tata AIG General Insurance",
    7: "United India Insurance",
    8: "Oriental Insurance",
    9: "IFFCO Tokio General Insurance",
    10: "Royal Sundaram General Insurance",
    11: "Reliance General Insurance",
    12: "SBI General Insurance",
    13: "Cholamandalam MS General Insurance",
    14: "Universal Sompo General Insurance",
    15: "Shriram General Insurance",
    16: "Bharti AXA General Insurance",
    17: "Future Generali India Insurance",
    22: "Reliance General Insurance",
    25: "Magma HDI General Insurance",
    27: "Kotak Mahindra General Insurance",
    30: "Liberty General Insurance",
    34: "Acko General Insurance",
    36: "Go Digit General Insurance",
    43: "Zuno General Insurance"
}

PB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.policybazaar.com/motor-insurance/car-insurance/",
    "Origin": "https://www.policybazaar.com",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "*/*"
}

# In-memory cache for PolicyBazaar Master Lists
_MASTER_CACHE = {
    "data": None,
    "last_fetched": 0
}

def format_registration_date(dt_str: Optional[str]) -> Optional[str]:
    """Formats '2025-12-20' or '20/12/2025' to '20 December, 2025'"""
    if not dt_str:
        return None
    dt_str = str(dt_str).strip()
    clean = dt_str.split("T")[0] if "T" in dt_str else dt_str
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            d = datetime.strptime(clean, fmt)
            return f"{d.day} {d.strftime('%B')}, {d.year}"
        except Exception:
            pass
    return dt_str

def format_manufacturing_month(dt_str: Optional[str]) -> Optional[str]:
    """Formats '2025-12-20' or '12/2025' to 'December-2025'"""
    if not dt_str:
        return None
    dt_str = str(dt_str).strip()
    clean = dt_str.split("T")[0] if "T" in dt_str else dt_str
    try:
        if "-" in clean and len(clean) >= 7:
            parts = clean.split("-")
            y, m = int(parts[0]), int(parts[1])
            if 1 <= m <= 12:
                return f"{MONTH_NAMES[m - 1]}-{y}"
        if "/" in clean:
            parts = clean.split("/")
            m, y = int(parts[0]), int(parts[1])
            if 1 <= m <= 12:
                return f"{MONTH_NAMES[m - 1]}-{y}"
    except Exception:
        pass
    return dt_str

def format_policy_expiry_date(dt_str: Optional[str]) -> Optional[str]:
    """Formats dates like '2026-12-15T00:00:00' or '2026-12-29' to '15-Dec-2026'"""
    if not dt_str:
        return None
    dt_str = str(dt_str).strip()
    if re.match(r'^\d{1,2}-[A-Za-z]{3}-\d{4}$', dt_str):
        try:
            d = datetime.strptime(dt_str, "%d-%b-%Y")
            return d.strftime("%d-%b-%Y")
        except Exception:
            return dt_str

    clean = dt_str.split("T")[0] if "T" in dt_str else dt_str
    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%d-%b-%Y",
        "%d %B %Y",
        "%d %B, %Y"
    ):
        try:
            d = datetime.strptime(clean, fmt)
            return d.strftime("%d-%b-%Y")
        except Exception:
            pass
    return dt_str

def determine_policy_status(expiry_str: Optional[str]) -> Optional[str]:
    if not expiry_str:
        return "Expired"
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

def calculate_days_remaining(expiry_str: Optional[str]) -> Tuple[Optional[int], Optional[str]]:
    if not expiry_str:
        return None, "Expiry Date Not Recorded"
    try:
        exp_date = datetime.strptime(expiry_str, "%d-%b-%Y").date()
        today = date.today()
        days_left = (exp_date - today).days
        if days_left < 0:
            return days_left, f"Expired {abs(days_left)} days ago"
        elif days_left == 0:
            return 0, "Expires today"
        else:
            return days_left, f"{days_left} days remaining"
    except Exception:
        return None, None

def calculate_vehicle_age(reg_date_str: Optional[str]) -> Optional[str]:
    if not reg_date_str:
        return None
    clean = str(reg_date_str).strip().split("T")[0]
    for fmt in ("%d %B, %Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            d = datetime.strptime(clean, fmt).date()
            today = date.today()
            total_months = (today.year - d.year) * 12 + (today.month - d.month)
            if total_months <= 0:
                return "Brand New (< 1 Month)"
            years = total_months // 12
            months = total_months % 12
            if years == 0:
                return f"{months} Months"
            elif months == 0:
                return f"{years} Years"
            else:
                return f"{years} Years, {months} Months"
        except Exception:
            pass
    return None

def determine_transmission(variant_name: Optional[str], spec: Dict[str, Any]) -> str:
    v_upper = (variant_name or "").upper()
    if any(k in v_upper for k in ["AMT", "AGS", "AT", "AUTOMATIC", "CVT", "DCT", "DSG", "TORQUE CONVERTER"]):
        return "Automatic"
    if "MT" in v_upper or "MANUAL" in v_upper:
        return "Manual"
    if spec.get("TransmissionType") == 1:
        return "Automatic"
    return "Manual"

def format_vehicle_class(pb_class: Optional[str]) -> str:
    if not pb_class:
        return "LMV (Light Motor Vehicle)"
    c = str(pb_class).strip().upper()
    if c == "LMV":
        return "LMV (Light Motor Vehicle)"
    elif c == "MCWG":
        return "Motorcycle with Gear"
    elif c == "MCWOG":
        return "Motorcycle without Gear"
    elif c == "HMV":
        return "Heavy Motor Vehicle"
    return c

def compute_original_expiry_date(reg_date_str: Optional[str], raw_insurance_upto: Optional[str] = None) -> Optional[str]:
    """Fallback calculation if explicit expiry is not available."""
    if raw_insurance_upto and str(raw_insurance_upto).strip():
        formatted = format_policy_expiry_date(str(raw_insurance_upto).strip())
        if formatted:
            return formatted

    if not reg_date_str:
        return None

    clean = str(reg_date_str).strip().split("T")[0]
    d = None
    for fmt in ("%d %B, %Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y"):
        try:
            d = datetime.strptime(clean, fmt).date()
            break
        except Exception:
            pass

    if not d:
        return None

    from datetime import timedelta
    today = date.today()
    try:
        anniv_this_year = date(today.year, d.month, d.day) - timedelta(days=1)
    except ValueError:
        anniv_this_year = date(today.year, d.month, 28)

    if anniv_this_year < today:
        days_past = (today - anniv_this_year).days
        if days_past <= 60:
            exp_date = anniv_this_year
        else:
            try:
                exp_date = date(today.year + 1, d.month, d.day) - timedelta(days=1)
            except ValueError:
                exp_date = date(today.year + 1, d.month, 28)
    else:
        exp_date = anniv_this_year

    return exp_date.strftime("%d-%b-%Y")

def _get_master_cache() -> Dict[str, Any]:
    """Fetches and caches PolicyBazaar masters for vehicle codes, variants, fuels, and RTOs."""
    now = time.time()
    if _MASTER_CACHE["data"] and (now - _MASTER_CACHE["last_fetched"] < 86400):
        return _MASTER_CACHE["data"]

    try:
        with httpx.Client(timeout=20.0) as client:
            payload = json.dumps([{"task": "getalllist"}])
            resp = client.post(
                "https://www.policybazaar.com/services/getcarservices_v2.php",
                headers=PB_HEADERS,
                data=payload
            )
            if resp.status_code == 200:
                master = resp.json()
                mmm = master.get("MakeModelMaster", [])

                by_veh_code = {}
                by_variant_id = {}
                by_make_model = {}
                for item in mmm:
                    vc = item.get("VehicleCode")
                    if vc:
                        by_veh_code[vc] = item
                    vid = item.get("VariantID")
                    if vid:
                        by_variant_id[vid] = item
                    k = (item.get("MakeID"), item.get("ModelID"))
                    if k not in by_make_model:
                        by_make_model[k] = item

                rto_master = {}
                for rto in master.get("RtoMaster", []):
                    c1 = rto.get("RtoId")
                    c2 = rto.get("AliasRegionCode")
                    if c1:
                        rto_master[str(c1).upper()] = rto
                    if c2:
                        rto_master[str(c2).upper()] = rto

                fuel_master = {
                    3: "CNG",
                    4: "Diesel",
                    5: "LPG",
                    7: "Petrol",
                    8: "LPG/Petrol",
                    9: "Electric",
                    99: "CNG"
                }
                for f in master.get("FuelMaster", []):
                    if f.get("FuelTypeID") and f.get("FuelName"):
                        fuel_master[f["FuelTypeID"]] = f["FuelName"]

                cached = {
                    "by_veh_code": by_veh_code,
                    "by_variant_id": by_variant_id,
                    "by_make_model": by_make_model,
                    "rto_master": rto_master,
                    "fuel_master": fuel_master
                }
                _MASTER_CACHE["data"] = cached
                _MASTER_CACHE["last_fetched"] = now
                return cached
    except Exception as e:
        print(f"[Scraper] Error fetching master cache: {e}")

    # Fallback to existing cache if refresh failed
    if _MASTER_CACHE["data"]:
        return _MASTER_CACHE["data"]

    return {
        "by_veh_code": {},
        "by_variant_id": {},
        "by_make_model": {},
        "rto_master": {},
        "fuel_master": {3: "CNG", 4: "Diesel", 5: "LPG", 7: "Petrol", 9: "Electric"}
    }

def _resolve_renewal_details(redirect_url: str) -> Dict[str, Any]:
    """
    For vehicles in renewal flow on PolicyBazaar, retrieves details directly via:
    1. Fast, headless-free HTTP extraction via CarDetails API (runs on any server/cloud VPS)
    2. Resilient multi-engine Playwright fallback
    """
    if not redirect_url:
        return {}

    # Method 1: Direct, ultra-fast HTTP request to PolicyBazaar CarDetails API
    try:
        parsed = urllib.parse.urlparse(redirect_url)
        qs = urllib.parse.parse_qs(parsed.query)
        enq_id = qs.get("id", [""])[0]
        enq_id2 = qs.get("id2", [""])[0]
        jt_data = qs.get("t", [""])[0]

        if enq_id and jt_data:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Referer": redirect_url,
                "Origin": "https://ci.policybazaar.com",
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "enquiryid": enq_id,
                "enquiryid2": enq_id2,
                "jtdata": jt_data
            }
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    "https://ci.policybazaar.com/carapi/Quote/CarDetails",
                    headers=headers,
                    json={"isInternalIP": False}
                )
                if resp.status_code == 200:
                    payload = resp.json()
                    cdata = payload.get("data")
                    if isinstance(cdata, dict) and (cdata.get("registrationDate") or cdata.get("makeModel")):
                        print("[Scraper] Successfully resolved renewal vehicle specs via direct HTTP CarDetails API.")
                        return cdata
    except Exception as e:
        print(f"[Scraper Direct HTTP Note]: {e}")

    # Method 2: Resilient Playwright browser fallback (works across Linux and Windows)
    renewal_data = {}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = None
            launch_attempts = [
                {"headless": True, "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]},
                {"headless": True, "channel": "chrome", "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]},
                {"headless": True, "channel": "chromium", "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]}
            ]
            for cfg in launch_attempts:
                try:
                    browser = p.chromium.launch(**cfg)
                    break
                except Exception:
                    continue

            if not browser:
                print("[Scraper Playwright] No supported browser engine found.")
                return {}

            context = browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            def on_resp(resp):
                url_lower = resp.url.lower()
                if "cardetails" in url_lower or "quotequestions" in url_lower:
                    try:
                        ct = resp.headers.get("content-type", "")
                        if "json" in ct:
                            d = resp.json()
                            if isinstance(d, dict) and d.get("data"):
                                cdata = d.get("data", {})
                                if isinstance(cdata, dict):
                                    renewal_data.update(cdata)
                    except Exception:
                        pass

            page.on("response", on_resp)
            try:
                page.goto(redirect_url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(4000)
            except Exception as e:
                print(f"[Scraper Renewal Playwright Note]: {e}")
            finally:
                browser.close()
    except Exception as e:
        print(f"[Scraper Playwright Exception]: {e}")

    return renewal_data

_resolve_renewal_via_playwright = _resolve_renewal_details

def scrape_vehicle_policy_sync(reg_no: str) -> Dict[str, Any]:
    """
    Direct, comprehensive, and authentic vehicle policy scraping pipeline from PolicyBazaar:
    Captures ALL vehicle and policy details present on PolicyBazaar.
    """
    cleaned_reg = re.sub(r'[^A-Za-z0-9]', '', reg_no).upper()
    print(f"[Scraper] Resolving vehicle and policy details for: {cleaned_reg}")

    master_cache = _get_master_cache()
    by_veh_code = master_cache["by_veh_code"]
    by_variant_id = master_cache["by_variant_id"]
    by_make_model = master_cache["by_make_model"]
    rto_master = master_cache["rto_master"]
    fuel_master = master_cache["fuel_master"]

    with httpx.Client(timeout=15.0) as client:
        # Step 1: Query VAHAN RC Details directly from PolicyBazaar
        rc_payload = json.dumps([{"task": "getrcdetails", "RegistrationNo": cleaned_reg}])
        r_rc = client.post(
            "https://www.policybazaar.com/services/getcarservices_v2.php",
            headers=PB_HEADERS,
            data=rc_payload
        )

        rc_data = {}
        if r_rc.status_code == 200:
            try:
                rc_json = r_rc.json()
                if isinstance(rc_json, dict):
                    rc_data = rc_json
            except Exception:
                pass

        is_empty_rc = (
            rc_data.get("MakeId", 0) == 0
            and rc_data.get("vehicleCode", 0) == 0
            and not rc_data.get("RegistrationYear")
            and not rc_data.get("RedirectUrl")
        )
        if not rc_data or is_empty_rc:
            raise ValueError(f"Vehicle '{cleaned_reg}' was not found in the national VAHAN registry on PolicyBazaar. Please check the registration number.")

        make_id = rc_data.get("MakeId")
        model_id = rc_data.get("ModelId")
        variant_id = rc_data.get("VariantId")
        veh_code = rc_data.get("vehicleCode")
        reg_date_raw = rc_data.get("RegistrationYear")
        rto_code = rc_data.get("rto") or (cleaned_reg[:4] if len(cleaned_reg) >= 4 else None)
        rto_id = rc_data.get("rtoId")
        fuel_id = rc_data.get("FuelTypeId")
        is_pvt = rc_data.get("isPvtVehicle", True)
        prev_insurer_id = rc_data.get("previousInsurerId")
        redirect_url = rc_data.get("RedirectUrl")

        # Step 2: Match with full master catalog
        spec = (
            by_veh_code.get(veh_code)
            or by_variant_id.get(variant_id)
            or by_make_model.get((make_id, model_id))
            or {}
        )

        make_name = spec.get("DisplayMakeName") or spec.get("MakeName")
        model_name = spec.get("ModelName")
        variant_name = spec.get("VariantName")
        engine_cc = spec.get("cubicCapacity")

        fuel_name = fuel_master.get(fuel_id) or (spec.get("FuelTypeID") and fuel_master.get(spec.get("FuelTypeID"))) or "Petrol"

        # Step 3: Extract authentic live policy expiry date via PolicyBazaar createEnquiry
        expiry_formatted = None
        enquiry_id = None
        if veh_code or reg_date_raw:
            enq_payload = json.dumps([{
                "task": "createEnquiry",
                "visitId": "2720610657",
                "utmTerm": "car-insurance",
                "utmSource": "",
                "utmMedium": "BU",
                "utmCampaign": "top-lead-form",
                "utmContent": "BU",
                "makeId": str(make_id or ""),
                "modelId": str(model_id or ""),
                "vehicleCode": str(veh_code or ""),
                "regDate": str(reg_date_raw or ""),
                "page_url": "https://www.policybazaar.com/motor-insurance/car-insurance/",
                "rtoId": rto_id or 0,
                "enquiryId": 0,
                "regNum": cleaned_reg,
                "PolicyType": 2,
                "fueltypevalue": str(fuel_id or ""),
                "leadSource": "PB",
                "isPvtVehicle": is_pvt
            }])
            try:
                r_enq = client.post(
                    "https://www.policybazaar.com/services/getcarservices_v2.php",
                    headers=PB_HEADERS,
                    data=enq_payload
                )
                if r_enq.status_code == 200 and r_enq.text.strip():
                    enq_resp = r_enq.json()
                    if isinstance(enq_resp, dict):
                        enquiry_id = enq_resp.get("enquiryId")
                        if enq_resp.get("policyExpDate"):
                            expiry_formatted = format_policy_expiry_date(enq_resp.get("policyExpDate"))
            except Exception as e:
                print(f"[Scraper Enquiry] Note: {e}")

        # Step 4: Handle renewal vehicles where specs are inside quotes redirect
        renewal_details = {}
        insurance_provider = None
        mfg_date_raw = rc_data.get("manufacturing_date") or rc_data.get("manufacturingDate")
        if (not make_name or not expiry_formatted or not reg_date_raw) and redirect_url:
            print(f"[Scraper] Resolving renewal vehicle via quotes redirect for {cleaned_reg}...")
            try:
                renewal_details = _resolve_renewal_via_playwright(redirect_url)
                if renewal_details:
                    pb_mm = renewal_details.get("makeModel")
                    if pb_mm:
                        parts = pb_mm.split(" ", 1)
                        if not make_name:
                            make_name = parts[0]
                        if not model_name:
                            model_name = parts[1] if len(parts) > 1 else parts[0]
                    if renewal_details.get("variant") and not variant_name:
                        variant_name = renewal_details.get("variant")
                    if renewal_details.get("policyExpiryDate") and not expiry_formatted:
                        expiry_formatted = format_policy_expiry_date(renewal_details.get("policyExpiryDate"))

                    # Extract Registration Date & Manufacturing Date from PolicyBazaar quotes
                    if renewal_details.get("registrationDate") and not reg_date_raw:
                        reg_date_raw = renewal_details.get("registrationDate")
                    if renewal_details.get("manufacturingDate"):
                        mfg_date_raw = renewal_details.get("manufacturingDate")

                    if renewal_details.get("cubicCapacity") and not engine_cc:
                        cc_digits = re.sub(r'[^0-9]', '', str(renewal_details.get("cubicCapacity")))
                        if cc_digits.isdigit():
                            engine_cc = int(cc_digits)

                    if renewal_details.get("existingInsurer"):
                        insurance_provider = renewal_details.get("existingInsurer")

                    if not engine_cc and model_name:
                        for item in by_make_model.values():
                            if str(item.get("ModelName", "")).lower() == model_name.lower():
                                engine_cc = item.get("cubicCapacity")
                                break
            except Exception as e:
                print(f"[Scraper Renewal Error]: {e}")

        # If mfg_date_raw is still missing, fallback to reg_date_raw
        if not mfg_date_raw:
            mfg_date_raw = reg_date_raw

        # Fallback expiry computation if API didn't return an explicit date
        if not expiry_formatted and reg_date_raw:
            expiry_formatted = compute_original_expiry_date(reg_date_raw)

        # Dates & Specifications
        reg_date_formatted = format_registration_date(reg_date_raw)
        mfg_month_formatted = format_manufacturing_month(mfg_date_raw)
        reg_year = None
        if reg_date_raw:
            clean_digits = re.sub(r'[^0-9]', '', str(reg_date_raw))
            if len(clean_digits) >= 4 and clean_digits[:4].isdigit():
                reg_year = int(clean_digits[:4])
        if not reg_year and renewal_details.get("registrationYear"):
            try:
                reg_year = int(renewal_details.get("registrationYear"))
            except Exception:
                pass

        # Build full maker model title
        title_components = [c for c in [make_name, model_name, variant_name] if c]
        if title_components:
            maker_model = " ".join(title_components)
        else:
            maker_model = f"Vehicle {cleaned_reg}"

        # Vehicle Type
        vehicle_type = "Private" if is_pvt else "Commercial"

        # Policy Status & Days countdown
        policy_status = determine_policy_status(expiry_formatted)
        days_left, days_status_text = calculate_days_remaining(expiry_formatted)
        vehicle_age = calculate_vehicle_age(reg_date_formatted or reg_date_raw)

        # RTO Authority
        rto_info = rto_master.get(str(rto_code).upper(), {}) if rto_code else {}
        rto_city = rto_info.get("CityName")
        rto_state = rto_info.get("StateName")
        if rto_city and rto_state:
            rto_name = f"{rto_city}, {rto_state}"
        elif rto_info.get("rtoLongName"):
            rto_name = rto_info.get("rtoLongName")
        elif rto_code:
            rto_name = f"RTO {rto_code}"
        else:
            rto_name = None

        transmission = determine_transmission(variant_name, spec)
        vehicle_class = format_vehicle_class(rc_data.get("PbVehClass"))
        if not insurance_provider:
            insurance_provider = INSURER_MAP.get(prev_insurer_id, "IRDAI Registered Insurer" if prev_insurer_id else None)
        policy_type = "Comprehensive (Own Damage + Third Party)" if is_pvt else "Commercial Motor Policy"

        # Comprehensive PolicyBazaar scraped metadata
        pb_scraped_metadata = {
            "make_id": make_id,
            "model_id": model_id,
            "variant_id": variant_id,
            "vehicle_code": veh_code,
            "rto_id": rto_id,
            "previous_insurer_id": prev_insurer_id,
            "previous_insurer": insurance_provider,
            "insurance_provider": insurance_provider,
            "transmission": transmission,
            "vehicle_class": vehicle_class,
            "is_bh_series": bool(rc_data.get("isBHRegNumber")),
            "vehicle_source": rc_data.get("source") or "VAHAN Official",
            "make_logo": spec.get("MakeLogo") or renewal_details.get("makeIcon"),
            "model_image": spec.get("ModelImage"),
            "policy_type": policy_type,
            "vehicle_age": vehicle_age,
            "days_remaining": days_left,
            "days_status_text": days_status_text,
            "rto_city": rto_city,
            "rto_state": rto_state,
            "rto_full_name": rto_info.get("rtoLongName") or rto_name,
            "is_popular_model": bool(spec.get("IsPopularModel")),
            "is_popular_variant": bool(spec.get("IsPopularVariant")),
            "enquiry_id": enquiry_id or rc_data.get("EnquiryId"),
            "power": spec.get("power"),
            "cubic_capacity": engine_cc,
            "renewal_idv": (renewal_details.get("previousPolicyDetails") or {}).get("renewalIdv"),
            "previous_policy_details": renewal_details.get("previousPolicyDetails"),
            "od_expiry_date": renewal_details.get("odExpiryDate"),
            "tp_expiry_date": renewal_details.get("tpExpiryDate")
        }

        return {
            "registration_number": cleaned_reg,
            "maker_model": maker_model.strip(),
            "vehicle_make": make_name,
            "vehicle_model": model_name or maker_model.strip(),
            "variant": variant_name,
            "vehicle_type": vehicle_type,
            "registration_date": reg_date_formatted,
            "manufacturing_month": mfg_month_formatted,
            "registration_year": reg_year,
            "fuel_type": fuel_name,
            "policy_expiry_date": expiry_formatted,
            "policy_status": policy_status,
            "owner_name": rc_data.get("owner_name") or renewal_details.get("ownerName"),
            "rto_code": rto_code,
            "rto_name": rto_name,
            "engine_cc": engine_cc,
            "color": rc_data.get("color") or renewal_details.get("color"),
            "seating_capacity": str(rc_data.get("seating_capacity") or "5"),
            "raw_data": {
                "rc": rc_data,
                "spec": spec,
                "renewal": renewal_details,
                "previous_insurer": insurance_provider,
                "pb_metadata": pb_scraped_metadata
            }
        }

async def scrape_vehicle_policy(reg_no: str) -> Dict[str, Any]:
    """Async entry point safe for ASGI / FastAPI."""
    return await asyncio.to_thread(scrape_vehicle_policy_sync, reg_no)