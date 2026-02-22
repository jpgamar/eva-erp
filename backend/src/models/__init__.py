# Import all models here so Alembic can discover them
from src.auth.models import User  # noqa: F401
from src.notifications.models import Notification  # noqa: F401
from src.vault.models import VaultConfig, Credential, VaultAuditLog  # noqa: F401
from src.tasks.models import Board, Task, TaskComment  # noqa: F401
from src.customers.models import Customer  # noqa: F401
from src.finances.models import ExchangeRate, IncomeEntry, Expense, Invoice, CashBalance  # noqa: F401
from src.kpis.models import KPISnapshot  # noqa: F401
from src.prospects.models import Prospect, ProspectInteraction  # noqa: F401
from src.meetings.models import Meeting  # noqa: F401
from src.documents.models import Folder, Document  # noqa: F401
from src.okrs.models import OKRPeriod, Objective, KeyResult  # noqa: F401
from src.assistant.models import AssistantConversation  # noqa: F401
from src.facturas.models import Factura  # noqa: F401
from src.eva_platform.drafts.models import AccountDraft  # noqa: F401
