# Catalogue Ownership & Tenant Isolation Rules

This document establishes the authoritative ownership, visibility, and data-isolation rules for Categories, Brands, Products, and Product Variants in the Bagodi E-Commerce Platform.

---

## 1. Categories Ownership Model

Categories support a **hybrid global and merchant-specific ownership model**:

### Global Categories (`tenant_id IS NULL`)
- **Owner:** TechMasters Platform Governance.
- **Management:** Managed exclusively by Platform Administrators via `platform.categories.*` permissions.
- **Visibility:** Visible platform-wide across all merchant portals and public customer channels.
- **Purpose:** Standard industry taxonomies (e.g., *Apparel*, *Footwear*, *Electronics*, *Home & Living*).
- **Uniqueness:** Category slug must be unique among global categories (`WHERE tenant_id IS NULL`).

### Merchant-Specific Categories (`tenant_id IS NOT NULL`)
- **Owner:** The respective merchant tenant (e.g., Bagodi).
- **Management:** Managed exclusively by merchant staff holding `catalog.categories.*` permissions.
- **Visibility:** Isolated to that specific merchant's storefront, administrative portal, and product associations.
- **Purpose:** Merchant-curated collections, boutique departments, or regional specialty groupings (e.g., *Bidar Handlooms*, *Festival Specials*).
- **Uniqueness:** Category slug must be unique within the merchant's tenant scope (`tenant_id, slug`).

### Hierarchy Support
- Both global and merchant categories support recursive parent-child subcategories via `parent_id` (`FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE RESTRICT`).
- A merchant category may have a global category as its parent, but a global category may never reference a merchant-specific child.

---

## 2. Brands Ownership Model

### Global Brands (`tenant_id IS NULL`)
- **Owner:** Platform Administrator.
- **Visibility:** Available for association across all merchants.
- **Purpose:** Well-known commercial manufacturers and national brands.

### Merchant Brands (`tenant_id IS NOT NULL`)
- **Owner:** The respective merchant tenant.
- **Visibility:** Private to the merchant's catalogue.
- **Purpose:** In-house labels, local artisan partnerships, and exclusive white-label products.

---

## 3. Products Ownership & Publishing

- **Ownership:** Every product is strictly **Merchant-Owned** (`tenant_id` is mandatory and non-nullable).
- **Tenant Scope:** A merchant cannot create, view, modify, or delete products belonging to another merchant.
- **Product Lifecycle:**
  - `status`: `"draft"` (work in progress), `"active"` (live), or `"archived"` (retired).
  - `is_published`: Boolean flag controlling public customer visibility.
- **Public Visibility Rule:**
  - An item is exposed on customer public APIs **only if** `status == 'active'` **AND** `is_published == True`.
  - Merchant staff can view all their products (draft, active, archived) in their admin portal.

---

## 4. Product Variants & SKU / Barcode Integrity

- **Independent Entity:** A variant is an independent database record (`ProductVariant`) with its own UUID primary key, belonging to a product.
- **Stock Quantities Excluded:** Inventory balances, ledger entries, damaged goods tracking, and reservations are **strictly excluded** from the catalogue schema. They are owned by the transactional inventory ledger engine (Phase 4).
- **Pricing Separation:** Base reference prices (`mrp` and `base_price`) are stored on the variant as catalog attributes. Dynamic promotional pricing, coupon discounts, and taxes belong to the pricing engine (Phase 6).
- **SKU Uniqueness:** Every variant must have an SKU that is unique within the merchant's tenant scope (`UniqueConstraint(tenant_id, sku)`).
- **Barcode Management:**
  - Barcodes are unique per merchant (`UniqueConstraint(tenant_id, barcode)`).
  - Physical USB and Bluetooth barcode scanners act as keyboard input on web/POS; the backend provides ultra-fast `GET /api/v1/barcodes/{barcode}` lookup returning the exact variant, base price, and product metadata.
