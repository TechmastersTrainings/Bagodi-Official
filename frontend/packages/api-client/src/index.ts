/**
 * Bagodi Platform Shared API Client SDK.
 */

import type { components } from "./schema.js";

export * from "./schema.js";
export * from "./auth.js";
export * from "./errors.js";
export * from "./types.js";
export * from "./client.js";

// Convenience Type Aliases
export type Schema = components["schemas"];

export type CustomerAddress = components["schemas"]["CustomerAddressResponse"];
export type CustomerAddressCreate = components["schemas"]["CustomerAddressCreate"];
export type CustomerAddressUpdate = components["schemas"]["CustomerAddressUpdate"];

export type OrderReturnRequest = components["schemas"]["OrderReturnRequestResponse"];
export type OrderReturnRequestCreate = components["schemas"]["OrderReturnRequestCreate"];
export type OrderReturnReviewRequest = components["schemas"]["OrderReturnReviewRequest"];

export type Cart = components["schemas"]["CartResponse"];
export type CartItem = components["schemas"]["CartItemResponse"];
export type CartItemAdd = components["schemas"]["CartItemAdd"];
export type CartItemUpdate = components["schemas"]["CartItemUpdate"];
export type CartMergeRequest = components["schemas"]["CartMergeRequest"];

export type Order = components["schemas"]["OrderResponse"];
export type OrderItem = components["schemas"]["OrderItemResponse"];
export type CheckoutRequest = components["schemas"]["CheckoutRequest"];
export type ShippingAddress = components["schemas"]["ShippingAddressSchema"];

export type Product = components["schemas"]["ProductDetailResponse"];
export type ProductDetail = components["schemas"]["ProductDetailResponse"];
export type ProductVariant = components["schemas"]["ProductVariantResponse"];
export type VariantDetail = components["schemas"]["ProductVariantResponse"];
export type ProductImage = components["schemas"]["ProductImageResponse"];
export type Category = components["schemas"]["CategoryResponse"];

export type ServiceabilityResponse = components["schemas"]["ServiceabilityCheckResponse"];

// Super Admin / Platform Governance Types
export type Tenant = components["schemas"]["TenantResponse"];
export type TenantCreate = components["schemas"]["TenantCreate"];
export type TenantKYCDocument = components["schemas"]["TenantKYCDocumentResponse"];
export type TenantKYCDocumentCreate = components["schemas"]["TenantKYCDocumentCreate"];
export type TenantKYCDocumentReview = components["schemas"]["TenantKYCDocumentReview"];
export type TenantStatusLog = components["schemas"]["TenantStatusLogResponse"];

export type SubscriptionPlan = components["schemas"]["SubscriptionPlanResponse"];
export type SubscriptionPlanCreate = components["schemas"]["SubscriptionPlanCreate"];
export type MerchantSubscription = components["schemas"]["MerchantSubscriptionResponse"];
export type MerchantInvoice = components["schemas"]["MerchantInvoiceResponse"];
export type MerchantInvoiceCreate = components["schemas"]["MerchantInvoiceCreate"];

export type PlatformAuditLog = components["schemas"]["PlatformAuditLogResponse"];
export type PlatformStaff = components["schemas"]["PlatformStaffResponse"];
export type PlatformStaffCreate = components["schemas"]["PlatformStaffCreate"];
