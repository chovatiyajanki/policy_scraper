from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, UniqueConstraint, func
from app.database import Base

class VehiclePolicy(Base):
    __tablename__ = "vehicle_policies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    registration_number = Column(String(20), index=True, nullable=False)
    maker_model = Column(String(255), nullable=True)
    vehicle_make = Column(String(100), nullable=True)
    vehicle_model = Column(String(150), nullable=True)
    variant = Column(String(150), nullable=True)
    vehicle_type = Column(String(50), nullable=True)
    registration_date = Column(String(50), nullable=True)
    manufacturing_month = Column(String(50), nullable=True)
    registration_year = Column(Integer, nullable=True)
    fuel_type = Column(String(50), nullable=True)
    policy_expiry_date = Column(String(50), nullable=True)
    policy_status = Column(String(50), nullable=True)
    owner_name = Column(String(150), nullable=True)
    rto_code = Column(String(20), nullable=True)
    rto_name = Column(String(100), nullable=True)
    engine_cc = Column(Integer, nullable=True)
    color = Column(String(50), nullable=True)
    seating_capacity = Column(String(10), nullable=True)
    raw_data = Column(JSON, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "registration_number", name="uq_user_registration"),
    )
