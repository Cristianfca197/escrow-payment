import uuid
from fastapi import APIRouter, Depends, Header, Path, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.escrow import EscrowOrderResponse
from app.services.escrow_service import EscrowService

router = APIRouter(prefix="/escrows", tags=["Escrows"])

@router.post(
    "/{escrow_id}/fund",
    response_model=EscrowOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Fondear orden de Escrow",
    description="Bloquea el saldo del comprador, fondea la bóveda de garantía y registra los asientos contables mediante Idempotency-Key."
)
def fund_escrow_endpoint(
    escrow_id: uuid.UUID = Path(..., description="UUID de la orden de Escrow"),
    idempotency_key: str = Header(
        ..., 
        alias="Idempotency-Key", 
        description="Clave única para garantizar idempotencia en la transacción"
    ),
    db: Session = Depends(get_db)
):
    return EscrowService.fund_escrow(
        db=db,
        escrow_order_id=escrow_id,
        idempotency_key=idempotency_key
    )

@router.post(
    "/{escrow_id}/release",
    response_model=EscrowOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Liberar fondos de Escrow al vendedor",
    description="Liquida la orden fondeada: acredita al vendedor descontando la comisión de la plataforma e impacta el libro mayor."
)
def release_escrow_endpoint(
    escrow_id: uuid.UUID = Path(..., description="UUID de la orden de Escrow"),
    fee_collector_account_id: uuid.UUID = Header(
        ..., 
        alias="X-Fee-Collector-ID",
        description="ID de la cuenta recolectora de comisiones"
    ),
    idempotency_key: str = Header(
        ..., 
        alias="Idempotency-Key", 
        description="Clave única para garantizar idempotencia"
    ),
    db: Session = Depends(get_db)
):
    return EscrowService.release_escrow(
        db=db,
        escrow_order_id=escrow_id,
        idempotency_key=idempotency_key,
        fee_collector_account_id=fee_collector_account_id
    )