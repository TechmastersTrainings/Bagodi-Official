import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.modules.catalog.router_barcode import router as barcode_router
from app.modules.catalog.router_merchant import router as merchant_catalog_router
from app.modules.catalog.router_platform import router as platform_catalog_router
from app.modules.catalog.router_public import router as public_catalog_router, storefront_router
from app.modules.delivery.router_customer import router as delivery_customer_router
from app.modules.delivery.router_delivery_staff import router as delivery_staff_router
from app.modules.delivery.router_merchant import router as delivery_merchant_router
from app.modules.delivery.router_public import router as delivery_public_router
from app.modules.health.router import router as health_router
from app.modules.identity.router import router as auth_router
from app.modules.identity.router_addresses import router as customer_addresses_router
from app.modules.identity.router_merchant_users import router as merchant_users_router
from app.modules.inventory.router import router as inventory_router
from app.modules.inventory.router_direct import router as inventory_direct_router
from app.modules.notifications.router_customer import router as notifications_customer_router
from app.modules.notifications.router_merchant import router as notifications_merchant_router
from app.modules.notifications.router_webhooks import router as notifications_webhooks_router
from app.modules.orders.router_cart import router as cart_router
from app.modules.orders.router_orders_customer import router as orders_customer_router, customer_orders_router
from app.modules.orders.router_orders_merchant import router as orders_merchant_router
from app.modules.orders.router_returns import router as returns_router
from app.modules.payments.router_customer import router as payments_customer_router
from app.modules.payments.router_merchant import router as payments_merchant_router
from app.modules.payments.router_webhooks import router as payments_webhooks_router
from app.modules.platform.router_platform import router as platform_router
from app.modules.platform.router_stores import router as stores_router
from app.modules.platform.router_super import router as super_router
from app.modules.pricing.router_customer import router as pricing_customer_router
from app.modules.pricing.router_merchant import router as pricing_merchant_router
from app.modules.reports.router_merchant import router as reports_merchant_router
from app.modules.reports.router_platform import router as reports_platform_router
from app.modules.reports.router_reports import router as reports_gateway_router
from app.modules.media.router import router as media_router

logger = logging.getLogger("bagodi.platform")
settings = get_settings()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


from app.db.ensure_seeds import ensure_foundational_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_production_configuration()
    await ensure_foundational_data()
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
    description="Bagodi multi-tenant retail e-commerce platform API",
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)

# Explicitly configured origins for customer storefront, merchant portal, super admin, and apex/subdomain web properties
EXPLICIT_CORS_ORIGINS = [
    "https://bagodi.in",
    "https://www.bagodi.in",
    "https://merchant.bagodi.in",
    "https://admin.bagodi.in",
    "https://superadmin.bagodi.in",
    "https://bagodi-merchant.vercel.app",
    "https://bagodi-super-admin.vercel.app",
    "https://bagodi-store.vercel.app",
    "https://bagodi.vercel.app",
    "http://bagodi.in",
    "http://www.bagodi.in",
    "http://merchant.bagodi.in",
    "http://admin.bagodi.in",
]

all_cors_origins = list(dict.fromkeys(EXPLICIT_CORS_ORIGINS + settings.cors_origin_list))

app.add_middleware(
    CORSMiddleware,
    allow_origins=all_cors_origins,
    allow_origin_regex=r"https?://(.*\.)?(bagodi\.in|vercel\.app)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Content-Type", "Authorization"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    try:
        raw_body = await request.body()
        body_preview = raw_body.decode("utf-8", errors="replace")[:1000]
    except Exception:
        body_preview = "<could not read body>"
    logger.warning(
        "RequestValidationError [%s] %s %s: errors=%s headers=%s body=%s",
        request_id,
        request.method,
        request.url,
        exc.errors(),
        dict(request.headers),
        body_preview,
    )
    # Format user-friendly error message
    error_messages = []
    for err in exc.errors():
        loc = ".".join(str(l) for l in err.get("loc", []) if l != "body")
        msg = err.get("msg", "Invalid field")
        error_messages.append(f"{loc}: {msg}" if loc else msg)
    message = "; ".join(error_messages) or "Invalid request payload"

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "VALIDATION_ERROR",
            "message": message,
            "details": {"errors": exc.errors()},
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id} if request_id else None,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", f"HTTP_{exc.status_code}")
        message = exc.detail.get("message", "Request failed")
        details = exc.detail.get("details")
    else:
        code = f"HTTP_{exc.status_code}"
        message = str(exc.detail) if exc.detail else "Request failed"
        details = None

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id} if request_id else None,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.error("Unhandled exception for request %s: %s", request_id, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred while processing the request.",
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id} if request_id else None,
    )


app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(merchant_users_router, prefix=settings.api_v1_prefix)
app.include_router(customer_addresses_router, prefix=settings.api_v1_prefix)
app.include_router(platform_router, prefix=settings.api_v1_prefix)
app.include_router(super_router, prefix=settings.api_v1_prefix)
app.include_router(platform_catalog_router, prefix=settings.api_v1_prefix)
app.include_router(stores_router, prefix=settings.api_v1_prefix)
app.include_router(merchant_catalog_router, prefix=settings.api_v1_prefix)
app.include_router(public_catalog_router, prefix=settings.api_v1_prefix)
app.include_router(storefront_router, prefix=settings.api_v1_prefix)
app.include_router(barcode_router, prefix=settings.api_v1_prefix)
app.include_router(inventory_router, prefix=settings.api_v1_prefix)
app.include_router(inventory_direct_router, prefix=settings.api_v1_prefix)
app.include_router(cart_router, prefix=settings.api_v1_prefix)
app.include_router(orders_customer_router, prefix=settings.api_v1_prefix)
app.include_router(customer_orders_router, prefix=settings.api_v1_prefix)
app.include_router(orders_merchant_router, prefix=settings.api_v1_prefix)
app.include_router(returns_router, prefix=settings.api_v1_prefix)
app.include_router(pricing_merchant_router, prefix=settings.api_v1_prefix)
app.include_router(pricing_customer_router, prefix=settings.api_v1_prefix)
app.include_router(payments_customer_router, prefix=settings.api_v1_prefix)
app.include_router(payments_merchant_router, prefix=settings.api_v1_prefix)
app.include_router(payments_webhooks_router, prefix=settings.api_v1_prefix)
app.include_router(notifications_customer_router, prefix=settings.api_v1_prefix)
app.include_router(notifications_merchant_router, prefix=settings.api_v1_prefix)
app.include_router(notifications_webhooks_router, prefix=settings.api_v1_prefix)
app.include_router(delivery_public_router, prefix=settings.api_v1_prefix)
app.include_router(delivery_customer_router, prefix=settings.api_v1_prefix)
app.include_router(delivery_staff_router, prefix=settings.api_v1_prefix)
app.include_router(delivery_merchant_router, prefix=settings.api_v1_prefix)
app.include_router(reports_merchant_router, prefix=settings.api_v1_prefix)
app.include_router(reports_platform_router, prefix=settings.api_v1_prefix)
app.include_router(reports_gateway_router, prefix=settings.api_v1_prefix)
app.include_router(media_router, prefix=settings.api_v1_prefix)
