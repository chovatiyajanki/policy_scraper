import asyncio
import json
from app.database import SessionLocal
from app.services.scraper import scrape_vehicle_policy
from app.models.policy import VehiclePolicy

async def test_full_scrape():
    db = SessionLocal()
    try:
        reg_no = "XX00XX0000"
        data = await scrape_vehicle_policy(reg_no)
        print("Scraped Data Result:\n", json.dumps({k: v for k, v in data.items() if k != "raw_data"}, indent=2))
        
        # Save to DB
        existing = db.query(VehiclePolicy).filter(VehiclePolicy.registration_number == data["registration_number"]).first()
        if not existing:
            rec = VehiclePolicy(**data)
            db.add(rec)
        else:
            for k, v in data.items():
                setattr(existing, k, v)
            rec = existing
        db.commit()
        db.refresh(rec)
        print(f"Successfully saved to PostgreSQL! ID: {rec.id}, Reg: {rec.registration_number}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_full_scrape())
