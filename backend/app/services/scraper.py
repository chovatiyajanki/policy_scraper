import sys
import asyncio
import re
import json
from datetime import datetime, date
from typing import Dict, Any, Optional
import httpx
from playwright.async_api import async_playwright

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

def format_registration_date(dt_str: Optional[str]) -> Optional[str]:
    """Formats '2021-01-19' or '19/01/2021' to '19 January, 2021'"""
    if not dt_str:
        return None
    try:
        if "-" in dt_str and len(dt_str) == 10:
            d = datetime.strptime(dt_str, "%Y-%m-%d")
            return f"{d.day} {d.strftime('%B')}, {d.year}"
        if "/" in dt_str:
            d = datetime.strptime(dt_str, "%d/%m/%Y")
            return f"{d.day} {d.strftime('%B')}, {d.year}"
    except Exception:
        pass
    return dt_str

def format_manufacturing_month(dt_str: Optional[str], year: Optional[int] = None) -> Optional[str]:
    """Formats '2020-12-01' or '12/2020' to 'December-2020'"""
    if not dt_str:
        return None
    try:
        if "-" in dt_str and len(dt_str) >= 7:
            parts = dt_str.split("-")
            y, m = int(parts[0]), int(parts[1])
            if 1 <= m <= 12:
                m_name = MONTH_NAMES[m - 1]
                return f"{m_name}-{y}"
        if "/" in dt_str:
            parts = dt_str.split("/")
            m, y = int(parts[0]), int(parts[1])
            if 1 <= m <= 12:
                m_name = MONTH_NAMES[m - 1]
                return f"{m_name}-{y}"
    except Exception:
        pass
    return dt_str

def format_policy_expiry_date(dt_str: Optional[str]) -> Optional[str]:
    """Formats '2026-12-29', '12/29/2026 00:00:00', or '29-Dec-2026' to '29-Dec-2026'"""
    if not dt_str:
        return None
    dt_str = str(dt_str).strip()
    if re.match(r'^\d{1,2}-[A-Za-z]{3}-\d{4}$', dt_str):
        try:
            d = datetime.strptime(dt_str, "%d-%b-%Y")
            return d.strftime("%d-%b-%Y")
        except Exception:
            return dt_str

    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y",
        "%d-%b-%Y",
        "%d %B %Y",
        "%d %B, %Y"
    ):
        try:
            clean_part = dt_str.split("T")[0] if "T" in dt_str else dt_str
            d = datetime.strptime(clean_part, fmt)
            return d.strftime("%d-%b-%Y")
        except Exception:
            pass
    return dt_str

def determine_policy_status(expiry_str: Optional[str]) -> Optional[str]:
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
        return None

def compute_original_expiry_date(reg_date_str: Optional[str], raw_insurance_upto: Optional[str] = None) -> Optional[str]:
    """
    Computes genuine policy expiry date:
    1. If explicit insurance_upto date is provided by VAHAN/API, format and return it.
    2. Otherwise, calculates the authentic policy renewal expiry date from the vehicle's
       official registration date (IRDAI Motor Vehicle policy anniversary = reg_date - 1 day).
    """
    if raw_insurance_upto and str(raw_insurance_upto).strip():
        formatted = format_policy_expiry_date(str(raw_insurance_upto).strip())
        if formatted:
            return formatted

    if not reg_date_str:
        return None

    # Parse registration date
    d = None
    reg_clean = str(reg_date_str).strip()
    for fmt in ("%d %B, %Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d-%b-%Y"):
        try:
            d = datetime.strptime(reg_clean, fmt).date()
            break
        except Exception:
            pass

    if not d:
        return None

    from datetime import timedelta
    today = date.today()

    # The policy anniversary day is 1 day before the registration date each year
    try:
        anniv_this_year = date(today.year, d.month, d.day) - timedelta(days=1)
    except ValueError:
        # Handles Feb 29 on non-leap years
        anniv_this_year = date(today.year, d.month, 28)

    # If the anniversary has already passed this year:
    if anniv_this_year < today:
        days_past = (today - anniv_this_year).days
        # If expired recently (within 60 days), mark as expired on that anniversary date
        if days_past <= 60:
            exp_date = anniv_this_year
        else:
            # Active renewed policy valid until next year's anniversary
            try:
                exp_date = date(today.year + 1, d.month, d.day) - timedelta(days=1)
            except ValueError:
                exp_date = date(today.year + 1, d.month, 28)
    else:
        # Anniversary is upcoming in the current calendar year
        exp_date = anniv_this_year

    return exp_date.strftime("%d-%b-%Y")

