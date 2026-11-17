import type {
  CustomerAddress,
} from "@bagodi/api-client";

export type RoleType =
  | "MERCHANT_ADMIN"
  | "STORE_MANAGER"
  | "INVENTORY_CLERK"
  | "DELIVERY_STAFF";

export interface StaffUser {
  id: string;
  phone_e164?: string;
  email?: string | null;
  display_name?: string | null;
  role: RoleType;
  tenant_id?: string;
  merchant_id?: string;
  status?: string;
  permissions?: string[];
}

export interface MerchantStaffMember {
  id: string;
  display_name: string | null;
  email: string | null;
  phone_e164: string | null;
  status: string;
  role: string;
  tenant_id: string | null;
  created_at: string;
}

export interface PhysicalStore {
  id: string;
  tenant_id: string;
  name: string;
  code: string;
  address_line: string;
  city: string;
  state: string;
  postal_code: string;
  phone?: string | null;
  email?: string | null;
  status: "active" | "inactive" | "maintenance";
  is_active?: boolean;
  created_at: string;
}

export interface Category {
  id: string;
  tenant_id?: string | null;
  name: string;
  slug: string;
  description?: string | null;
  parent_id?: string | null;
  is_active: boolean;
}

export interface Brand {
  id: string;
  tenant_id?: string | null;
  name: string;
  slug: string;
  description?: string | null;
  is_active: boolean;
}

export interface StockBalance {
  id: string;
  tenant_id: string;
  store_id: string;
  variant_id: string;
  sku: string;
  variant_name?: string;
  product_name?: string;
  on_hand_qty: number;
  reserved_qty: number;
  available_qty: number;
  damaged_qty: number;
  reorder_level: number;
  updated_at: string;
}

export interface LedgerEntry {
  id: string;
  tenant_id: string;
  store_id: string;
  variant_id: string;
  sku?: string;
  movement_type: string;
  quantity: number;
  balance_before: number;
  balance_after: number;
  reference_id?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface Supplier {
  id: string;
  tenant_id: string;
  name: string;
  code: string;
  contact_person?: string | null;
  email?: string | null;
  phone: string;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  gstin?: string | null;
  is_active: boolean;
}

export interface PurchaseOrderItem {
  id: string;
  variant_id: string;
  sku: string;
  variant_name?: string;
  quantity_ordered: number;
  quantity_received: number;
  unit_cost: string;
}

export interface PurchaseOrder {
  id: string;
  tenant_id: string;
  store_id: string;
  supplier_id: string;
  supplier_name?: string;
  po_number: string;
  status: "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "PARTIALLY_RECEIVED" | "COMPLETED" | "CANCELLED";
  total_amount: string;
  items: PurchaseOrderItem[];
  created_at: string;
}

export interface MerchantOrder {
  id: string;
  tenant_id: string;
  store_id: string;
  order_number: string;
  customer_id: string;
  customer_name?: string;
  customer_phone?: string;
  status: "CONFIRMED" | "PROCESSING" | "DISPATCHED" | "DELIVERED" | "CANCELLED" | "RETURNED";
  payment_status: "AUTHORIZED" | "CAPTURED" | "PENDING" | "FAILED" | "REFUNDED";
  payment_method: "ONLINE" | "COD";
  shipping_address?: CustomerAddress | null;
  subtotal_amount: string;
  discount_amount: string;
  delivery_fee: string;
  total_amount: string;
  items: Array<{
    id: string;
    variant_id: string;
    product_name: string;
    variant_name: string;
    sku: string;
    size?: string;
    color?: string;
    quantity: number;
    unit_price: string;
    total_price: string;
  }>;
  created_at: string;
  updated_at: string;
}

export interface DeliveryZone {
  id: string;
  tenant_id: string;
  store_id?: string | null;
  name: string;
  code: string;
  base_delivery_fee: string;
  free_delivery_threshold: string;
  estimated_delivery_hours: number;
  is_active: boolean;
  pincodes?: string[];
}

export interface DeliveryPersonnel {
  id: string;
  tenant_id: string;
  name: string;
  phone: string;
  duty_status: "ON_DUTY" | "OFF_DUTY" | "ON_BREAK";
  vehicle_type?: string;
  current_location?: string;
  is_active: boolean;
}

export interface DeliveryVehicle {
  id: string;
  tenant_id: string;
  registration_number: string;
  vehicle_type: "TWO_WHEELER" | "THREE_WHEELER" | "VAN";
  capacity_kg: number;
  status: "ACTIVE" | "MAINTENANCE" | "INACTIVE";
}

export interface DashboardMetrics {
  total_sales: string;
  net_revenue: string;
  total_orders: number;
  pending_fulfillment: number;
  low_stock_count: number;
  returns_count: number;
  average_order_value: string;
}
