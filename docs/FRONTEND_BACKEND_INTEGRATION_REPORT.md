# Frontend-to-Backend Integration Audit & API Contract Report

**Document Reference:** `docs/FRONTEND_BACKEND_INTEGRATION_REPORT.md`  
**Platform Owner:** TechMasters Innovations Private Limited  
**Platform:** Bagodi E-Commerce Platform (Anchor Merchant: Bagodi, Bidar, Karnataka)  
**Phase:** 11 — End-to-End System Integration, Performance Benchmarking & Production Hardening  
**Date:** November 2026  
**Status:** Canonical Reference & Contract Audit  

---

## 1. Executive Summary

This report establishes the authoritative architectural boundary and integration contract between the **Bagodi Multi-Tenant Backend Engine** and the three frontend monorepo applications:
1. `frontend/apps/customer-web`: Mobile-first responsive web storefront for retail shoppers.
2. `frontend/apps/merchant-admin`: Operational dashboard for merchant store managers, catalogue managers, inventory clerks, and dispatch teams.
3. `frontend/apps/super-admin`: Platform governance dashboard for TechMasters Innovations platform engineers and administrators.

All backend APIs (131 OpenAPI operations across 12 domain modules) are 100% implemented, containerized, secured with tenant isolation and RBAC, and fully documented in `docs/openapi.json`. The three frontend applications are scaffolded with clean React 18, TypeScript, and Vite configurations, adhering strictly to the **Zero Dummy Data Policy**—displaying foundation shells rather than fabricated mock data until bound to authorized backend endpoints.

---

## 2. Global Integration & Communication Standards

### 2.1 Base URLs and API Versioning
All backend endpoints are versioned under the `/api/v1` namespace:
- **Local Development:** `http://localhost:8000/api/v1`
- **Staging / Sandbox:** `https://api.staging.bagodi.com/api/v1`
- **Production:** `https://api.bagodi.com/api/v1`

### 2.2 Authentication & Security Principal Headers
All authenticated API requests require standard RFC 6750 Bearer token authorization:
```http
Authorization: Bearer <access_token>
```
The backend `get_security_principal` dependency extracts the cryptographic JWT payload, verifying the signature, issuer, subject (`user_id`), expiration (`exp`), and tenant claims.

### 2.3 Tenant Context Propagation
- **Merchant & Delivery Requests:** For merchant-scoped endpoints (`/api/v1/merchant/...`) and delivery staff operations, the tenant context is derived directly from the authenticated user's assigned `tenant_id` claim inside the verified JWT.
- **Customer Storefront Requests:** Customers may supply the optional header `X-Tenant-ID: <uuid>` or store slug to scope catalog browsing to a specific merchant. If omitted, public endpoints resolve the default anchor merchant (Bagodi Bidar).
- **Security Rule:** Frontends must never attempt to spoof or override tenant identity. The backend strictly cross-checks JWT claims against path and payload tenant parameters; mismatches trigger `403 Forbidden` (`FORBIDDEN_CROSS_TENANT_ACCESS`).

### 2.4 Standard Error Response Schema
All error responses return a standardized JSON structure conforming to the backend exception handlers:
```json
{
  "error": "INSUFFICIENT_AVAILABLE_STOCK",
  "message": "Only 2 units available for variant 550e8400-e29b-41d4-a716-446655440000",
  "details": {
    "variant_id": "550e8400-e29b-41d4-a716-446655440000",
    "requested_quantity": 5,
    "available_quantity": 2
  }
}
```
Frontends must bind their toast, form validation, and error alert components directly to `response.data.message` and `response.data.error`.

### 2.5 Standard Pagination Format
All list endpoints support cursor- or limit-offset pagination:
- Request query parameters: `limit` (default: 20, max: 100), `offset` (default: 0).
- Response wrapper format:
```json
{
  "items": [...],
  "total": 142,
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```

---

## 3. Application 1: Customer Web Storefront (`customer-web`)

