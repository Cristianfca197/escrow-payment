import enum
import uuid
from sqlalchemy import Column, String, Numeric, ForeignKey, Enum, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base

class EscrowStatus(str, enum.Enum):
    CREATED = "CREATED"
    FUNDED = "FUNDED"
    RELEASED = "RELEASED"
    REFUNDED = "REFUNDED"

class AccountType(str, enum.Enum):
    USER_WALLET = "USER_WALLET"
    ESCROW_VAULT = "ESCROW_VAULT"
    FEE_COLLECTOR = "FEE_COLLECTOR"

class Account(Base):
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)  # Nullable para cuentas internas
    account_type = Column(Enum(AccountType), nullable=False)
    currency = Column(String(10), nullable=False, default="USDT")
    cached_balance = Column(Numeric(18, 4), nullable=False, default=0.0000)

    __table_args__ = (
        CheckConstraint("cached_balance >= 0", name="check_positive_balance"),
    )

class EscrowOrder(Base):
    __tablename__ = "escrow_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    buyer_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    seller_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    vault_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    amount = Column(Numeric(18, 4), nullable=False)
    status = Column(Enum(EscrowStatus), nullable=False, default=EscrowStatus.CREATED)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    escrow_order_id = Column(UUID(as_uuid=True), ForeignKey("escrow_orders.id"), nullable=False)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    amount = Column(Numeric(18, 4), nullable=False)  # Negativo = Débito, Positivo = Crédito
    created_at = Column(DateTime(timezone=True), server_default=func.now())