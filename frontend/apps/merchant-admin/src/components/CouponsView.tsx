import React, { useState } from "react";
import { Tag, Plus, Trash2, X } from "lucide-react";

interface CouponItem {
  id: string;
  code: string;
  name: string;
  description: string | null;
  discount_type: string;
  discount_value: string;
  min_order_amount: string;
  max_discount_amount: string | null;
  start_date: string;
  end_date: string;
  status: string;
}

interface CouponsViewProps {
  coupons: CouponItem[];
  onCreateCoupon: (data: any) => Promise<void>;
  onDeleteCoupon: (couponId: string) => Promise<void>;
}

export const CouponsView: React.FC<CouponsViewProps> = ({
  coupons,
  onCreateCoupon,
  onDeleteCoupon,
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [discountType, setDiscountType] = useState<"PERCENTAGE" | "FIXED_AMOUNT">("PERCENTAGE");
  const [discountValue, setDiscountValue] = useState("10");
  const [minOrder, setMinOrder] = useState("999");
  const [maxDiscount, setMaxDiscount] = useState("2000");
  const [startDate, setStartDate] = useState(new Date().toISOString().split("T")[0]);
  const [endDate, setEndDate] = useState(
    new Date(Date.now() + 60 * 86400000).toISOString().split("T")[0]
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim() || !name.trim()) return;

    setIsSubmitting(true);
    try {
      await onCreateCoupon({
        code: code.trim().toUpperCase(),
        name: name.trim(),
        description: description.trim() || null,
        discount_type: discountType,
        discount_value: parseFloat(discountValue),
        min_order_amount: parseFloat(minOrder) || 0,
        max_discount_amount: maxDiscount ? parseFloat(maxDiscount) : null,
        start_date: new Date(startDate).toISOString(),
        end_date: new Date(endDate + "T23:59:59").toISOString(),
        usage_limit_total: 500,
        usage_limit_per_customer: 1,
        status: "active",
      });

      setIsModalOpen(false);
      setCode("");
      setName("");
      setDescription("");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id: string, codeName: string) => {
    if (window.confirm(`Are you sure you want to delete coupon code "${codeName}"?`)) {
      await onDeleteCoupon(id);
    }
  };

  return (
    <div className="table-container">
      <div className="table-toolbar">
        <div>
          <span style={{ fontWeight: 700, fontSize: "1rem" }}>
            Store Coupons & Promotional Discount Rules
          </span>
          <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
            Create promotional coupon codes for customers during checkout (e.g. BAGODI10, FESTIVE25)
          </div>
        </div>

        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={() => setIsModalOpen(true)}
        >
          <Plus size={16} />
          <span>Create Coupon</span>
        </button>
      </div>

      {coupons.length === 0 ? (
        <div className="empty-state">
          <Tag size={36} color="var(--brand-terracotta)" />
          <div className="empty-state-title" style={{ marginTop: 12 }}>
            No Active Coupons Registered
          </div>
          <div className="empty-state-text">
            Create your first store promotional campaign to offer percentage or fixed amount discounts.
          </div>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setIsModalOpen(true)}
            style={{ marginTop: 12 }}
          >
            <Plus size={16} />
            <span>Create First Coupon</span>
          </button>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Coupon Code</th>
              <th>Campaign Name</th>
              <th>Discount Value</th>
              <th>Minimum Order</th>
              <th>Validity</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {coupons.map((c) => (
              <tr key={c.id}>
                <td>
                  <span className="variant-tag" style={{ fontWeight: 700, letterSpacing: "0.05em" }}>
                    {c.code}
                  </span>
                </td>
                <td>
                  <strong>{c.name}</strong>
                  {c.description && (
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {c.description}
                    </div>
                  )}
                </td>
                <td style={{ fontWeight: 600 }}>
                  {c.discount_type === "PERCENTAGE"
                    ? `${parseFloat(c.discount_value)}% OFF`
                    : `₹${parseFloat(c.discount_value).toLocaleString("en-IN")} FLAT`}
                  {c.max_discount_amount && (
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                      Max: ₹{parseFloat(c.max_discount_amount).toLocaleString("en-IN")}
                    </div>
                  )}
                </td>
                <td>₹{parseFloat(c.min_order_amount || "0").toLocaleString("en-IN")}</td>
                <td style={{ fontSize: "0.75rem", whiteSpace: "nowrap" }}>
                  {new Date(c.start_date).toLocaleDateString()} to {new Date(c.end_date).toLocaleDateString()}
                </td>
                <td>
                  <span className="status-pill success">{c.status.toUpperCase()}</span>
                </td>
                <td>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleDelete(c.id, c.code)}
                    style={{ color: "var(--status-danger)", padding: "4px 8px" }}
                    title="Delete Coupon"
                  >
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* CREATE COUPON MODAL */}
      {isModalOpen && (
        <div className="modal-overlay" onClick={() => setIsModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Create Store Promotional Coupon</h3>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setIsModalOpen(false)}
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-row">
                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label">Coupon Code *</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. BAGODI20"
                      value={code}
                      onChange={(e) => setCode(e.target.value.toUpperCase())}
                      required
                    />
                  </div>

                  <div className="form-group" style={{ flex: 2 }}>
                    <label className="form-label">Campaign Name *</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. Festive Silk Inauguration"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Description (Optional)</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Exclusive 20% discount on Banarasi silk collection"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </div>

                <div className="form-row">
                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label">Discount Type *</label>
                    <select
                      className="form-select"
                      value={discountType}
                      onChange={(e) => setDiscountType(e.target.value as any)}
                    >
                      <option value="PERCENTAGE">Percentage (%)</option>
                      <option value="FIXED_AMOUNT">Fixed Amount (₹)</option>
                    </select>
                  </div>

                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label">
                      {discountType === "PERCENTAGE" ? "Discount Percentage (%) *" : "Flat Discount (₹) *"}
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      className="form-input"
                      value={discountValue}
                      onChange={(e) => setDiscountValue(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label">Minimum Order Value (₹) *</label>
                    <input
                      type="number"
                      step="0.01"
                      className="form-input"
                      value={minOrder}
                      onChange={(e) => setMinOrder(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label">Maximum Discount Cap (₹)</label>
                    <input
                      type="number"
                      step="0.01"
                      className="form-input"
                      value={maxDiscount}
                      onChange={(e) => setMaxDiscount(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label">Valid From *</label>
                    <input
                      type="date"
                      className="form-input"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label">Valid Until *</label>
                    <input
                      type="date"
                      className="form-input"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                  {isSubmitting ? "Creating..." : "Save Coupon"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
