import React, { useState } from "react";
import { Search, Eye, X } from "lucide-react";
import { PlatformAuditLog } from "../types";

interface AuditLogsViewProps {
  logs: PlatformAuditLog[];
}

export const AuditLogsView: React.FC<AuditLogsViewProps> = ({ logs }) => {
  const [search, setSearch] = useState("");
  const [targetFilter, setTargetFilter] = useState("ALL");
  const [inspectingLog, setInspectingLog] = useState<PlatformAuditLog | null>(null);

  const filtered = logs.filter((log) => {
    const matchesTarget =
      targetFilter === "ALL" || log.target_type === targetFilter;
    const s = search.toLowerCase();
    const matchesSearch =
      !s ||
      log.action.toLowerCase().includes(s) ||
      (log.actor_email && log.actor_email.toLowerCase().includes(s)) ||
      (log.target_id && log.target_id.toLowerCase().includes(s));
    return matchesTarget && matchesSearch;
  });

  return (
    <div>
      <div className="toolbar-container">
        <div className="filter-group">
          <div className="search-input-wrapper">
            <Search size={16} />
            <input
              type="text"
              className="search-input"
              placeholder="Search action or actor..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <button
            className={`filter-tab ${targetFilter === "ALL" ? "active" : ""}`}
            onClick={() => setTargetFilter("ALL")}
          >
            All Logs ({logs.length})
          </button>
          <button
            className={`filter-tab ${targetFilter === "TENANT" ? "active" : ""}`}
            onClick={() => setTargetFilter("TENANT")}
          >
            Tenants
          </button>
          <button
            className={`filter-tab ${targetFilter === "KYC" ? "active" : ""}`}
            onClick={() => setTargetFilter("KYC")}
          >
            KYC
          </button>
          <button
            className={`filter-tab ${targetFilter === "INVOICE" ? "active" : ""}`}
            onClick={() => setTargetFilter("INVOICE")}
          >
            Billing
          </button>
          <button
            className={`filter-tab ${targetFilter === "USER" ? "active" : ""}`}
            onClick={() => setTargetFilter("USER")}
          >
            Staff
          </button>
        </div>
      </div>

      <div className="table-container">
        <div className="table-header-bar">
          <span className="table-header-title">
            Immutable Administrative Audit Trail ({filtered.length})
          </span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Action Code</th>
              <th>Target Type & ID</th>
              <th>Actor</th>
              <th>IP Address</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: "36px", color: "var(--text-muted)" }}>
                  No administrative audit records match your query.
                </td>
              </tr>
            ) : (
              filtered.map((log) => (
                <tr key={log.id}>
                  <td style={{ fontSize: "0.8rem", whiteSpace: "nowrap" }}>
                    {new Date(log.created_at).toLocaleString("en-IN", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })}
                  </td>
                  <td>
                    <span
                      style={{
                        padding: "3px 8px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        backgroundColor: log.action.includes("REJECT") || log.action.includes("SUSPEND")
                          ? "var(--status-error-bg)"
                          : log.action.includes("VERIF") || log.action.includes("ACTIV") || log.action.includes("PAID")
                          ? "var(--status-success-bg)"
                          : "var(--bg-surface-elevated)",
                        color: log.action.includes("REJECT") || log.action.includes("SUSPEND")
                          ? "var(--status-error)"
                          : log.action.includes("VERIF") || log.action.includes("ACTIV") || log.action.includes("PAID")
                          ? "var(--status-success)"
                          : "var(--text-primary)",
                        fontFamily: "monospace",
                      }}
                    >
                      {log.action}
                    </span>
                  </td>
                  <td>
                    <div style={{ fontWeight: 600 }}>{log.target_type}</div>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontFamily: "monospace" }}>
                      {log.target_id || "—"}
                    </div>
                  </td>
                  <td style={{ fontSize: "0.8rem" }}>
                    {log.actor_email || "System Engine"}
                  </td>
                  <td style={{ fontSize: "0.78rem", fontFamily: "monospace", color: "var(--text-muted)" }}>
                    {log.ip_address || "Internal"}
                  </td>
                  <td>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => setInspectingLog(log)}
                    >
                      <Eye size={13} />
                      <span>Payload</span>
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Payload Modal */}
      {inspectingLog && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <h2 className="modal-title">Audit Event Payload: {inspectingLog.action}</h2>
              <button className="modal-close-btn" onClick={() => setInspectingLog(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <pre
                style={{
                  backgroundColor: "var(--bg-surface-elevated)",
                  padding: "16px",
                  borderRadius: "var(--radius-md)",
                  fontSize: "0.8rem",
                  fontFamily: "monospace",
                  overflowX: "auto",
                  border: "1px solid var(--border-color)",
                }}
              >
                {JSON.stringify(inspectingLog.details, null, 2)}
              </pre>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setInspectingLog(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
