import React, { useState } from "react";
import {
  Tag,
  Plus,
  Search,
  CheckCircle,
  XCircle,
  Percent,
  Calendar,
  X,
  Trash2,
} from "lucide-react";
import type { AdminCoupon } from "../types";

interface AdminCouponsViewProps {
  coupons: AdminCoupon[];
  onCreateCoupon: (data: any) => Promise<void>;
  onDeleteCoupon: (couponId: string) => Promise<void>;
}

export const AdminCouponsView: React.FC<AdminCouponsViewProps> = ({
  coupons,
  onCreateCoupon,
  onDeleteCoupon,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Form State
  const [code, setCode] = useState("");
  const [discountType, setDiscountType] = useState<"PERCENTAGE" | "FIXED_AMOUNT">("PERCENTAGE");
  const [discountValue, setDiscountValue] = useState("15");
  const [minOrder, setMinOrder] = useState("2499");
  const [maxDiscount, setMaxDiscount] = useState("1000");
  const [validDays, setValidDays] = useState("30");
  const [usageLimit, setUsageLimit] = useState("500");
  const [submitting, setSubmitting] = useState(false);

  const filteredCoupons = coupons.filter(
    (c) =>
      !searchQuery ||
      c.code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const activeCount = coupons.filter((c) => c.is_active).length;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    setSubmitting(true);
    try {
      const now = new Date();
      const until = new Date();
      until.setDate(until.getDate() + parseInt(validDays));

      await onCreateCoupon({
        code: code.trim().toUpperCase(),
        discount_type: discountType,
        discount_value: parseFloat(discountValue) || 0,
        min_order_amount: parseFloat(minOrder) || 0,
        max_discount_amount: discountType === "PERCENTAGE" ? parseFloat(maxDiscount) || null : null,
        valid_from: now.toISOString(),
        valid_until: until.toISOString(),
        usage_limit: parseInt(usageLimit) || null,
        is_active: true,
      });

      setIsModalOpen(false);
      setCode("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="tab-pane">
      {/* Metric Cards */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Total Platform Coupons</span>
            <Tag size={18} color="var(--brand-terracotta)" />
          </div>
          <div className="metric-value">{coupons.length}</div>
          <div className="metric-subtext">Active &amp; archival promotions</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Active Promotions</span>
            <CheckCircle size={18} color="#16a34a" />
          </div>
          <div className="metric-value" style={{ color: "#16a34a" }}>
            {activeCount}
          </div>
          <div className="metric-subtext">Currently valid for checkout deduction</div>
        </div>
      </div>

      {/* Controls */}
      <div className="table-controls" style={{ marginTop: "1.5rem" }}>
        <div className="search-box" style={{ maxWidth: 360 }}>
          <Search size={16} color="var(--text-secondary)" />
          <input
            type="text"
            placeholder="Search coupons by code..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <button className="btn btn-primary" onClick={() => setIsModalOpen(true)}>
          <Plus size={16} />
          <span>Create Promotional Coupon</span>
        </button>
      </div>

      {/* Coupons Table */}
      <div className="table-wrapper" style={{ marginTop: "1rem" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Voucher Code</th>
              <th>Benefit / Discount</th>
              <th>Order Thresholds</th>
              <th>Usage Stats</th>
              <th>Validity Window</th>
              <th>Status</th>
              <th style={{ textAlign: "right" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredCoupons.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                  <Tag size={32} style={{ margin: "0 auto 0.75rem", display: "block", opacity: 0.4 }} />
                  <div>No coupons created yet. Click &quot;Create Promotional Coupon&quot; to add one.</div>
                </td>
              </tr>
            ) : (
              filteredCoupons.map((c) => (
                <tr key={c.id}>
                  <td>
                    <code
                      style={{
                        fontSize: "0.95rem",
                        fontWeight: 700,
                        color: "var(--brand-terracotta)",
                        background: "var(--bg-app)",
                        padding: "4px 8px",
                        borderRadius: 4,
                      }}
                    >
                      {c.code}
                    </code>
                  </td>
                  <td>
                    <span style={{ fontWeight: 600 }}>
                      {c.discount_type === "PERCENTAGE" ? `${c.discount_value}% OFF` : `₹${c.discount_value} FLAT`}
                    </span>
                    {c.max_discount_amount && (
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        Max Cap: ₹{c.max_discount_amount}
                      </div>
                    )}
                  </td>
                  <td style={{ fontSize: "0.85rem" }}>
                    Min Spend: <strong>₹{c.min_order_amount}</strong>
                  </td>
                  <td>
                    <span className="badge" style={{ fontSize: "0.75rem" }}>
                      {c.usage_count || 0} / {c.usage_limit || "∞"} used
                    </span>
                  </td>
                  <td style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    {new Date(c.valid_from).toLocaleDateString("en-IN", { day: "numeric", month: "short" })} –{" "}
                    {new Date(c.valid_until).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                  </td>
                  <td>
                    <span className={`status-pill ${c.is_active ? "success" : "warning"}`}>
                      {c.is_active ? "Active" : "Expired"}
                    </span>
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        if (window.confirm(`Delete coupon ${c.code}?`)) {
                          onDeleteCoupon(c.id);
                        }
                      }}
                      style={{ color: "#dc2626" }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* CREATE MODAL */}
      {isModalOpen && (
        <div className="modal-overlay" onClick={() => setIsModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 500 }}>
            <div className="modal-header">
              <h3 className="modal-title">Create Platform Coupon</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsModalOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Coupon Code *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. FESTIVE20 or WELCOME10"
                    value={code}
                    onChange={(e) => setCode(e.target.value.toUpperCase())}
                    required
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Discount Type *</label>
                    <select
                      className="form-select"
                      value={discountType}
                      onChange={(e) => setDiscountType(e.target.value as any)}
                    >
                      <option value="PERCENTAGE">Percentage (% Off)</option>
                      <option value="FIXED_AMOUNT">Flat Amount (₹ Off)</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Discount Value *</label>
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
                  <div className="form-group">
                    <label className="form-label">Min Order Spend (₹) *</label>
                    <input
                      type="number"
                      className="form-input"
                      value={minOrder}
                      onChange={(e) => setMinOrder(e.target.value)}
                      required
                    />
                  </div>

                  {discountType === "PERCENTAGE" && (
                    <div className="form-group">
                      <label className="form-label">Max Discount Cap (₹)</label>
                      <input
                        type="number"
                        className="form-input"
                        value={maxDiscount}
                        onChange={(e) => setMaxDiscount(e.target.value)}
                      />
                    </div>
                  )}
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Validity (Days from now)</label>
                    <input
                      type="number"
                      className="form-input"
                      value={validDays}
                      onChange={(e) => setValidDays(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Total Redemptions Cap</label>
                    <input
                      type="number"
                      className="form-input"
                      value={usageLimit}
                      onChange={(e) => setUsageLimit(e.target.value)}
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  Create Coupon
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

