from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from fastapi.routing import APIRoute
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import require_agent_user
from src.auth.models import User
from src.common.database import get_db
from src.customers.router import create_customer as create_customer_core
from src.customers.schemas import CustomerCreate, CustomerResponse
from src.facturas.router import create_factura as create_factura_core
from src.facturas.router import list_facturas as list_facturas_core
from src.facturas.schemas import FacturaCreate, FacturaResponse

router = APIRouter(prefix="/agent", tags=["agent"])

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class CustomerFacturaWorkflowRequest(BaseModel):
    customer: CustomerCreate
    factura: FacturaCreate


class CustomerFacturaWorkflowResponse(BaseModel):
    customer: CustomerResponse
    factura: FacturaResponse


def _route_domain(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 3:
        return parts[2]
    if len(parts) >= 2:
        return parts[1]
    return "root"


@router.get("/capabilities")
async def capabilities(
    request: Request,
    user: User = Depends(require_agent_user),
):
    grouped: dict[str, list[dict]] = defaultdict(list)

    for route in request.app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/v1"):
            continue
        if route.path.startswith("/api/v1/agent"):
            continue

        methods = sorted(method for method in route.methods if method not in {"HEAD", "OPTIONS"})
        if not methods:
            continue

        grouped[_route_domain(route.path)].append(
            {
                "name": route.name,
                "path": route.path,
                "methods": methods,
                "mutating": any(method in MUTATING_METHODS for method in methods),
            }
        )

    domains = []
    for domain in sorted(grouped.keys()):
        routes = sorted(grouped[domain], key=lambda item: (item["path"], item["name"]))
        domains.append(
            {
                "domain": domain,
                "route_count": len(routes),
                "mutating_route_count": sum(1 for route in routes if route["mutating"]),
                "routes": routes,
            }
        )

    return {
        "mode": "agent",
        "actor_email": user.email,
        "summary": {
            "domains": len(domains),
            "routes": sum(domain["route_count"] for domain in domains),
            "mutating_routes": sum(domain["mutating_route_count"] for domain in domains),
        },
        "domains": domains,
    }


@router.get("/openapi")
async def openapi_spec(
    request: Request,
    _user: User = Depends(require_agent_user),
):
    return request.app.openapi()


@router.post("/customers", response_model=CustomerResponse, status_code=201)
async def agent_create_customer(
    data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_agent_user),
):
    return await create_customer_core(data=data, db=db, user=user)


@router.post("/facturas", response_model=FacturaResponse, status_code=201)
async def agent_create_factura(
    data: FacturaCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_agent_user),
):
    return await create_factura_core(data=data, db=db, user=user)


@router.get("/facturas", response_model=list[FacturaResponse])
async def agent_list_facturas(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_agent_user),
):
    return await list_facturas_core(status=status, db=db, user=user)


@router.post("/workflows/customer-factura", response_model=CustomerFacturaWorkflowResponse, status_code=201)
async def create_customer_and_factura(
    data: CustomerFacturaWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_agent_user),
):
    customer = await create_customer_core(data=data.customer, db=db, user=user)

    factura_payload = FacturaCreate(
        **{
            **data.factura.model_dump(),
            "customer_id": customer.id,
        }
    )
    factura = await create_factura_core(data=factura_payload, db=db, user=user)
    return CustomerFacturaWorkflowResponse(customer=customer, factura=factura)