### 3.1 Overview
- **Path:** `frontend/apps/customer-web`
- **Target Audience:** Retail shoppers browsing products, placing orders, making payments, and tracking deliveries.
- **Zero Dummy Data Adherence:** Foundation shell loads without mock catalogue cards or fake pricing. Real products render dynamically only when fetched from `/api/v1/catalog/products`.

### 3.2 Endpoint Integration Matrix

| Customer Journey Stage | UI Screen / Component | HTTP Method & Path | Payload / Query | Response Type / Action |
| :--- | :--- | :--- | :--- | :--- |
| **Authentication** | Login Modal / Screen | `POST /api/v1/identity/auth/otp/request` | `{"phone": "+919876543210"}` | Triggers SMS OTP delivery. |
| | OTP Verification | `POST /api/v1/identity/auth/otp/verify` | `{"phone": "...", "otp_code": "123456"}` | Stores `access_token` and `refresh_token`. |
| | Token Refresh | `POST /api/v1/identity/auth/refresh` | `{"refresh_token": "..."}` | Rotates refresh token automatically on 401. |
| | User Profile | `GET /api/v1/identity/me` | None | Loads customer name, phone, email, and addresses. |
| **Catalog Browsing** | Categories Bar | `GET /api/v1/catalog/categories` | `?tenant_id=<id>` | Renders category tree and icons. |
| | Product Listing (PLP) | `GET /api/v1/catalog/products` | `?category_id=<id>&limit=20` | Renders product grid with active variants. |
| | Product Detail (PDP) | `GET /api/v1/catalog/products/{id}` | None | Loads variants, attributes, images, and descriptions. |
| | Real-Time Pricing | `GET /api/v1/pricing/products/{id}` | `?store_id=<id>` | Fetches live calculated price and discount badge. |
| **Cart Management** | Cart Drawer / Page | `GET /api/v1/customer/cart` | None | Displays persistent items, unit prices, and subtotals. |
| | Add Item to Cart | `POST /api/v1/customer/cart/items` | `{"variant_id": "...", "quantity": 1}` | Adds item or increments existing variant. |
| | Update Item Quantity | `PATCH /api/v1/customer/cart/items/{id}` | `{"quantity": 3}` | Updates quantity; validates stock on server. |
| | Remove Item | `DELETE /api/v1/customer/cart/items/{id}` | None | Removes item from persistent cart. |
| **Checkout & Pricing** | Coupon Input Box | `POST /api/v1/pricing/coupons/validate` | `{"coupon_code": "WELCOME10", "order_amount": 1200}` | Displays coupon discount breakdown. |
| | Delivery Estimate | `POST /api/v1/delivery/rates/calculate` | `{"delivery_pincode": "585401", "total_weight_kg": 1.2}` | Returns delivery fee and serviceability status. |
| | Submit Checkout | `POST /api/v1/customer/orders/checkout` | `{"cart_id": "...", "store_id": "...", "shipping_address": {...}, "payment_method": "ONLINE"}` | Atomically reserves stock and creates order in `PLACED` status. |
| **Payment Flow** | Payment Gateway Modal | `POST /api/v1/customer/payments/initiate` | `{"order_id": "...", "provider": "razorpay"}` | Returns gateway transaction ID and provider order token. |
| | Payment Verification | `POST /api/v1/customer/payments/{id}/verify` | `{"gateway_payment_id": "...", "gateway_signature": "..."}` | Captures payment and updates order to `CONFIRMED`. |
| **Order Tracking** | Order History | `GET /api/v1/customer/orders` | `?limit=10&offset=0` | Paginated list of customer orders with statuses. |
| | Order Detail | `GET /api/v1/customer/orders/{id}` | None | Full order snapshot, items, pricing, delivery status. |
| | Live Tracking | `GET /api/v1/customer/orders/{id}/tracking` | None | Courier checkpoints, live delivery stage, ETA. |
| | Cancel Order | `POST /api/v1/customer/orders/{id}/cancel` | `{"reason": "Changed mind"}` | Cancels order (if before dispatch) and triggers refund. |

