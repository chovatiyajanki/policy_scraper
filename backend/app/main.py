import sys
import asyncio
from contextlib import asynccontextmanager

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.api.policies import router as policies_router
from app.api.auth import router as auth_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure all tables exist on startup
    Base.metadata.create_all(bind=engine)
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            res = conn.execute(text(
                "SELECT indexdef FROM pg_indexes WHERE tablename = 'vehicle_policies' AND indexname = 'ix_vehicle_policies_registration_number'"
            )).scalar()
            if res and "UNIQUE" in res.upper():
                conn.execute(text("DROP INDEX IF EXISTS ix_vehicle_policies_registration_number;"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vehicle_policies_registration_number ON vehicle_policies (registration_number);"))
                conn.commit()
    except Exception as e:
        print(f"[DB Init Warning] Could not verify index: {e}")
    yield

app = FastAPI(
    title="Vehicle Policy Scraper API",
    description="High-performance scraper for Indian vehicle registration details, manufacturing info, and policy expiry dates.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(policies_router)

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Vehicle Policy Scraper API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}
