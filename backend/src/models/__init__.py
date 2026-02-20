# Import all models here so Alembic can discover them
from src.auth.models import User  # noqa: F401
from src.notifications.models import Notification  # noqa: F401
from src.vault.models import VaultConfig, Credential, VaultAuditLog  # noqa: F401
from src.tasks.models import Board, Column, Task, TaskComment, TaskActivity  # noqa: F401
from src.customers.models import Customer  # noqa: F401
from src.finances.models import ExchangeRate, IncomeEntry, Expense, Invoice, CashBalance  # noqa: F401
