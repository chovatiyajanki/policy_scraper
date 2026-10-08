import asyncio
from app.database import SessionLocal
from app.schemas.policy import PolicyScrapeRequest
from app.api.policies import scrape_and_save_policy

async def test_endpoint():
    db = SessionLocal()
    try:
        req = PolicyScrapeRequest(registration_number="XX00XX0000", force_refresh=True)
        res = await scrape_and_save_policy(req, db)
        print("Endpoint Success:", res.id, res.registration_number, res.vehicle_model)
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_endpoint())