---

## 4. Application 2: Merchant Operations Admin (`merchant-admin`)

### 4.1 Overview
- **Path:** `frontend/apps/merchant-admin`
- **Target Audience:** Store managers, inventory clerks, dispatch supervisors, and merchant administrators.
- **Tenant Scope:** Strictly isolated to the merchant tenant defined in the user's JWT. All data requests filter by `tenant_id`.

### 4.2 Endpoint Integration Matrix

| Functional Module | UI Screen / Component | HTTP Method & Path | Purpose & Action |
| :--- | :--- | :--- | :--- |
| **Store Management** | Store Selector / Settings | `GET /api/v1/merchant/stores` | Lists all retail fulfillment stores owned by merchant. |
| | Store Operating Hours | `PUT /api/v1/merchant/stores/{id}` | Updates operating hours, address, and dispatch settings. |
| **Catalogue & Variants** | Product Management Table | `GET /api/v1/merchant/catalog/products` | Lists products with variant count, SKU, and status. |
| | Create New Product | `POST /api/v1/merchant/catalog/products` | Creates parent product and base attributes. |
| | Variant & SKU Manager | `POST /api/v1/merchant/catalog/products/{id}/variants` | Configures variant attributes, SKU, and barcode. |
| | Publish / Archive Product| `PATCH /api/v1/merchant/catalog/products/{id}/status` | Toggles product visibility on public storefront. |
| **Inventory & Ledger** | Stock Balance Overview | `GET /api/v1/merchant/inventory/balances` | Displays On-Hand, Reserved, and Available stock per store. |
| | Stock Inwarding (PO) | `POST /api/v1/merchant/inventory/purchase-orders` | Creates purchase order for incoming supplier stock. |
| | Goods Inward Receipt | `POST /api/v1/merchant/inventory/purchase-orders/{id}/receipts` | Inwards stock; posts double-entry ledger transaction. |
| | Stock Adjustment / Waste | `POST /api/v1/merchant/inventory/adjustments` | Writes off damaged stock with immutable audit reason. |
| | Immutable Stock Ledger | `GET /api/v1/merchant/inventory/ledger` | Auditable log of all journal debits and credits. |
| **Pricing & Coupons** | Promotions Manager | `POST /api/v1/merchant/pricing/promotions` | Sets percentage or fixed promotional discounts. |
| | Coupon Codes Screen | `POST /api/v1/merchant/pricing/coupons` | Creates coupons with usage limits and expiry dates. |
| | Coupon Performance | `GET /api/v1/merchant/pricing/coupons` | Monitors redemption counts and remaining budget. |
| **Order Fulfillment** | Order Processing Queue | `GET /api/v1/merchant/orders` | Filters orders by status: `PLACED`, `CONFIRMED`, `PACKED`. |
| | Accept / Confirm Order | `POST /api/v1/merchant/orders/{id}/confirm` | Confirms order and generates picking slip. |
| | Mark Order Packed | `POST /api/v1/merchant/orders/{id}/pack` | Marks items packed and ready for carrier dispatch. |
| | Cancel / Reject Order | `POST /api/v1/merchant/orders/{id}/cancel` | Rejects order, releases stock reservation, voids payment. |
| **Logistics & Dispatch** | Dispatch & Assignment | `POST /api/v1/merchant/delivery/shipments` | Creates shipment; assigns internal staff or external courier. |
| | Internal Staff Manifest | `GET /api/v1/merchant/delivery/staff/manifests` | Lists shipments assigned to local Bidar bike riders. |
| | Courier Label Download | `GET /api/v1/merchant/delivery/shipments/{id}/label` | Downloads carrier shipping label PDF (Shiprocket). |
| | COD Cash Reconciliation | `POST /api/v1/merchant/delivery/reconcile-cod` | Confirms cash collected by delivery staff. |
| **Reports & Analytics** | Operations Dashboard | `GET /api/v1/merchant/reports/dashboard` | Sales, revenue, AOV, pending orders, and top products. |
| | Inventory Valuation | `GET /api/v1/merchant/reports/inventory-valuation` | Balance and asset valuation across store locations. |
| | Financial Reconciliation | `GET /api/v1/merchant/reports/financial-reconciliation` | Captured payments, gateway fees, refunds, and discrepancies. |
| | CSV Report Export | `GET /api/v1/merchant/reports/export/csv` | Streams RFC 4180 CSV export for external bookkeeping. |

