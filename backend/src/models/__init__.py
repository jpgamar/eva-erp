# Import all models here so Alembic can discover them.
#
# Tasks/Boards models removed in the empresas-ux-pass consolidation —
# the data lives in `empresa_items` now. Leaving the import here would
# fail at startup AND would block `alembic upgrade head` on deploy.
from src.auth.models import User  # noqa: F401
from src.notifications.models import Notification  # noqa: F401
from src.vault.models import VaultConfig, Credential, VaultAuditLog  # noqa: F401
from src.customers.models import Customer  # noqa: F401
from src.finances.models import (  # noqa: F401
    ExchangeRate,
    IncomeEntry,
    StripePaymentEvent,
    StripePayoutEvent,
    ManualDepositEntry,
    Expense,
    Invoice,
    CashBalance,
)
from src.kpis.models import KPISnapshot  # noqa: F401
from src.prospects.models import Prospect, ProspectInteraction  # noqa: F401
from src.meetings.models import Meeting  # noqa: F401
from src.documents.models import Folder, Document  # noqa: F401
from src.okrs.models import OKRPeriod, Objective, KeyResult  # noqa: F401
from src.assistant.models import AssistantConversation  # noqa: F401
from src.facturas.models import Factura  # noqa: F401
from src.eva_platform.drafts.models import AccountDraft  # noqa: F401
from src.eva_platform.pricing_models import AccountPricingProfile  # noqa: F401
from src.eva_billing.models import EvaBillingRecord  # noqa: F401
from src.empresas.models import (  # noqa: F401
    Empresa,
    EmpresaHistory,
    EmpresaInteraction,
    EmpresaItem,
    PaymentLink,
    ProspectEmpresaMap,
)
