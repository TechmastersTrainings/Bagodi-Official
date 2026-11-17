export type RoleType =
  | "SUPER_ADMIN"
  | "COMPLIANCE_OFFICER"
  | "FINANCE_CONTROLLER"
  | "SUPPORT_OPERATOR";

export interface PlatformUser {
  id: string;
  phone_e164: string | null;
  email: string | null;
  display_name: string | null;
  status: "active" | "suspended";
  is_platform_user: boolean;
  roles: string[];
  created_at: string;
}

export interface AllPlatformUser {
  id: string;
  phone_e164: string | null;
  email: string | null;
  display_name: string | null;
  status: string;
  is_platform_user: boolean;
  tenant_id: string | null;
  tenant_name: string | null;
  roles: string[];
  created_at: string;
}

export interface AdminProduct {
  id: string;
  tenant_id: string;
  category_id: string;
  brand_id: string | null;
  name: string;
  slug: string;
  description: string | null;
  status: string;
  is_published: boolean;
  variants: Array<{
    id: string;
    sku: string;
    size: string | null;
    base_price: string | number;
    mrp: string | number;
    available_qty?: number;
    status: string;
  }>;
  images: Array<{
    id: string;
    url: string;
    alt_text: string | null;
    is_primary: boolean;
  }>;
  created_at: string;
}

export interface AdminOrder {
  id: string;
  order_number: string;
  tenant_id: string;
  customer_id?: string | null;
  total_amount: string | number;
  subtotal_amount: string | number;
  delivery_fee: string | number;
  discount_amount: string | number;
  status: string;
  payment_status: string;
  payment_method?: string | null;
  shipping_address?: Record<string, any>;
  items: Array<{
    id: string;
    product_name: string;
    size?: string | null;
    quantity: number;
    unit_price: string | number;
    total_price: string | number;
  }>;
  created_at: string;
}

export interface AdminReturn {
  id: string;
  order_id: string;
  order_number?: string;
  tenant_id: string;
  status: string;
  reason: string;
  inspection_notes?: string | null;
  created_at: string;
}

export interface AdminCoupon {
  id: string;
  code: string;
  discount_type: string;
  discount_value: string | number;
  min_order_amount: string | number;
  max_discount_amount?: string | number | null;
  valid_from: string;
  valid_until: string;
  usage_limit?: number | null;
  usage_count: number;
  is_active: boolean;
  created_at: string;
}

export interface AdminPaymentTransaction {
  id: string;
  tenant_id?: string | null;
  order_id: string;
  amount: string | number;
  currency: string;
  payment_method: string;
  gateway_provider: string;
  gateway_payment_id?: string | null;
  status: string;
  refund_amount?: string | number;
  created_at: string;
}

export interface AdminDeliveryZone {
  id: string;
  name: string;
  description?: string | null;
  serviceable_pincodes: string[];
  is_active: boolean;
}

export interface AdminDeliveryPersonnel {
  id: string;
  name: string;
  phone_number: string;
  vehicle_type?: string | null;
  duty_status: "ON_DUTY" | "OFF_DUTY";
  is_active: boolean;
}

export interface TenantOverview {
  id: string;
  name: string;
  slug: string;
  status: "pending" | "active" | "suspended";
  legal_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  business_type: string | null;
  pan_number: string | null;
  gstin: string | null;
  registered_address: string | null;
  store_count: number;
  kyc_status: "NOT_SUBMITTED" | "PENDING_REVIEW" | "VERIFIED" | "REJECTED";
  current_plan_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface KYCDocument {
  id: string;
  tenant_id: string;
  document_type:
    | "GST_CERTIFICATE"
    | "PAN_CARD"
    | "TRADE_LICENSE"
    | "BANK_STATEMENT"
    | "IDENTITY_PROOF";
  document_number: string;
  document_url: string;
  file_name: string;
  file_size_bytes: number;
  status: "PENDING" | "VERIFIED" | "REJECTED";
  rejection_reason?: string | null;
  verified_at?: string | null;
  verified_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TenantLifecycleLog {
  id: string;
  tenant_id: string;
  previous_status: string;
  new_status: string;
  reason: string | null;
  actor_id: string | null;
  created_at: string;
}

export interface SubscriptionPlan {
  id: string;
  code: string;
  name: string;
  description: string | null;
  billing_cycle: "MONTHLY" | "ANNUAL";
  price: string | number;
  currency: string;
  max_stores: number;
  max_staff_users: number;
  commission_rate_percent: string | number;
  features: string[];
  is_active: boolean;
  created_at: string;
}

export interface MerchantSubscription {
  id: string;
  tenant_id: string;
  plan_id: string;
  status: "ACTIVE" | "TRIAL" | "PAST_DUE" | "CANCELLED";
  current_period_start: string;
  current_period_end: string;
  auto_renew: boolean;
  created_at: string;
  plan?: SubscriptionPlan;
}

export interface MerchantInvoice {
  id: string;
  tenant_id: string;
  subscription_id: string | null;
  invoice_number: string;
  billing_period_start: string;
  billing_period_end: string;
  amount: string | number;
  tax_amount: string | number;
  total_amount: string | number;
  currency: string;
  status: "PAID" | "PENDING" | "OVERDUE" | "VOID";
  due_date: string;
  paid_at: string | null;
  payment_reference: string | null;
  line_items: Array<{ description: string; amount: string | number }>;
  created_at: string;
}

export interface PlatformAuditLog {
  id: string;
  actor_id: string | null;
  actor_email: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  details: Record<string, any>;
  ip_address: string | null;
  created_at: string;
}

export interface SystemHealth {
  app_name: string;
  app_env: string;
  status: string;
  database: string;
  pool_size: number;
  active_tenants: number;
  pending_outbox_events: number;
  failed_outbox_events: number;
  system_timestamp: string;
}

export interface PlatformOverviewMetrics {
  start_date: string;
  end_date: string;
  total_active_tenants: number;
  total_physical_stores: number;
  platform_total_orders: number;
  platform_gmv: string | number;
  platform_average_order_value: string | number;
  total_registered_users: number;
  tenants: Array<{
    tenant_id: string;
    tenant_name: string;
    tenant_slug: string;
    status: string;
    store_count: number;
    total_orders: number;
    gross_merchandise_value: string | number;
    active_products_count: number;
    created_at: string;
  }>;
}

export interface OutboxItem {
  id: string;
  tenant_id: string;
  tenant_name: string | null;
  event_type: string;
  aggregate_type: string;
  aggregate_id: string;
  status: string;
  retry_count: number;
  created_at: string;
  updated_at: string;
}

