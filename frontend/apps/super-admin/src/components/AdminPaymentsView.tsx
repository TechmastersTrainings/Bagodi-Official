import React, { useState } from "react";
import {
  CreditCard,
  Search,
  CheckCircle,
  XCircle,
  Clock,
  ArrowDownLeft,
  RotateCcw,
  IndianRupee,
  ShieldCheck,
} from "lucide-react";
import type { AdminPaymentTransaction } from "../types";

interface AdminPaymentsViewProps {
  payments: AdminPaymentTransaction[];
  onRefundPayment: (paymentId: string, amount: number, reason: string) => Promise<void>;
}

export const AdminPaymentsView: React.FC<AdminPaymentsViewProps> = ({
  payments,
  onRefundPayment,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [methodFilter, setMethodFilter] = useState("ALL");

  const filteredPayments = payments.filter((p) => {
    const matchesSearch =
      !searchQuery ||
      p.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.order_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.gateway_payment_id && p.gateway_payment_id.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesStatus = statusFilter === "ALL" || p.status === statusFilter;
    const matchesMethod = methodFilter === "ALL" || p.payment_method === methodFilter;
    return matchesSearch && matchesStatus && matchesMethod;
  });

  const totalCaptured = payments
    .filter((p) => p.status === "SUCCESS" || p.status === "CAPTURED")
    .reduce((acc, p) => acc + (parseFloat(String(p.amount)) || 0), 0);

  const successCount = payments.filter((p) => p.status === "SUCCESS" || p.status === "CAPTURED").length;
  const pendingCount = payments.filter((p) => p.status === "PENDING").length;
  const refundedCount = payments.filter((p) => p.status === "REFUNDED" || (p.refund_amount && Number(p.refund_amount) > 0)).length;

  return (
    <div className="tab-pane">
      {/* Metric Cards */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Settled Gross Payments</span>
            <IndianRupee size={18} color="var(--brand-terracotta)" />
          </div>
          <div className="metric-value">₹{totalCaptured.toLocaleString("en-IN")}</div>
          <div className="metric-subtext">Across Razorpay &amp; Cash on Delivery</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Successful Transactions</span>
            <CheckCircle size={18} color="#16a34a" />
          </div>
          <div className="metric-value" style={{ color: "#16a34a" }}>
            {successCount}
          </div>
          <div className="metric-subtext">Captured &amp; verified payments</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Pending Settlements</span>
            <Clock size={18} color="#f59e0b" />
          </div>
          <div className="metric-value" style={{ color: "#f59e0b" }}>
            {pendingCount}
          </div>
          <div className="metric-subtext">Awaiting cash collect or gateway confirmation</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Refunded Orders</span>
            <RotateCcw size={18} color="#dc2626" />
          </div>
          <div className="metric-value" style={{ color: "#dc2626" }}>
            {refundedCount}
          </div>
          <div className="metric-subtext">Reversals &amp; returns settled</div>
        </div>
      </div>

      {/* Controls */}
      <div className="table-controls" style={{ marginTop: "1.5rem" }}>
        <div style={{ display: "flex", gap: "0.75rem", flex: 1, alignItems: "center" }}>
          <div className="search-box" style={{ maxWidth: 360 }}>
            <Search size={16} color="var(--text-secondary)" />
            <input
              type="text"
              placeholder="Search by transaction ID, order ID, gateway ref..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <select
            className="form-select"
            style={{ width: 170 }}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="ALL">All Statuses</option>
            <option value="SUCCESS">Success / Captured</option>
            <option value="PENDING">Pending</option>
            <option value="REFUNDED">Refunded</option>
            <option value="FAILED">Failed</option>
          </select>

          <select
            className="form-select"
            style={{ width: 170 }}
            value={methodFilter}
            onChange={(e) => setMethodFilter(e.target.value)}
          >
            <option value="ALL">All Payment Methods</option>
            <option value="UPI">UPI</option>
            <option value="CASH_ON_DELIVERY">Cash on Delivery</option>
            <option value="CARD">Credit / Debit Card</option>
            <option value="NETBANKING">Net Banking</option>
          </select>
        </div>
      </div>

      {/* Payments Table */}
      <div className="table-wrapper" style={{ marginTop: "1rem" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Payment Reference</th>
              <th>Order ID</th>
              <th>Payment Channel</th>
              <th>Amount (₹)</th>
              <th>Status</th>
              <th>Gateway / Provider</th>
              <th>Timestamp</th>
              <th style={{ textAlign: "right" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredPayments.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                  <CreditCard size={32} style={{ margin: "0 auto 0.75rem", display: "block", opacity: 0.4 }} />
                  <div>No payment transactions recorded.</div>
                </td>
              </tr>
            ) : (
              filteredPayments.map((p) => (
                <tr key={p.id}>
                  <td>
                    <div style={{ fontWeight: 700, color: "var(--brand-terracotta)" }}>
                      PAY-{p.id.slice(0, 8).toUpperCase()}
                    </div>
                    {p.gateway_payment_id && (
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        {p.gateway_payment_id}
                      </div>
                    )}
                  </td>
                  <td>
                    <span style={{ fontWeight: 600 }}>ORD-{p.order_id.slice(0, 8).toUpperCase()}</span>
                  </td>
                  <td>
                    <span className="badge" style={{ fontSize: "0.75rem" }}>
                      {p.payment_method?.replace(/_/g, " ") || "ONLINE"}
                    </span>
                  </td>
                  <td style={{ fontWeight: 700, fontSize: "0.95rem" }}>
                    ₹{parseFloat(String(p.amount)).toLocaleString("en-IN")}
                  </td>
                  <td>
                    <span
                      className={`status-pill ${p.status === "SUCCESS" || p.status === "CAPTURED"
                          ? "success"
                          : p.status === "REFUNDED"
                            ? "warning"
                            : p.status === "PENDING"
                              ? "warning"
                              : "danger"
                        }`}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                    {p.gateway_provider || "Razorpay"}
                  </td>
                  <td style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    {new Date(p.created_at).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    {(p.status === "SUCCESS" || p.status === "CAPTURED") && (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                          const reason = window.prompt("Enter refund reason:");
                          if (reason) {
                            onRefundPayment(p.id, parseFloat(String(p.amount)), reason);
                          }
                        }}
                        style={{ fontSize: "0.75rem" }}
                      >
                        <RotateCcw size={13} />
                        <span>Refund</span>
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

