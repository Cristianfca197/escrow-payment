import uuid
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.entities import EscrowStatus

class EscrowOrderResponse(BaseModel):
    id: uuid.UUID
    buyer_account_id: uuid.UUID
    seller_account_id: uuid.UUID
    vault_account_id: uuid.UUID
    amount: Decimal = Field(..., ge=Decimal("0.01"), decimal_places=4)
    status: EscrowStatus
    created_at: datetime

    class Config:
        from_attributes = True