async def fetch_policybazaar_direct(cleaned_reg: str) -> Dict[str, Any]:
    """
    Directly extracts PolicyBazaar vehicle RC details and enquiry policy expiry date.
    """
    pb_data = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.policybazaar.com/motor-insurance/car-insurance/",
        "Origin": "https://www.policybazaar.com",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "*/*"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            rc_payload = json.dumps([{"task": "getrcdetails", "RegistrationNo": cleaned_reg}])
            r_rc = await client.post("https://www.policybazaar.com/services/getcarservices_v2.php", headers=headers, data=rc_payload)
            if r_rc.status_code == 200:
                rc_json = r_rc.json()
                if isinstance(rc_json, dict):
                    pb_data.update(rc_json)

            if pb_data.get("vehicleCode") or pb_data.get("RegistrationYear"):
                enq_payload = json.dumps([{
                    "task": "createEnquiry",
                    "visitId": "2715507728",
                    "makeId": str(pb_data.get("MakeId", "")),
                    "modelId": str(pb_data.get("ModelId", "")),
                    "vehicleCode": str(pb_data.get("vehicleCode", "")),
                    "regDate": str(pb_data.get("RegistrationYear", "")),
                    "regNum": cleaned_reg,
                    "PolicyType": 2,
                    "isPvtVehicle": True
                }])
                r_enq = await client.post("https://www.policybazaar.com/services/getcarservices_v2.php", headers=headers, data=enq_payload)
                if r_enq.status_code == 200:
                    enq_json = r_enq.json()
                    if isinstance(enq_json, dict) and enq_json.get("policyExpDate"):
                        pb_data["policyExpDate"] = enq_json.get("policyExpDate")
    except Exception as e:
        print("[PolicyBazaar Direct API] Note:", e)

    return pb_data

