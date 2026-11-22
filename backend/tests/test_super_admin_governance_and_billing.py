import uuid
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from app.db.session import engine


@pytest.mark.asyncio
async def test_complete_super_admin_governance_and_billing_lifecycle(client: AsyncClient, mint_jwt_token):
    """
    Milestone 5 End-to-End Test:
    Validates complete TechMasters Super Admin / Platform Governance & Multi-Tenant Management:
    1. Super Admin Authentication & Staff RBAC Delegation
    2. Tenant Onboarding with Business Details & Initial Subscription
    3. KYC Document Management: Upload, Rejection, and Verification
    4. Tenant Lifecycle: Suspension with Audit Reason, Re-activation, and History Logs
    5. Subscription Plans, Billing Invoices, and Payment Settlement
    6. Platform-Wide Overview & Merchant Comparative Analytics
    7. Global Administrative Audit Logging
    8. System Diagnostics, Pool Health & Outbox Queue Monitoring
    """
    # 1. Super Admin Setup
    super_admin_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (:id, '+919999900001', 'superadmin@platform.internal', 'Platform SuperAdmin', 'active', true, now(), now()) "
                "ON CONFLICT DO NOTHING"
            ),
            {"id": super_admin_id},
        )

    admin_token = mint_jwt_token(
        user_id=super_admin_id,
        is_platform_user=True,
        permissions=["platform.*", "reports:read"],
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Staff RBAC Delegation: Create Compliance Officer
    compliance_user_id = uuid.uuid4()
    staff_resp = await client.post(
        "/api/v1/platform/staff",
        json={
            "phone_e164": "+919999900002",
            "email": "compliance@platform.internal",
            "display_name": "Radha Sharma",
            "role_code": "COMPLIANCE_OFFICER",
        },
        headers=admin_headers,
    )
    assert staff_resp.status_code == 201, staff_resp.text
    staff_data = staff_resp.json()
    assert staff_data["is_platform_user"] is True
    assert "COMPLIANCE_OFFICER" in staff_data["roles"]

    # List Staff
    staff_list_resp = await client.get("/api/v1/platform/staff", headers=admin_headers)
    assert staff_list_resp.status_code == 200
    assert any(s["phone_e164"] == "+919999900002" for s in staff_list_resp.json())

    # 3. Seed Subscription Plans & List Plans
    plans_resp = await client.get("/api/v1/platform/billing/plans", headers=admin_headers)
    assert plans_resp.status_code == 200
    plans = plans_resp.json()
    assert len(plans) >= 3
    starter_plan = next((p for p in plans if p["code"] == "STARTER"), plans[0])
    growth_plan = next((p for p in plans if p["code"] == "GROWTH_RETAIL"), plans[1])

    # 4. Merchant Tenant Onboarding
    tenant_slug = f"bidar-heritage-silks-{uuid.uuid4().hex[:6]}"
    onboard_resp = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Bidar Heritage Silks",
            "slug": tenant_slug,
            "legal_name": "Bidar Heritage Handloom Private Limited",
            "contact_email": "management@bidarsilks.in",
            "contact_phone": "+919845012345",
            "business_type": "PRIVATE_LIMITED",
            "pan_number": "AABCB1234C",
            "gstin": "29AABCB1234C1Z5",
            "registered_address": "Fort View Complex, Gandhi Circle, Bidar, Karnataka 585401",
            "initial_plan_code": "GROWTH_RETAIL",
        },
        headers=admin_headers,
    )
    assert onboard_resp.status_code == 201, onboard_resp.text
    tenant = onboard_resp.json()
    tenant_id = tenant["id"]
    assert tenant["status"] == "pending"
    assert tenant["business_type"] == "PRIVATE_LIMITED"
    assert tenant["gstin"] == "29AABCB1234C1Z5"

    # 5. KYC Document Management: Upload Documents
    # Doc 1: GST Certificate
    gst_doc_resp = await client.post(
        f"/api/v1/platform/tenants/{tenant_id}/kyc-documents",
        json={
            "document_type": "GST_CERTIFICATE",
            "document_number": "29AABCB1234C1Z5",
            "document_url": "https://storage.bagodi.in/kyc/gst_cert_bidarsilks.pdf",
            "file_name": "gst_cert_bidarsilks.pdf",
            "file_size_bytes": 245000,
        },
        headers=admin_headers,
    )
    assert gst_doc_resp.status_code == 201, gst_doc_resp.text
    gst_doc_id = gst_doc_resp.json()["id"]

    # Doc 2: PAN Card
    pan_doc_resp = await client.post(
        f"/api/v1/platform/tenants/{tenant_id}/kyc-documents",
        json={
            "document_type": "PAN_CARD",
            "document_number": "AABCB1234C",
            "document_url": "https://storage.bagodi.in/kyc/pan_card_bidarsilks.pdf",
            "file_name": "pan_card_bidarsilks.pdf",
            "file_size_bytes": 180000,
        },
        headers=admin_headers,
    )
    assert pan_doc_resp.status_code == 201, pan_doc_resp.text
    pan_doc_id = pan_doc_resp.json()["id"]

    # KYC List
    kyc_list_resp = await client.get(
        f"/api/v1/platform/tenants/{tenant_id}/kyc-documents",
        headers=admin_headers,
    )
    assert kyc_list_resp.status_code == 200
    assert len(kyc_list_resp.json()) == 2

    # Reject PAN Card initially (e.g. blurry image)
    reject_resp = await client.post(
        f"/api/v1/platform/tenants/{tenant_id}/kyc-documents/{pan_doc_id}/review",
        json={
            "status": "REJECTED",
            "rejection_reason": "Image scan is blurred; company seal not visible",
        },
        headers=admin_headers,
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "REJECTED"

    # Re-verify PAN Card after clear upload
    verify_pan_resp = await client.post(
        f"/api/v1/platform/tenants/{tenant_id}/kyc-documents/{pan_doc_id}/review",
        json={"status": "VERIFIED"},
        headers=admin_headers,
    )
    assert verify_pan_resp.status_code == 200
    assert verify_pan_resp.json()["status"] == "VERIFIED"

    # Verify GST Certificate
    verify_gst_resp = await client.post(
        f"/api/v1/platform/tenants/{tenant_id}/kyc-documents/{gst_doc_id}/review",
        json={"status": "VERIFIED"},
        headers=admin_headers,
    )
    assert verify_gst_resp.status_code == 200
    assert verify_gst_resp.json()["status"] == "VERIFIED"

    # 6. Tenant Activation
    activate_resp = await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/status",
        json={
            "status": "active",
            "reason": "Full KYC documentation verified and approved by compliance team",
        },
        headers=admin_headers,
    )
    assert activate_resp.status_code == 200
    assert activate_resp.json()["status"] == "active"
    assert activate_resp.json()["kyc_status"] == "VERIFIED"

    # 7. Tenant Suspension & Reactivation Lifecycle History
    suspend_resp = await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/status",
        json={
            "status": "suspended",
            "reason": "Temporary suspension pending updated shop & establishment license renewal",
        },
        headers=admin_headers,
    )
    assert suspend_resp.status_code == 200
    assert suspend_resp.json()["status"] == "suspended"

    # Re-activate
    reactivate_resp = await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/status",
        json={
            "status": "active",
            "reason": "Shop establishment certificate renewal submitted and confirmed",
        },
        headers=admin_headers,
    )
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["status"] == "active"

    # Check Lifecycle Logs
    lifecycle_resp = await client.get(
        f"/api/v1/platform/tenants/{tenant_id}/lifecycle-logs",
        headers=admin_headers,
    )
    assert lifecycle_resp.status_code == 200
    logs = lifecycle_resp.json()
    assert len(logs) >= 3
    assert any(l["new_status"] == "suspended" for l in logs)
    assert any(l["new_status"] == "active" for l in logs)

    # 8. Subscription Management & Merchant Invoicing
    # Upgrade subscription to Omnichannel Enterprise
    enterprise_plan = next((p for p in plans if p["code"] == "ENTERPRISE_FLAGSHIP"), plans[-1])
    assign_resp = await client.post(
        f"/api/v1/platform/billing/subscriptions/assign?tenant_id={tenant_id}",
        json={"plan_id": enterprise_plan["id"], "auto_renew": True},
        headers=admin_headers,
    )
    assert assign_resp.status_code == 200, assign_resp.text
    active_sub = assign_resp.json()
    assert active_sub["status"] == "ACTIVE"

    # Generate Merchant Invoice
    invoice_resp = await client.post(
        "/api/v1/platform/billing/invoices",
        json={
            "tenant_id": tenant_id,
            "subscription_id": active_sub["id"],
            "billing_period_start": "2026-11-01",
            "billing_period_end": "2026-11-30",
            "amount": "19999.00",
            "tax_amount": "3599.82",
            "total_amount": "23598.82",
            "due_date": "2026-11-15",
            "line_items": [
                {
                    "description": "Omnichannel Enterprise Platform Tier (November 2026)",
                    "amount": "19999.00",
                },
                {
                    "description": "GST @ 18% (CGST 9% + SGST 9%)",
                    "amount": "3599.82",
                },
            ],
        },
        headers=admin_headers,
    )
    assert invoice_resp.status_code == 201, invoice_resp.text
    invoice_id = invoice_resp.json()["id"]
    assert invoice_resp.json()["status"] == "PENDING"

    # Settle / Pay Invoice
    pay_resp = await client.patch(
        f"/api/v1/platform/billing/invoices/{invoice_id}/pay",
        json={"payment_reference": "HDFC-NEFT-20261110-09876"},
        headers=admin_headers,
    )
    assert pay_resp.status_code == 200
    assert pay_resp.json()["status"] == "PAID"
    assert pay_resp.json()["payment_reference"] == "HDFC-NEFT-20261110-09876"

    # 9. Global Administrative Audit Logs
    audit_resp = await client.get("/api/v1/platform/audit-logs", headers=admin_headers)
    assert audit_resp.status_code == 200
    audit_events = audit_resp.json()
    assert len(audit_events) >= 5
    actions = [e["action"] for e in audit_events]
    assert "TENANT_ONBOARDED" in actions
    assert "KYC_DOCUMENT_UPLOADED" in actions
    assert "TENANT_SUSPENDED" in actions
    assert "MERCHANT_INVOICE_PAID" in actions

    # 10. System Health & Outbox Diagnostics
    health_resp = await client.get("/api/v1/platform/system/health", headers=admin_headers)
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["status"] == "HEALTHY"
    assert health_data["database"] == "CONNECTED"
    assert health_data["active_tenants"] >= 1

    # Outbox Queue
    outbox_resp = await client.get("/api/v1/platform/system/outbox", headers=admin_headers)
    assert outbox_resp.status_code == 200
    assert isinstance(outbox_resp.json(), list)

    # Trigger manual outbox process
    worker_resp = await client.post("/api/v1/platform/system/outbox/process", headers=admin_headers)
    assert worker_resp.status_code == 200
    assert "processed" in worker_resp.json()

    # 11. Platform Analytics Overview
    overview_resp = await client.get("/api/v1/platform/reports/overview", headers=admin_headers)
    assert overview_resp.status_code == 200
    overview_data = overview_resp.json()
    assert overview_data["total_active_tenants"] >= 1
    assert "tenants" in overview_data

    print("\n✅ MILESTONE 5 SUPER ADMIN & PLATFORM GOVERNANCE WORKFLOW VERIFIED SUCCESSFULLY!")

