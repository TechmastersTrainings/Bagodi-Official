# Pricing, Promotions & Coupon Engine Specification

**Platform Owner:** TechMasters Innovations Private Limited  
**Merchant Scope:** Multi-tenant (Merchant-specific configuration)  
**Initial Merchant:** Bagodi (Bidar, Karnataka)  
**System Module:** `backend/app/modules/pricing`  

---

## 1. Architectural Principles & Boundaries

1. **Backend-Only Authority:**
   All product pricing, promotional markdowns, coupon discounts, taxes, and order totals are authoritatively calculated and verified on the server. Client-submitted prices, discounts, or totals are strictly rejected.
2. **Separation of Concerns:**
   - **Catalogue (`catalog`):** Stores reference base prices (`base_price` and `mrp`) on `ProductVariant`. Does not manage temporal sales or dynamic discounts.
   - **Inventory (`inventory`):** Manages stock counts, physical locations, and double-entry stock ledger. Does not manage pricing.
   - **Pricing (`pricing`):** Evaluates promotions, coupons, minimum spend requirements, stacking rules, and produces verified price breakdowns.
   - **Orders (`orders`):** Calls `PricingService` during checkout to produce immutable order-line snapshots and records coupon redemptions.
3. **Tenant Isolation:**
   All promotions, coupons, redemptions, and audit logs are strictly scoped by `tenant_id`. Cross-tenant coupon usage or promotion sharing is strictly blocked.
4. **Auditability:**
   Every creation, modification, status update, or deletion of a promotion or coupon generates an immutable entry in `pricing_audit_logs`.

---

## 2. Entities & Data Models

### A. Promotions (`promotions`)
Merchant-configured promotional rules that automatically apply to eligible products or shopping carts during an active promotional window.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `tenant_id` | UUID | Owning merchant tenant ID (Foreign Key) |
| `name` | String(150) | Human-readable title (e.g., "Diwali Festive 15% Off") |
| `description` | Text | Marketing terms and conditions |
| `promotion_type` | String(20) | `PERCENTAGE` or `FIXED_AMOUNT` |
| `scope` | String(20) | `VARIANT`, `PRODUCT`, `CATEGORY`, or `CART` |
| `target_id` | UUID (nullable) | ID of the target variant, product, or category (`NULL` for `CART`) |
| `discount_value` | Numeric(12, 2) | Percentage rate (e.g. `15.00` = 15%) or flat amount (e.g. `200.00` = ₹200) |
| `max_discount_amount` | Numeric(12, 2) (nullable) | Maximum discount cap (especially for percentage discounts) |
| `min_order_amount` | Numeric(12, 2) | Minimum item spend or cart subtotal required to trigger rule |
| `start_date` | DateTime (UTC) | Start of promotional validity |
| `end_date` | DateTime (UTC, nullable) | End of promotional validity (`NULL` = perpetual) |
| `status` | String(20) | `active`, `inactive`, or `archived` |
| `priority` | Integer | Tie-breaking priority (higher number takes precedence) |
| `is_stackable` | Boolean | Whether this promotion combines with other promotions or coupons |

### B. Coupons (`coupons`)
Customer-redeemable alphanumeric codes that grant order-level or cart-level discounts upon validation.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `tenant_id` | UUID | Merchant tenant ID |
| `code` | String(50) | Uppercase coupon code (unique per tenant: `uq_coupons_tenant_code`) |
| `name` | String(150) | Title of the campaign (e.g. "Bidar Heritage Inaugural") |
| `description` | Text | Terms, redemption eligibility, restrictions |
| `discount_type` | String(20) | `PERCENTAGE` or `FIXED_AMOUNT` |
| `discount_value` | Numeric(12, 2) | Discount percentage or flat amount |
| `max_discount_amount` | Numeric(12, 2) (nullable) | Maximum monetary cap on percentage discount |
| `min_order_amount` | Numeric(12, 2) | Minimum cart subtotal required for coupon validation |
| `start_date` | DateTime (UTC) | Effective start date and time |
| `end_date` | DateTime (UTC) | Expiration date and time |
| `status` | String(20) | `active`, `inactive`, or `expired` |
| `total_usage_limit` | Integer (nullable) | Overall redemption ceiling across all customers (`NULL` = unlimited) |
| `usage_limit_per_customer` | Integer | Max redemptions allowed per individual customer (default `1`) |
| `total_redeemed_count` | Integer | Total successful redemptions to date (default `0`) |
| `is_stackable` | Boolean | Whether coupon can be combined with other promotions (default `False`) |

### C. Coupon Redemptions (`coupon_redemptions`)
Tracks each customer redemption transaction to guarantee concurrency safety and enforce per-customer and platform-wide limits.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `tenant_id` | UUID | Merchant tenant ID |
| `coupon_id` | UUID | Foreign Key to `coupons.id` |
| `customer_id` | UUID | Foreign Key to `users.id` |
| `order_id` | UUID | Foreign Key to `orders.id` (`uq_coupon_redemptions_order` prevents double use) |
| `discount_applied` | Numeric(12, 2) | Exact monetary value deducted from order |
| `redeemed_at` | DateTime (UTC) | Timestamp of redemption |
| `status` | String(20) | `consumed` or `reverted` (if order was cancelled) |

