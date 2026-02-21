"""Tool definitions and execution for the AI assistant."""
import json
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.customers.models import Customer
from src.finances.models import CashBalance, Expense, IncomeEntry, Invoice
from src.kpis.models import KPISnapshot
from src.meetings.models import Meeting
from src.okrs.models import KeyResult, OKRPeriod, Objective
from src.prospects.models import Prospect
from src.tasks.models import Task
from src.vault.models import Credential

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_kpis",
            "description": "Get current KPI metrics: MRR, ARR, revenue, expenses, customers, burn rate, runway, tasks, prospects.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_customers",
            "description": "Query customers with optional filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status: active, churned, paused, trial"},
                    "search": {"type": "string", "description": "Search by company or contact name"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_income",
            "description": "Query income entries. Returns list of income records.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Filter by category"},
                    "limit": {"type": "integer", "description": "Max records to return (default 20)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_expenses",
            "description": "Query expenses with optional filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Filter by category"},
                    "paid_by": {"type": "string", "description": "Filter by who paid"},
                    "limit": {"type": "integer", "description": "Max records to return (default 20)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_prospects",
            "description": "Query sales prospects.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by pipeline status"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_tasks",
            "description": "Query tasks with optional filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "overdue_only": {"type": "boolean", "description": "Only return overdue tasks"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_meetings",
            "description": "Query meetings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "Filter by type: internal, prospect, customer, partner"},
                    "limit": {"type": "integer", "description": "Max records (default 10)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_vault_costs",
            "description": "Get service/tool cost summary from the vault (NO secrets, only costs).",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Filter by category"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_okrs",
            "description": "Get OKR objectives and key results for the active period.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_invoices",
            "description": "Query invoices.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status: draft, sent, paid, overdue, cancelled"},
                    "limit": {"type": "integer", "description": "Max records (default 20)"},
                },
            },
        },
    },
]


def _dec(v):
    """Convert Decimal to float for JSON serialization."""
    if isinstance(v, Decimal):
        return float(v)
    return v


