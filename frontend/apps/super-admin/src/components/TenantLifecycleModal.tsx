import React, { useState } from "react";
import { X, ShieldAlert, ShieldCheck, History, AlertTriangle } from "lucide-react";
import { TenantOverview, TenantLifecycleLog } from "../types";

interface TenantLifecycleModalProps {
  isOpen: boolean;
  onClose: () => void;
  tenant: TenantOverview | null;
  lifecycleLogs: TenantLifecycleLog[];
  onUpdateStatus: (
    newStatus: "active" | "suspended" | "pending",
    reason: string
  ) => Promise<void>;
}

export const TenantLifecycleModal: React.FC<TenantLifecycleModalProps> = ({
  isOpen,
  onClose,
  tenant,
  lifecycleLogs,
  onUpdateStatus,
}) => {
  const [targetStatus, setTargetStatus] = useState<"active" | "suspended" | "pending">(
    tenant?.status === "active" ? "suspended" : "active"
  );
  const [reason, setReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen || !tenant) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) return;

    setIsSubmitting(true);
    try {
      await onUpdateStatus(targetStatus, reason.trim());
      setReason("");
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div className="kpi-icon-wrapper terracotta">
              {targetStatus === "suspended" ? (
                <ShieldAlert size={18} />
              ) : (
                <ShieldCheck size={18} />
              )}
            </div>
            <div>
              <h2 className="modal-title">Merchant Lifecycle & Status Control</h2>
              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                {tenant.name} — Current Status: <strong style={{ textTransform: "uppercase" }}>{tenant.status}</strong>
              </p>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {/* Warning Banner if suspending */}
            {targetStatus === "suspended" && (
              <div
                style={{
                  padding: "12px 16px",
                  backgroundColor: "var(--status-error-bg)",
                  border: "1px solid rgba(198, 40, 40, 0.25)",
                  borderRadius: "var(--radius-md)",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "10px",
                  marginBottom: "18px",
                }}
              >
                <AlertTriangle size={18} color="var(--status-error)" style={{ flexShrink: 0, marginTop: "2px" }} />
                <div style={{ fontSize: "0.82rem", color: "var(--status-error)" }}>
                  Suspending this merchant immediately revokes checkout for customer web storefronts and restricts merchant dashboard order dispatch.
                </div>
              </div>
            )}

            <div className="form-group" style={{ marginBottom: "16px" }}>
              <label className="form-label">New Platform Status *</label>
              <select
                className="form-select"
                value={targetStatus}
                onChange={(e) => setTargetStatus(e.target.value as any)}
              >
                <option value="active">Active (Full Retail Operations Permitted)</option>
                <option value="suspended">Suspended (Platform Restriction Enforced)</option>
                <option value="pending">Pending (Awaiting Document Compliance)</option>
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: "22px" }}>
              <label className="form-label">Mandatory Administrative Audit Reason *</label>
              <textarea
                className="form-textarea"
                placeholder="Provide a specific audit justification for this lifecycle transition (e.g. KYC compliance confirmed, trade license expired)..."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                required
              />
            </div>

            {/* Historical Status Timeline */}
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "12px" }}>
                <History size={15} color="var(--text-muted)" />
                <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>
                  Historical Status Audit Log ({lifecycleLogs.length})
                </span>
              </div>

              {lifecycleLogs.length === 0 ? (
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                  No historical status changes recorded yet.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "180px", overflowY: "auto" }}>
                  {lifecycleLogs.map((log) => (
                    <div
                      key={log.id}
                      style={{
                        padding: "10px 14px",
                        backgroundColor: "var(--bg-surface-elevated)",
                        borderRadius: "var(--radius-sm)",
                        borderLeft: `3px solid ${
                          log.new_status === "active"
                            ? "var(--status-success)"
                            : log.new_status === "suspended"
                            ? "var(--status-error)"
                            : "var(--status-warning)"
                        }`,
                        fontSize: "0.8rem",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "3px" }}>
                        <span style={{ fontWeight: 700, textTransform: "uppercase" }}>
                          {log.previous_status} → {log.new_status}
                        </span>
                        <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                          {new Date(log.created_at).toLocaleString("en-IN", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                      <div style={{ color: "var(--text-secondary)" }}>
                        {log.reason || "No reason recorded"}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={`btn ${targetStatus === "suspended" ? "btn-danger" : "btn-primary"}`}
              disabled={isSubmitting || !reason.trim()}
            >
              <span>{isSubmitting ? "Updating..." : `Confirm Transition to ${targetStatus.toUpperCase()}`}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