### D. Pricing Audit Logs (`pricing_audit_logs`)
Maintains an immutable historical record of all pricing and promotion rule adjustments for administrative governance.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `tenant_id` | UUID | Merchant tenant ID |
| `entity_type` | String(30) | `promotion` or `coupon` |
| `entity_id` | UUID | ID of the modified entity |
| `action` | String(20) | `CREATE`, `UPDATE`, `STATUS_CHANGE`, `DELETE` |
| `changed_by_user_id` | UUID (nullable) | User ID of the merchant admin |
| `changes` | JSONB | Snapshot of changed fields `{"old": {...}, "new": {...}}` |
| `created_at` | DateTime (UTC) | Timestamp of event |

---

## 3. Pricing Precedence & Conflict Resolution Matrix

When calculating the final price for a cart or checkout, `PricingService` executes the following sequential evaluation pipeline:

```
[Base Variant Price: ProductVariant.base_price]
                       │
                       ▼
         [Item-Level Promotion Evaluation]
        (Variant > Product > Category Specificity)
                       │
                       ▼
      [Discounted Item Subtotal Calculation]
                       │
                       ▼
         [Cart-Level Promotion Evaluation]
        (Highest Priority / Best Value Rule)
                       │
                       ▼
         [Coupon Code Evaluation & Stacking]
     (Eligibility, Date, Usage Limits & Stacking)
                       │
                       ▼
      [Floor, Cap, and Snapshot Generation]
```

### Rule 1: Specificity Precedence
Item-level promotions are evaluated in descending order of specificity:
$$\text{VARIANT (Rank 3)} > \text{PRODUCT (Rank 2)} > \text{CATEGORY (Rank 1)}$$
- If an active `VARIANT` promotion exists, it wins. Parent `PRODUCT` and `CATEGORY` promotions are discarded for this line item.
- If no `VARIANT` promotion exists, an active `PRODUCT` promotion applies, overriding any `CATEGORY` promotion.
- If neither variant nor product promotions exist, an active `CATEGORY` promotion applies.

### Rule 2: Intra-Level Conflict Resolution
If multiple promotions qualify at the same level:
1. Higher `priority` integer wins.
2. If priorities are equal, the promotion yielding the greatest discount (maximum customer savings) is selected.

### Rule 3: Monetary Floor & Discount Capping
- No item price or cart total can drop below ₹0.00 (`Decimal("0.00")`).
- For percentage discounts, if `max_discount_amount` is defined:
  $$\text{discount} = \min\left(\text{unit\_price} \times \frac{\text{discount\_value}}{100},\; \text{max\_discount\_amount}\right)$$

### Rule 4: Cart-Level Promotions
- Evaluated against the net subtotal of eligible items after item-level promotions are deducted.
- Only triggers if `subtotal >= min_order_amount`.

### Rule 5: Coupon Validation & Stacking Rules
- Validated against:
  1. Active status and current datetime within `[start_date, end_date]`.
  2. Order subtotal meets `min_order_amount`.
  3. Total redemptions `< total_usage_limit` (if set).
  4. Customer redemptions `< usage_limit_per_customer`.
- **Stacking Logic:**
  - If `coupon.is_stackable is True`: Coupon discount applies on top of all item-level and cart-level promotional discounts.
  - If `coupon.is_stackable is False`: The coupon overrides any cart-level promotion. The customer receives the coupon discount instead of cart-level promotions.

---

## 4. Concurrency Safety & Over-Redemption Prevention

To prevent race conditions during high-concurrency flash sales (e.g. "First 50 orders get ₹500 off"):
1. **Row-Level Locking:** During checkout, coupon validation executes with PostgreSQL row-level lock:
   ```sql
   SELECT * FROM coupons WHERE id = :coupon_id AND tenant_id = :tenant_id FOR UPDATE;
   ```
2. **Atomic Verification:**
   - Evaluates `total_redeemed_count < total_usage_limit`.
   - Counts existing non-reverted customer redemptions inside the transaction:
     ```sql
     SELECT COUNT(*) FROM coupon_redemptions
     WHERE coupon_id = :coupon_id AND customer_id = :customer_id AND status = 'consumed';
     ```
3. **Atomic Increment:** If valid, inserts a `coupon_redemptions` record with `status = 'consumed'` and increments `coupons.total_redeemed_count = total_redeemed_count + 1`.
4. **Order Cancellation Compensation:** If an order is cancelled, a compensating transaction updates `coupon_redemptions.status = 'reverted'` and decrements `coupons.total_redeemed_count = total_redeemed_count - 1`.

---

## 5. Order Snapshot & Discount Breakdown

When an order is created, the backend captures an immutable pricing breakdown:
- Each `order_items` record stores:
  - `original_unit_price`: Base catalog price before discounts.
  - `unit_price`: Effective unit price charged after item-level discounts.
  - `discount_amount`: Total discount amount on this line item.
  - `applied_promotion_id`: UUID of the promotion applied (if any).
  - `applied_promotion_title`: Name of the promotion.
- The `orders` record stores:
  - `subtotal`: Sum of all items at original base price.
  - `discount_amount`: Total discounts (item discounts + cart discounts + coupon discounts).
  - `shipping_fee`: Final shipping charge.
  - `total_amount`: Final payable amount.
  - `coupon_id` and `coupon_code`: Code applied.
  - `discount_breakdown`: Structured JSON containing:
    ```json
    {
      "item_discounts_total": "150.00",
      "cart_discount_total": "0.00",
      "coupon_discount_total": "100.00",
      "promotions_applied": [
        {"scope": "PRODUCT", "title": "Silver Festive 10%", "amount": "150.00"}
      ],
      "coupon_applied": {
        "code": "WELCOME100",
        "title": "Welcome Voucher",
        "amount": "100.00"
      }
    }
    ```
