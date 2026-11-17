import React, { useState } from "react";
import {
  RotateCcw,
  CheckCircle,
  XCircle,
  Eye,
  X,
  FileCheck,
  Truck,
} from "lucide-react";
import type { OrderReturnRequest } from "@bagodi/api-client";

interface ReturnsViewProps {
  returns: OrderReturnRequest[];
  onReviewReturn: (returnId: string, data: any) => Promise<void>;
  onRestockInspectedReturn: (data: any) => Promise<void>;
}

export const ReturnsView: React.FC<ReturnsViewProps> = ({
  returns,
  onReviewReturn,
  onRestockInspectedReturn,
}) => {
  const [filterType, setFilterType] = useState<string>("ALL");
  const [selectedReturn, setSelectedReturn] = useState<OrderReturnRequest | null>(null);

  // Review form state
  const [adminNotes, setAdminNotes] = useState("");
  const [pickupTrackingId, setPickupTrackingId] = useState("");
  const [isRestockModalOpen, setIsRestockModalOpen] = useState(false);
  const [restockCondition, setRestockCondition] = useState<"PRISTINE" | "DEFECTIVE">("PRISTINE");

  const filteredReturns = returns.filter((r) => {
    if (filterType === "ALL") return true;
    return r.request_type === filterType;
  });

  const handleReviewAction = async (newStatus: "APPROVED" | "REJECTED" | "PICKED_UP" | "RECEIVED" | "COMPLETED") => {
    if (!selectedReturn) return;

    await onReviewReturn(selectedReturn.id, {
      status: newStatus,
      admin_notes: adminNotes.trim() || `Processed as ${newStatus} by store manager`,
      pickup_tracking_id: pickupTrackingId.trim() || null,
      refund_amount: newStatus === "COMPLETED" && selectedReturn.request_type === "RETURN" ? selectedReturn.refund_amount : null,
    });

    setSelectedReturn(null);
    setAdminNotes("");
    setPickupTrackingId("");
  };

  const handleRestockSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReturn) return;

    // Call inventory return endpoint if pristine
    if (restockCondition === "PRISTINE" && selectedReturn.requested_variant_id) {
      await onRestockInspectedReturn({
        variant_id: selectedReturn.requested_variant_id,
        quantity: 1,
        return_id: selectedReturn.id,
        condition: "RESALE_READY",
        notes: "Passed physical inspection: brand tags intact, unworn",
      });
    }

    // Complete return request
    await handleReviewAction("COMPLETED");
    setIsRestockModalOpen(false);
  };

  return (
    <div>
      {/* Sub Tabs */}
      <div className="filter-tabs">
        <button
          className={`filter-tab ${filterType === "ALL" ? "active" : ""}`}
          onClick={() => setFilterType("ALL")}
        >
          All Requests ({returns.length})
        </button>
        <button
          className={`filter-tab ${filterType === "EXCHANGE" ? "active" : ""}`}
          onClick={() => setFilterType("EXCHANGE")}
        >
          Size Exchanges ({returns.filter((r) => r.request_type === "EXCHANGE").length})
        </button>
        <button
          className={`filter-tab ${filterType === "RETURN" ? "active" : ""}`}
          onClick={() => setFilterType("RETURN")}
        >
          Returns & Refunds ({returns.filter((r) => r.request_type === "RETURN").length})
        </button>
      </div>

      <div className="table-container">
        <div className="table-toolbar">
          <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>
            Customer Returns & Size Exchange Requests
          </span>
          <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
            ⚠️ Physical inspection required before any returned garment is accepted back into saleable stock.
          </div>
        </div>

        {filteredReturns.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">
              <RotateCcw size={28} />
            </div>
            <div className="empty-state-title">No Pending Returns or Exchanges</div>
            <div className="empty-state-text">
              Customer size exchange requests or returns submitted for delivered orders will appear here for store inspection.
            </div>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Date Requested</th>
                <th>Request Type</th>
                <th>Reason</th>
                <th>Requested Swap Size</th>
                <th>Customer Notes</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredReturns.map((req) => (
                <tr key={req.id}>
                  <td style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                    {new Date(req.created_at).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                  </td>
                  <td>
                    <span className={`status-pill ${req.request_type === "EXCHANGE" ? "info" : "warning"}`}>
                      {req.request_type === "EXCHANGE" ? "Size Exchange" : "Return & Refund"}
                    </span>
                  </td>
                  <td style={{ fontWeight: 600 }}>{req.reason.replace(/_/g, " ")}</td>
                  <td>
                    {req.requested_size ? (
                      <span className="variant-tag" style={{ background: "var(--brand-terracotta-light)", color: "var(--brand-terracotta)" }}>
                        Swap to Size: {req.requested_size}
                      </span>
                    ) : (
                      <span style={{ color: "var(--text-muted)", fontSize: "0.8125rem" }}>Refund to source</span>
                    )}
                  </td>
                  <td style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", maxWidth: 240 }}>
                    {req.detailed_reason || "—"}
                  </td>
                  <td>
                    <span className={`status-pill ${
                      req.status === "COMPLETED"
                        ? "success"
                        : req.status === "REJECTED"
                        ? "danger"
                        : req.status === "APPROVED" || req.status === "RECEIVED"
                        ? "info"
                        : "warning"
                    }`}>
                      {req.status}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        setSelectedReturn(req);
                        setAdminNotes(req.admin_notes || "");
                      }}
                    >
                      <Eye size={14} />
                      <span>Review</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* REVIEW & INSPECTION MODAL */}
      {selectedReturn && (
        <div className="modal-overlay" onClick={() => setSelectedReturn(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 580 }}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">
                  Review {selectedReturn.request_type === "EXCHANGE" ? "Size Exchange" : "Return"} Request
                </h3>
                <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                  Submitted on {new Date(selectedReturn.created_at).toLocaleString("en-IN")}
                </div>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setSelectedReturn(null)}>
                <X size={16} />
              </button>
            </div>

            <div className="modal-body">
              <div style={{ padding: "0.85rem", background: "var(--bg-subtle)", borderRadius: "var(--radius-sm)" }}>
                <div style={{ fontWeight: 700, fontSize: "0.875rem", marginBottom: "0.4rem" }}>
                  Customer Request Details
                </div>
                <div style={{ fontSize: "0.875rem", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                  <div><strong>Reason:</strong> {selectedReturn.reason.replace(/_/g, " ")}</div>
                  {selectedReturn.requested_size && (
                    <div>
                      <strong>Requested Replacement Size:</strong>{" "}
                      <span className="variant-tag" style={{ background: "var(--brand-terracotta-light)", color: "var(--brand-terracotta)" }}>
                        {selectedReturn.requested_size}
                      </span>
                    </div>
                  )}
                  {selectedReturn.detailed_reason && (
                    <div><strong>Customer Remark:</strong> "{selectedReturn.detailed_reason}"</div>
                  )}
                </div>
              </div>

              {/* Physical Inspection Warning */}
              <div style={{ padding: "0.85rem", background: "var(--citrus-light)", borderLeft: "4px solid var(--citrus-warm)", borderRadius: "var(--radius-xs)", fontSize: "0.8125rem", color: "var(--text-primary)" }}>
                <strong>Quality Assurance Rule:</strong> Garments returned for size exchange must be physically inspected to confirm brand tags are intact and fabric is unaltered before approving replacement dispatch or restocking.
              </div>

              <div className="form-group">
                <label className="form-label">Store Staff Inspection Notes</label>
                <textarea
                  className="form-textarea"
                  rows={2}
                  placeholder="Record condition of the garment, tag verification, and fit exchange notes..."
                  value={adminNotes}
                  onChange={(e) => setAdminNotes(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Pickup / Courier Tracking ID (If applicable)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. BGD-RTO-TRK-9901"
                  value={pickupTrackingId}
                  onChange={(e) => setPickupTrackingId(e.target.value)}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: "0.5rem" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  Current Status: <strong>{selectedReturn.status}</strong>
                </div>

                <div style={{ display: "flex", gap: "0.5rem" }}>
                  {selectedReturn.status === "REQUESTED" && (
                    <>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => handleReviewAction("APPROVED")}
                      >
                        <CheckCircle size={14} />
                        <span>Approve Request</span>
                      </button>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleReviewAction("REJECTED")}
                        style={{ color: "var(--status-danger)" }}
                      >
                        <XCircle size={14} />
                        <span>Reject</span>
                      </button>
                    </>
                  )}

                  {selectedReturn.status === "APPROVED" && (
                    <button
                      className="btn btn-botanical btn-sm"
                      onClick={() => handleReviewAction("RECEIVED")}
                    >
                      <Truck size={14} />
                      <span>Mark Doorstep Pickup Received</span>
                    </button>
                  )}

                  {(selectedReturn.status === "RECEIVED" || selectedReturn.status === "APPROVED") && (
                    <button
                      className="btn btn-botanical btn-sm"
                      onClick={() => setIsRestockModalOpen(true)}
                    >
                      <FileCheck size={14} />
                      <span>Physical Inspection Passed → Restock & Complete</span>
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setSelectedReturn(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RESTOCK CONFIRMATION MODAL */}
      {isRestockModalOpen && selectedReturn && (
        <div className="modal-overlay" onClick={() => setIsRestockModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <h3 className="modal-title">Physical Garment Inspection Check</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsRestockModalOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleRestockSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Garment Condition Verified *</label>
                  <select
                    className="form-select"
                    value={restockCondition}
                    onChange={(e) => setRestockCondition(e.target.value as any)}
                  >
                    <option value="PRISTINE">Pristine / Tags Intact → Return to Saleable Stock (+1 Available)</option>
                    <option value="DEFECTIVE">Damaged / Stained / Washed → Quarantine as Defective</option>
                  </select>
                </div>
                <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", padding: "0.75rem", background: "var(--bg-subtle)", borderRadius: "var(--radius-sm)" }}>
                  Completing this inspection will close the return ticket and update the inventory ledger.
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsRestockModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-botanical">
                  Confirm Inspection & Restock
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
