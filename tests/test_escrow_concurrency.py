import uuid
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException
from app.database import SessionLocal
from app.models.entities import Account, AccountType, EscrowOrder, EscrowStatus
from app.services.escrow_service import EscrowService

def test_concurrent_funding_prevents_double_spending(db_session):
    # 1. Setup: Crear comprador con 100 USDT, vendedor y bóveda
    buyer = Account(
        account_type=AccountType.USER_WALLET,
        currency="USDT",
        cached_balance=Decimal("100.0000")
    )
    seller = Account(
        account_type=AccountType.USER_WALLET,
        currency="USDT",
        cached_balance=Decimal("0.0000")
    )
    vault = Account(
        account_type=AccountType.ESCROW_VAULT,
        currency="USDT",
        cached_balance=Decimal("0.0000")
    )
    db_session.add_all([buyer, seller, vault])
    db_session.commit()

    # 2. Crear dos órdenes de Escrow de 100 USDT cada una
    order_1 = EscrowOrder(
        buyer_account_id=buyer.id,
        seller_account_id=seller.id,
        vault_account_id=vault.id,
        amount=Decimal("100.0000"),
        status=EscrowStatus.CREATED
    )
    order_2 = EscrowOrder(
        buyer_account_id=buyer.id,
        seller_account_id=seller.id,
        vault_account_id=vault.id,
        amount=Decimal("100.0000"),
        status=EscrowStatus.CREATED
    )
    db_session.add_all([order_1, order_2])
    db_session.commit()

    # Función que corre en cada hilo con su propia sesión de DB
    def attempt_fund(order_id: uuid.UUID, key: str):
        session = SessionLocal()
        try:
            return EscrowService.fund_escrow(session, order_id, key)
        finally:
            session.close()

    # 3. Disparo concurrente con 2 hilos al mismo tiempo
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_1 = executor.submit(attempt_fund, order_1.id, "key-concurrente-1")
        future_2 = executor.submit(attempt_fund, order_2.id, "key-concurrente-2")

        res_1 = None
        res_2 = None
        exc_1 = None
        exc_2 = None

        try:
            res_1 = future_1.result()
        except HTTPException as e:
            exc_1 = e

        try:
            res_2 = future_2.result()
        except HTTPException as e:
            exc_2 = e

    # 4. Aserciones de consistencia
    # Exactamente una petición debe triunfar y la otra debe fallar con 400
    successes = [r for r in [res_1, res_2] if r is not None]
    failures = [e for e in [exc_1, exc_2] if e is not None]

    assert len(successes) == 1, "Solo una orden debió fondearse"
    assert len(failures) == 1, "La otra debió ser rechazada"
    assert failures[0].status_code == 400
    assert "Fondos insuficientes" in failures[0].detail

    # 5. Verificar que el saldo del comprador nunca sea negativo
    db_session.refresh(buyer)
    db_session.refresh(vault)
    assert buyer.cached_balance == Decimal("0.0000")
    assert vault.cached_balance == Decimal("100.0000")


def test_idempotent_reexecution_does_not_duplicate_charge(db_session):
    # Setup de cuenta con 100 USDT
    buyer = Account(account_type=AccountType.USER_WALLET, currency="USDT", cached_balance=Decimal("100.0000"))
    seller = Account(account_type=AccountType.USER_WALLET, currency="USDT", cached_balance=Decimal("0.0000"))
    vault = Account(account_type=AccountType.ESCROW_VAULT, currency="USDT", cached_balance=Decimal("0.0000"))
    db_session.add_all([buyer, seller, vault])
    db_session.commit()

    order = EscrowOrder(
        buyer_account_id=buyer.id,
        seller_account_id=seller.id,
        vault_account_id=vault.id,
        amount=Decimal("50.0000"),
        status=EscrowStatus.CREATED
    )
    db_session.add(order)
    db_session.commit()

    key = "idempotency-key-test-123"

    # Primera ejecución: exitosa
    res_first = EscrowService.fund_escrow(db_session, order.id, key)
    assert res_first.status == EscrowStatus.FUNDED

    # Reintento con la misma key: debe devolver la orden sin descontar de nuevo
    res_second = EscrowService.fund_escrow(db_session, order.id, key)
    assert res_second.id == order.id

    db_session.refresh(buyer)
    # Deben quedar 50 USDT exactos, no 0
    assert buyer.cached_balance == Decimal("50.0000")