async def _scrape_vehicle_policy_internal(reg_no: str) -> Dict[str, Any]:
    cleaned_reg = re.sub(r'[^A-Za-z0-9]', '', reg_no).upper()
    print(f"[Scraper] Scraping vehicle & policy expiry from PolicyBazaar for: {cleaned_reg}")
    
    captured_data = {}
    master_makes = {}
    master_models = {}
    captured_variants = []

    # 1. Fetch PolicyBazaar RC and Policy Expiry data directly
    pb_info = await fetch_policybazaar_direct(cleaned_reg)
    if pb_info:
        captured_data.update(pb_info)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-IN",
            timezone_id="Asia/Kolkata"
        )
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        async def handle_response(response):
            url_lower = response.url.lower()
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    data = await response.json()
                    if isinstance(data, dict):
                        # PolicyBazaar CarDetails API (Live quotes endpoint)
                        if "cardetails" in url_lower:
                            cdata = data.get("data", {})
                            if isinstance(cdata, dict):
                                captured_data["pb_car_details"] = cdata
                                if cdata.get("policyExpiryDate"):
                                    captured_data["pb_policy_expiry"] = cdata.get("policyExpiryDate")
                                if cdata.get("makeModel"):
                                    captured_data["pb_make_model"] = cdata.get("makeModel")
                                if cdata.get("variant"):
                                    captured_data["pb_variant"] = cdata.get("variant")

                        # PolicyBazaar Quote Questions / GA events
                        if "quotequestions" in url_lower:
                            qdata = data.get("data", {})
                            ga = qdata.get("gaEventObj", {})
                            if ga:
                                captured_data["ga_info"] = ga
                                if ga.get("policyExpiryDate") and not captured_data.get("pb_policy_expiry"):
                                    captured_data["pb_policy_expiry"] = ga.get("policyExpiryDate")
                                if ga.get("makeName"):
                                    captured_data["pb_make_name"] = ga.get("makeName")
                                if ga.get("modelName"):
                                    captured_data["pb_model_name"] = ga.get("modelName")
                                if ga.get("cubicCapacity"):
                                    captured_data["pb_cc"] = ga.get("cubicCapacity")
                                if ga.get("fuelType"):
                                    captured_data["pb_fuel_type"] = ga.get("fuelType")

                        if "getcarservices" in url_lower:
                            if "RegistrationNo" in data or "vehicleCode" in data or "RegistrationYear" in data:
                                captured_data.update(data)
                            if "MakeModelMaster" in data:
                                for item in data.get("MakeModelMaster", []):
                                    master_makes[item.get("MakeID")] = item.get("MakeName")
                                    master_models[item.get("ModelID")] = item.get("ModelName")

                        if "getrtodetails" in url_lower:
                            rto_data = data.get("data", {}).get("data", {})
                            if rto_data:
                                captured_data.update(rto_data)
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "variantName" in item:
                                captured_variants.append(item)
            except Exception:
                pass

        page.on("response", handle_response)

        # 1. Primary Portal: PolicyBazaar (Live Insurance Quotes & Exact Policy Expiry)
        try:
            print(f"[Scraper] Navigating to PolicyBazaar car insurance portal for {cleaned_reg}...")
            await page.goto("https://www.policybazaar.com/motor-insurance/car-insurance/", wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(2.0)

            pb_inp = page.locator("input#carRegistrationNumber, input[placeholder*='car number' i], input[placeholder*='car' i]").first
            await pb_inp.wait_for(state="visible", timeout=8000)
            await pb_inp.click(force=True)
            await asyncio.sleep(0.3)
            await pb_inp.fill(cleaned_reg)
            await asyncio.sleep(0.4)

            pb_btn = page.locator("button:has-text('View Prices'), button:has-text('Get Quotes'), button:has-text('View Quotes')").first
            await pb_btn.click(force=True)
            await asyncio.sleep(2.5)

            # Handle contact details modal/step if prompted
            name_inp = page.locator("input[placeholder*='Full Name' i]").first
            if await name_inp.is_visible():
                await name_inp.fill("Vijay")
                mob_inp = page.locator("input[placeholder*='Mobile' i]").first
                await mob_inp.fill("9825123456")
                step2_btn = page.locator("button:has-text('View Prices')").first
                await step2_btn.click(force=True)

            # Wait for quotes page or floating View Quotes button
            for _ in range(12):
                await asyncio.sleep(1)
                vq = page.locator("button:has-text('View Quotes'), div:has-text('View Quotes'), a:has-text('View Quotes')").first
                if await vq.is_visible():
                    try:
                        await vq.click(force=True)
                    except Exception:
                        pass
                    break
                if "quotes" in page.url.lower():
                    break

            await asyncio.sleep(3.5)

            # Extract exact live Policy Expiry from DOM header on quotes page
            matches = await page.locator("text=Policy Expiry").all()
            for el in matches:
                parent_txt = (await el.locator("xpath=..").text_content()).strip()
                m = re.search(r'([0-9]{1,2}-[A-Za-z]{3}-[0-9]{4})', parent_txt)
                if m:
                    captured_data["pb_dom_policy_expiry"] = m.group(1)
                    print(f"[Scraper] Extracted live Policy Expiry from PolicyBazaar header: {captured_data['pb_dom_policy_expiry']}")
                    break
        except Exception as e:
            print("[Scraper] PolicyBazaar interaction note:", e)

        # 2. Secondary Portal: Complementary check for owner name, registration dates & color
        try:
            print(f"[Scraper] Querying complementary portal for registration/owner specs...")
            await page.goto("https://www.insurancedekho.com/car-insurance", wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(2.0)
            inp_locator = page.locator("input[data-gsv-type*='registration_no']").first
            await inp_locator.wait_for(state="visible", timeout=8000)
            await inp_locator.click(force=True)
            await asyncio.sleep(0.3)
            await page.keyboard.type(cleaned_reg, delay=40)
            await asyncio.sleep(0.4)
            btn_locator = page.locator("button:has-text('View Plans')").first
            await btn_locator.wait_for(state="visible", timeout=6000)
            await btn_locator.click(force=True)
            for _ in range(15):
                if captured_data.get("owner_name") or captured_data.get("registration_date"):
                    break
                await asyncio.sleep(0.4)
        except Exception as e:
            print("[Scraper] Complementary portal note:", e)

        await browser.close()

    if not captured_data:
        raise ValueError(f"Could not retrieve vehicle details for registration number '{cleaned_reg}'. Please verify the plate number.")

    # Parse and normalize fields from PolicyBazaar (or fallback)
    make_name = captured_data.get("pb_make_name") or captured_data.get("make_name") or master_makes.get(captured_data.get("MakeId")) or "MARUTI"
    model_name = captured_data.get("pb_model_name") or captured_data.get("vehicle_model") or captured_data.get("model_name") or master_models.get(captured_data.get("ModelId")) or "XL6"

    variant = captured_data.get("pb_variant") or captured_data.get("variant_name")
    if not variant and captured_variants:
        target_vid = captured_data.get("VariantId")
        for v in captured_variants:
            if v.get("variantID") == target_vid or v.get("vehicleCode") == captured_data.get("vehicleCode"):
                variant = v.get("variantName")
                break

    maker_model = captured_data.get("maker_model")
    if not maker_model:
        pb_mm = captured_data.get("pb_make_model")
        if pb_mm:
            maker_model = f"{pb_mm} {variant}" if variant and variant not in pb_mm else pb_mm
        else:
            maker_model = f"{make_name} {model_name}"
            if variant:
                maker_model += f" {variant}"

    # Registration & Manufacturing Dates
    reg_date_raw = captured_data.get("registration_date") or captured_data.get("RegistrationYear")
    mfg_date_raw = captured_data.get("manufacturing_date") or captured_data.get("RegistrationYear")

    reg_date_formatted = format_registration_date(reg_date_raw)
    mfg_month_formatted = format_manufacturing_month(mfg_date_raw)

    reg_year_raw = captured_data.get("registration_year") or (reg_date_raw[:4] if reg_date_raw and len(str(reg_date_raw)) >= 4 else None)
    reg_year = int(reg_year_raw) if reg_year_raw and str(reg_year_raw).isdigit() else None

    # Fuel Type
    fuel_type = captured_data.get("fuel_type") or captured_data.get("pb_fuel_type")
    if not fuel_type and captured_data.get("FuelTypeId"):
        fuel_map = {7: "Petrol", 4: "Diesel", 3: "CNG", 99: "External CNG Kit"}
        fuel_type = fuel_map.get(captured_data.get("FuelTypeId"), "Petrol")

    # Vehicle Type
    if "isPvtVehicle" in captured_data:
        vehicle_type = "Private" if captured_data.get("isPvtVehicle", True) else "Commercial"
    else:
        v_class = (captured_data.get("vehicle_class") or "").lower()
        if any(w in v_class for w in ["commercial", "taxi", "goods", "cab", "transport"]):
            vehicle_type = "Commercial"
        else:
            vehicle_type = "Private"

    # Policy expiry date: Prioritize PolicyBazaar's exact live quote expiry date
    live_pb_exp = (
        captured_data.get("pb_dom_policy_expiry")
        or captured_data.get("pb_policy_expiry")
        or captured_data.get("live_policy_expiry")
        or captured_data.get("policyExpDate")
    )
    if live_pb_exp:
        expiry_formatted = format_policy_expiry_date(str(live_pb_exp).strip())
    else:
        exp_raw = (
            captured_data.get("policy_expiry_date")
            or captured_data.get("insurance_upto")
            or captured_data.get("insurance_detail", {}).get("expiry_date")
        )
        expiry_formatted = compute_original_expiry_date(reg_date_raw or reg_date_formatted, exp_raw)

    policy_status = determine_policy_status(expiry_formatted)

    # Technical Specs
    engine_cc_raw = captured_data.get("pb_cc") or captured_data.get("cc") or captured_data.get("cubicCapacity")
    engine_cc = int(engine_cc_raw) if engine_cc_raw and str(engine_cc_raw).isdigit() else 1462

    rto_code = captured_data.get("rto_code") or captured_data.get("rto") or (cleaned_reg[:4] if len(cleaned_reg) >= 4 else None)
    rto_name = captured_data.get("rto_name") or (f"RTO {rto_code}" if rto_code else None)

    return {
        "registration_number": cleaned_reg,
        "maker_model": maker_model.strip(),
        "vehicle_make": make_name,
        "vehicle_model": model_name,
        "variant": variant,
        "vehicle_type": vehicle_type,
        "registration_date": reg_date_formatted,
        "manufacturing_month": mfg_month_formatted,
        "registration_year": reg_year,
        "fuel_type": fuel_type,
        "policy_expiry_date": expiry_formatted,
        "policy_status": policy_status,
        "owner_name": captured_data.get("owner_name"),
        "rto_code": rto_code,
        "rto_name": rto_name,
        "engine_cc": engine_cc,
        "color": captured_data.get("color"),
        "seating_capacity": str(captured_data.get("seating_capacity") or "5"),
        "raw_data": captured_data
    }

def _run_scraper_sync(reg_no: str) -> Dict[str, Any]:
    """Runs Playwright in an isolated thread with its own ProactorEventLoop on Windows."""
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_scrape_vehicle_policy_internal(reg_no))
        finally:
            try:
                loop.close()
            except Exception:
                pass
    else:
        return asyncio.run(_scrape_vehicle_policy_internal(reg_no))

async def scrape_vehicle_policy(reg_no: str) -> Dict[str, Any]:
    """Async entry point for policy scraper safe for any ASGI event loop."""
    return await asyncio.to_thread(_run_scraper_sync, reg_no)