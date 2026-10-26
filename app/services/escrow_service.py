import uuid
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.entities import (
    EscrowOrder,
    EscrowStatus,
    Account,
    Transaction,
    LedgerEntry,
)

class EscrowService:
    @staticmethod
    def fund_escrow(
        db: Session, 
        escrow_order_id: uuid.UUID, 
        idempotency_key: str
    ) -> EscrowOrder:
        """
        Fondea una orden de Escrow bloqueando el saldo del comprador y 
        transfiriéndolo a la bóveda mediante partida doble inmutable.
        """
        
        # 1. Chequeo de Idempotencia (¿Ya procesamos esta petición exacta?)
        existing_tx = db.execute(
            select(Transaction).where(Transaction.idempotency_key == idempotency_key)
        ).scalar_one_or_none()

        if existing_tx:
            # Si la transacción ya existe, devolvemos el estado actual sin reejecutar lógica
            return db.execute(
                select(EscrowOrder).where(EscrowOrder.id == existing_tx.escrow_order_id)
            ).scalar_one()

        # Iniciamos el bloque atómico
        try:
            # 2. Validar que la orden existe y puede ser fondeada
            order = db.execute(
                select(EscrowOrder).where(EscrowOrder.id == escrow_order_id)
            ).scalar_one_or_none()

            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, 
                    detail="Orden de Escrow no encontrada"
                )

            if order.status != EscrowStatus.CREATED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"La orden no puede fondearse en su estado actual: {order.status.value}"
                )

            amount_to_fund: Decimal = Decimal(str(order.amount))

            # 3. Adquirir Locks exclusivos (SELECT ... FOR UPDATE) ordenados por ID para evitar Deadlocks
            account_ids = sorted([order.buyer_account_id, order.vault_account_id])
            
            locked_accounts = db.execute(
                select(Account)
                .where(Account.id.in_(account_ids))
                .order_by(Account.id.asc())
                .with_for_update()
            ).scalars().all()

            accounts_map = {acc.id: acc for acc in locked_accounts}
            buyer_acc = accounts_map.get(order.buyer_account_id)
            vault_acc = accounts_map.get(order.vault_account_id)

            if not buyer_acc or not vault_acc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Cuentas asociadas a la orden no encontradas"
                )

            # 4. Validar saldo disponible del comprador
            if buyer_acc.cached_balance < amount_to_fund:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Fondos insuficientes. Saldo actual: {buyer_acc.cached_balance}, Requerido: {amount_to_fund}"
                )

            # 5. Crear la cabecera de la Transacción con su Idempotency Key
            tx = Transaction(
                escrow_order_id=order.id,
                idempotency_key=idempotency_key,
                description=f"Fondeo de orden Escrow {order.id}"
            )
            db.add(tx)
            db.flush()  # Genera el tx.id necesario para las foreign keys sin comitear aún

            # 6. Generar Asientos Contables de Partida Doble (Suma neta == 0)
            debit_entry = LedgerEntry(
                transaction_id=tx.id,
                account_id=buyer_acc.id,
                amount=-amount_to_fund  # Débito
            )
            credit_entry = LedgerEntry(
                transaction_id=tx.id,
                account_id=vault_acc.id,
                amount=amount_to_fund   # Crédito
            )
            db.add_all([debit_entry, credit_entry])

            # 7. Actualizar saldos cacheados
            buyer_acc.cached_balance -= amount_to_fund
            vault_acc.cached_balance += amount_to_fund

            # 8. Transición de Estado de la Orden
            order.status = EscrowStatus.FUNDED

            # 9. Commit atómico de todos los cambios
            db.commit()
            db.refresh(order)
            return order

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno al procesar fondeo: {str(e)}"
            )