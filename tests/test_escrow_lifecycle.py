from decimal import Decimal
from app.database import SessionLocal
from app.models.entities import Account, AccountType, EscrowOrder, EscrowStatus
from app.services.escrow_service import EscrowService


def test_release_escrow_settles_ledger_and_fees(db_session):
    # Setup de cuentas
    buyer = Account(account_type=AccountType.USER_WALLET, cached_balance=Decimal("100.0000"))
    seller = Account(account_type=AccountType.USER_WALLET, cached_balance=Decimal("0.0000"))
    vault = Account(account_type=AccountType.ESCROW_VAULT, cached_balance=Decimal("0.0000"))
    fee_collector = Account(account_type=AccountType.FEE_COLLECTOR, cached_balance=Decimal("0.0000"))
    
    db_session.add_all([buyer, seller, vault, fee_collector])
    db_session.commit()

    # Crear y fondear orden de 100 USDT
    order = EscrowOrder(
        buyer_account_id=buyer.id,
        seller_account_id=seller.id,
        vault_account_id=vault.id,
        amount=Decimal("100.0000"),
        status=EscrowStatus.CREATED
    )
    db_session.add(order)
    db_session.commit()

    EscrowService.fund_escrow(db_session, order.id, "fund-key-lifecycle-1")

    # Liberar fondos con 2% de comisión
    released_order = EscrowService.release_escrow(
        db=db_session,
        escrow_order_id=order.id,
        idempotency_key="release-key-lifecycle-1",
        fee_collector_account_id=fee_collector.id,
        fee_percentage=Decimal("0.02")
    )

    assert released_order.status == EscrowStatus.RELEASED

    # Verificación de saldos
    db_session.refresh(buyer)
    db_session.refresh(vault)
    db_session.refresh(seller)
    db_session.refresh(fee_collector)

    assert buyer.cached_balance == Decimal("0.0000")
    assert vault.cached_balance == Decimal("0.0000")
    assert seller.cached_balance == Decimal("98.0000")        # 100 - 2%
    assert fee_collector.cached_balance == Decimal("2.0000")  # 2% fee