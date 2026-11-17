import React, { useState } from "react";
import {
  RotateCcw,
  Search,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ArrowRightLeft,
  Clock,
  ShieldCheck,
} from "lucide-react";
import type { AdminReturn } from "../types";

interface AdminReturnsViewProps {
  returns: AdminReturn[];
  onReviewReturn: (returnId: string, status: string, notes?: string) => Promise<void>;
}

export const AdminReturnsView: React.FC<AdminReturnsViewProps> = ({
  returns,
  onReviewReturn,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const filteredReturns = returns.filter((r) => {
    const matchesSearch =
      !searchQuery ||
      r.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.order_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.reason && r.reason.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesStatus = statusFilter === "ALL" || r.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const requestedCount = returns.filter((r) => r.status === "REQUESTED").length;
  const approvedCount = returns.filter((r) => r.status === "APPROVED" || r.status === "INSPECTED").length;
  const completedCount = returns.filter((r) => r.status === "COMPLETED").length;

  return (
    <div className="tab-pane">
      {/* Metric Cards */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Total Return Requests</span>
            <RotateCcw size={18} color="var(--brand-terracotta)" />
          </div>
          <div className="metric-value">{returns.length}</div>
          <div className="metric-subtext">Returns &amp; size exchanges</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Awaiting Boutique Inspection</span>
            <Clock size={18} color="#f59e0b" />
          </div>
          <div className="metric-value" style={{ color: "#f59e0b" }}>
            {requestedCount}
          </div>
          <div className="metric-subtext">Customer requested reversal</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Approved &amp; In-Transit</span>
            <ArrowRightLeft size={18} color="#2563eb" />
          </div>
          <div className="metric-value" style={{ color: "#2563eb" }}>
            {approvedCount}
          </div>
          <div className="metric-subtext">Return verified by QA</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Restocked / Refunded</span>
            <CheckCircle size={18} color="#16a34a" />
          </div>
          <div className="metric-value" style={{ color: "#16a34a" }}>
            {completedCount}
          </div>
          <div className="metric-subtext">Completed inventory adjustments</div>
        </div>
      </div>

      {/* Controls */}
      <div className="table-controls" style={{ marginTop: "1.5rem" }}>
        <div style={{ display: "flex", gap: "0.75rem", flex: 1, alignItems: "center" }}>
          <div className="search-box" style={{ maxWidth: 360 }}>
            <Search size={16} color="var(--text-secondary)" />
            <input
              type="text"
              placeholder="Search by return ID, order ID, or reason..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <select
            className="form-select"
            style={{ width: 180 }}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="ALL">All Return Statuses</option>
            <option value="REQUESTED">Requested</option>
            <option value="APPROVED">Approved</option>
            <option value="INSPECTED">Inspected</option>
            <option value="COMPLETED">Completed</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </div>
      </div>

      {/* Returns Table */}
      <div className="table-wrapper" style={{ marginTop: "1rem" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Return Reference</th>
              <th>Original Order</th>
              <th>Customer Reason</th>
              <th>Inspection Status</th>
              <th>Requested Date</th>
              <th style={{ textAlign: "right" }}>Governance Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredReturns.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                  <RotateCcw size={32} style={{ margin: "0 auto 0.75rem", display: "block", opacity: 0.4 }} />
                  <div>No return or size swap requests found.</div>
                </td>
              </tr>
            ) : (
              filteredReturns.map((r) => (
                <tr key={r.id}>
                  <td>
                    <div style={{ fontWeight: 700, color: "var(--brand-terracotta)" }}>
                      RET-{r.id.slice(0, 8).toUpperCase()}
                    </div>
                  </td>
                  <td>
                    <div style={{ fontWeight: 600 }}>ORD-{r.order_id.slice(0, 8).toUpperCase()}</div>
                  </td>
                  <td style={{ fontSize: "0.85rem" }}>{r.reason || "Size misfit / exchange request"}</td>
                  <td>
                    <span
                      className={`status-pill ${r.status === "COMPLETED"
                          ? "success"
                          : r.status === "REJECTED"
                            ? "danger"
                            : "warning"
                        }`}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                    {new Date(r.created_at).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <div style={{ display: "inline-flex", gap: "6px" }}>
                      {r.status === "REQUESTED" && (
                        <>
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => onReviewReturn(r.id, "APPROVED")}
                            style={{ padding: "4px 8px", fontSize: "0.75rem" }}
                          >
                            Approve
                          </button>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => onReviewReturn(r.id, "REJECTED", "Garment tags missing / worn")}
                            style={{ padding: "4px 8px", fontSize: "0.75rem", color: "#dc2626" }}
                          >
                            Reject
                          </button>
                        </>
                      )}
                      {r.status === "APPROVED" && (
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => onReviewReturn(r.id, "COMPLETED", "Inspected and restocked")}
                          style={{ padding: "4px 8px", fontSize: "0.75rem", background: "#16a34a", borderColor: "#16a34a" }}
                        >
                          Restock to Inventory
                        </button>
                      )}
                    </div>
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