async def execute_tool(name: str, args: dict, db: AsyncSession) -> str:
    """Execute a tool function and return JSON string result."""
    if name == "query_kpis":
        from datetime import date as date_type
        today = date_type.today()
        # MRR
        mrr_r = await db.execute(select(func.coalesce(func.sum(Customer.mrr_usd), 0)).where(Customer.status == "active"))
        mrr = float(mrr_r.scalar() or 0)
        # Revenue this month
        rev_r = await db.execute(
            select(func.coalesce(func.sum(IncomeEntry.amount_usd), 0))
            .where(func.extract("year", IncomeEntry.date) == today.year, func.extract("month", IncomeEntry.date) == today.month)
        )
        revenue = float(rev_r.scalar() or 0)
        # Expenses
        exp_r = await db.execute(select(func.coalesce(func.sum(Expense.amount_usd), 0)))
        expenses = float(exp_r.scalar() or 0)
        # Customers
        cust_r = await db.execute(select(func.count(Customer.id)).where(Customer.status == "active"))
        active_customers = cust_r.scalar() or 0
        # Cash
        cash_r = await db.execute(select(CashBalance).order_by(CashBalance.date.desc()).limit(1))
        cash = cash_r.scalar_one_or_none()
        return json.dumps({
            "mrr_usd": mrr, "arr_usd": mrr * 12, "revenue_this_month_usd": revenue,
            "total_expenses_usd": expenses, "net_profit_usd": revenue - expenses,
            "active_customers": active_customers, "arpu_usd": round(mrr / active_customers, 2) if active_customers else 0,
            "cash_balance_usd": float(cash.amount_usd) if cash else None,
        })

    elif name == "query_customers":
        q = select(Customer).order_by(Customer.created_at.desc()).limit(30)
        if args.get("status"):
            q = q.where(Customer.status == args["status"])
        if args.get("search"):
            q = q.where(Customer.company_name.ilike(f"%{args['search']}%"))
        result = await db.execute(q)
        customers = result.scalars().all()
        return json.dumps([
            {"company": c.company_name, "contact": c.contact_name, "status": c.status,
             "plan": c.plan_tier, "mrr": _dec(c.mrr), "currency": c.mrr_currency}
            for c in customers
        ])

    elif name == "query_income":
        q = select(IncomeEntry).order_by(IncomeEntry.date.desc()).limit(args.get("limit", 20))
        if args.get("category"):
            q = q.where(IncomeEntry.category == args["category"])
        result = await db.execute(q)
        items = result.scalars().all()
        return json.dumps([
            {"source": i.source, "description": i.description, "amount": _dec(i.amount),
             "currency": i.currency, "amount_usd": _dec(i.amount_usd), "date": str(i.date), "category": i.category}
            for i in items
        ])

    elif name == "query_expenses":
        q = select(Expense).order_by(Expense.date.desc()).limit(args.get("limit", 20))
        if args.get("category"):
            q = q.where(Expense.category == args["category"])
        if args.get("paid_by"):
            q = q.where(Expense.paid_by.ilike(f"%{args['paid_by']}%"))
        result = await db.execute(q)
        items = result.scalars().all()
        return json.dumps([
            {"name": e.name, "amount": _dec(e.amount), "currency": e.currency,
             "amount_usd": _dec(e.amount_usd), "category": e.category, "vendor": e.vendor,
             "date": str(e.date), "is_recurring": e.is_recurring}
            for e in items
        ])

    elif name == "query_prospects":
        q = select(Prospect).order_by(Prospect.created_at.desc()).limit(30)
        if args.get("status"):
            q = q.where(Prospect.status == args["status"])
        result = await db.execute(q)
        items = result.scalars().all()
        return json.dumps([
            {"company": p.company_name, "contact": p.contact_name, "status": p.status,
             "source": p.source, "estimated_mrr": _dec(p.estimated_mrr), "next_follow_up": str(p.next_follow_up) if p.next_follow_up else None}
            for p in items
        ])

    elif name == "query_tasks":
        from datetime import date
        q = select(Task).order_by(Task.created_at.desc()).limit(30)
        if args.get("overdue_only"):
            q = q.where(Task.due_date < date.today()).where(Task.due_date.isnot(None))
        result = await db.execute(q)
        items = result.scalars().all()
        return json.dumps([
            {"title": t.title, "priority": t.priority, "due_date": str(t.due_date) if t.due_date else None, "status": t.status}
            for t in items
        ])

    elif name == "query_meetings":
        q = select(Meeting).order_by(Meeting.date.desc()).limit(args.get("limit", 10))
        if args.get("type"):
            q = q.where(Meeting.type == args["type"])
        result = await db.execute(q)
        items = result.scalars().all()
        return json.dumps([
            {"title": m.title, "date": str(m.date), "type": m.type,
             "duration": m.duration_minutes, "attendees": m.attendees}
            for m in items
        ])

    elif name == "query_vault_costs":
        q = select(Credential).order_by(Credential.name)
        if args.get("category"):
            q = q.where(Credential.category == args["category"])
        result = await db.execute(q)
        items = result.scalars().all()
        total_usd = sum(_dec(c.monthly_cost_usd) or 0 for c in items)
        return json.dumps({
            "total_monthly_usd": total_usd,
            "services": [
                {"name": c.name, "category": c.category, "monthly_cost": _dec(c.monthly_cost),
                 "currency": c.cost_currency, "monthly_cost_usd": _dec(c.monthly_cost_usd)}
                for c in items
            ],
        })

    elif name == "query_okrs":
        from sqlalchemy.orm import selectinload
        result = await db.execute(
            select(OKRPeriod).where(OKRPeriod.status == "active")
            .options(selectinload(OKRPeriod.objectives).selectinload(Objective.key_results))
            .limit(1)
        )
        period = result.scalar_one_or_none()
        if not period:
            return json.dumps({"message": "No active OKR period found."})
        return json.dumps({
            "period": period.name,
            "objectives": [
                {
                    "title": o.title, "status": o.status,
                    "key_results": [
                        {"title": kr.title, "current": _dec(kr.current_value),
                         "target": _dec(kr.target_value), "unit": kr.unit, "progress": _dec(kr.progress_pct)}
                        for kr in o.key_results
                    ],
                }
                for o in period.objectives
            ],
        })

    elif name == "query_invoices":
        q = select(Invoice).order_by(Invoice.issue_date.desc()).limit(args.get("limit", 20))
        if args.get("status"):
            q = q.where(Invoice.status == args["status"])
        result = await db.execute(q)
        items = result.scalars().all()
        return json.dumps([
            {"number": i.invoice_number, "customer": i.customer_name, "total": _dec(i.total),
             "currency": i.currency, "status": i.status, "issue_date": str(i.issue_date), "due_date": str(i.due_date)}
            for i in items
        ])

    return json.dumps({"error": f"Unknown tool: {name}"})
