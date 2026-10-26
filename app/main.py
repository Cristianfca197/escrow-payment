from fastapi import FastAPI
from app.api.v1.endpoints import escrow

app = FastAPI(
    title="Escrow Payment Gateway API",
    description="Motor de pagos, retención de fondos y libro mayor de partida doble.",
    version="0.1.0"
)

app.include_router(escrow.router, prefix="/api/v1")

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "escrow-gateway"}