---

## 5. Application 3: Platform Super Admin (`super-admin`)

### 5.1 Overview
- **Path:** `frontend/apps/super-admin`
- **Target Audience:** TechMasters Innovations platform operators and system administrators.
- **Permissions:** Restricted strictly to users holding the `SUPER_ADMIN` platform role.
- **Security Guard:** Cross-tenant boundary filters are bypassed only for system governance endpoints explicitly mounted under `/api/v1/platform/...`.

### 5.2 Endpoint Integration Matrix

| Governance Area | UI Screen / Component | HTTP Method & Path | Governance Action |
| :--- | :--- | :--- | :--- |
| **Tenant Onboarding** | Merchant Directory | `GET /api/v1/platform/tenants` | Lists all platform tenants, tier, domain, and status. |
| | Onboard New Merchant | `POST /api/v1/platform/tenants` | Provisions new merchant tenant, schema isolation, and admin user. |
| | Tenant Details & Audit | `GET /api/v1/platform/tenants/{id}` | Inspects merchant stores, user count, and activity log. |
| **Tenant Suspension** | Merchant Suspension Toggle | `POST /api/v1/platform/tenants/{id}/suspend` | Suspends merchant: immediately blocks logins and storefront checkouts. |
| | Tenant Reactivation | `POST /api/v1/platform/tenants/{id}/activate` | Restores suspended merchant to active operational status. |
| **System Operations** | Platform Macro Metrics | `GET /api/v1/platform/analytics/overview` | Platform-wide GMV, active merchant count, total orders. |
| | Outbox Queue Health | `GET /api/v1/platform/outbox/status` | Monitored backlog, dead-letter count, and dispatch latency. |
| | System Health Probes | `GET /api/v1/health/ready` | Verifies PostgreSQL connection pool and Redis cache health. |

---

## 6. Frontend Client Implementation Guidelines

To maintain architectural purity and avoid code duplication across the three frontend applications, the frontend engineering team must adhere to the following conventions:

### 6.1 Unified API Client Factory
All API calls must use an Axios or Fetch instance with standard request and response interceptors:
```typescript
import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true;
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        const res = await axios.post('/api/v1/identity/auth/refresh', { refresh_token: refreshToken });
        localStorage.setItem('access_token', res.data.access_token);
        localStorage.setItem('refresh_token', res.data.refresh_token);
        error.config.headers.Authorization = `Bearer ${res.data.access_token}`;
        return apiClient(error.config);
      } catch (refreshErr) {
        localStorage.clear();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);
```

### 6.2 Zero Dummy Data Enforcement
- Never write hardcoded placeholder arrays (e.g. `const mockProducts = [...]`) into component state.
- Always initialize component state with empty arrays (`[]`) and render accessible loading skeletons (e.g. `<SkeletonCard />`) while asynchronous backend queries are in-flight.
- If an API returns an empty array (`[]`), render an informative empty-state message (e.g., "No products available in this category yet").

---

## 7. Audit Conclusion & Readiness Status

1. **Backend API Readiness:** **100% Complete & Authoritative.** All 131 routes defined in `docs/openapi.json` are fully operational, tested against database isolation and security boundaries, and ready for frontend traffic.
2. **Frontend Applications:** **Foundation Complete.** Monorepo structure, build configurations, and foundation shells are established. Next phase of frontend engineering involves binding React view components to these endpoints according to the matrices detailed above.
