import React, { useState } from "react";
import {
  Database,
  Cpu,
  Layers,
  Play,
  AlertTriangle,
} from "lucide-react";
import { SystemHealth, OutboxItem } from "../types";

interface SystemHealthViewProps {
  health: SystemHealth | null;
  outboxItems: OutboxItem[];
  onTriggerWorker: () => Promise<void>;
}

export const SystemHealthView: React.FC<SystemHealthViewProps> = ({
  health,
  outboxItems,
  onTriggerWorker,
}) => {
  const [isProcessing, setIsProcessing] = useState(false);

  const handleTrigger = async () => {
    setIsProcessing(true);
    try {
      await onTriggerWorker();
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div>
      {/* System Diagnostics KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">FastAPI Application</span>
            <div className="kpi-icon-wrapper sage">
              <Cpu size={18} />
            </div>
          </div>
          <div className="kpi-value">{health?.status || "HEALTHY"}</div>
          <div className="kpi-subtext">
            Env: {health?.app_env || "production"} • {health?.app_name || "Bagodi Backend"}
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">PostgreSQL Database</span>
            <div className="kpi-icon-wrapper terracotta">
              <Database size={18} />
            </div>
          </div>
          <div className="kpi-value">{health?.database || "CONNECTED"}</div>
          <div className="kpi-subtext">
            Asyncpg Connection Pool: {health?.pool_size || 20} max connections
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Transactional Outbox Queue</span>
            <div className="kpi-icon-wrapper citrus">
              <Layers size={18} />
            </div>
          </div>
          <div className="kpi-value tabular-nums">{health?.pending_outbox_events || 0}</div>
          <div className="kpi-subtext">Pending transactional domain notifications</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Failed Outbox Events</span>
            <div className="kpi-icon-wrapper neutral">
              <AlertTriangle size={18} />
            </div>
          </div>
          <div className="kpi-value tabular-nums">{health?.failed_outbox_events || 0}</div>
          <div className="kpi-subtext">Dead-letter queue items requiring retry</div>
        </div>
      </div>

      {/* Outbox Queue Monitoring */}
      <div className="table-container">
        <div className="table-header-bar">
          <div>
            <span className="table-header-title">Transactional Notification Outbox Monitoring</span>
            <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Atomically enqueued domain events dispatched to SMS, WhatsApp, and email providers
            </p>
          </div>

          <button
            className="btn btn-sage btn-sm"
            onClick={handleTrigger}
            disabled={isProcessing}
          >
            <Play size={14} className={isProcessing ? "spin" : ""} />
            <span>{isProcessing ? "Triggering Worker..." : "Process Outbox Batch"}</span>
          </button>
        </div>

        <table className="data-table">
          <thead>
            <tr>
              <th>Event ID</th>
              <th>Merchant Tenant</th>
              <th>Domain Event Type</th>
              <th>Aggregate Type & ID</th>
              <th>Status</th>
              <th>Retries</th>
              <th>Created Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {outboxItems.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: "36px", color: "var(--text-muted)" }}>
                  No outbox events currently in queue.
                </td>
              </tr>
            ) : (
              outboxItems.map((item) => (
                <tr key={item.id}>
                  <td style={{ fontFamily: "monospace", fontSize: "0.75rem" }}>
                    {item.id.slice(0, 8)}...
                  </td>
                  <td style={{ fontWeight: 600 }}>{item.tenant_name || "Platform"}</td>
                  <td>
                    <span
                      style={{
                        padding: "3px 8px",
                        backgroundColor: "var(--bg-surface-elevated)",
                        borderRadius: "var(--radius-sm)",
                        fontFamily: "monospace",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                      }}
                    >
                      {item.event_type}
                    </span>
                  </td>
                  <td style={{ fontSize: "0.8rem" }}>
                    {item.aggregate_type} ({item.aggregate_id})
                  </td>
                  <td>
                    <span className={`status-pill ${item.status.toLowerCase()}`}>
                      {item.status}
                    </span>
                  </td>
                  <td className="tabular-nums" style={{ fontWeight: 600 }}>
                    {item.retry_count}
                  </td>
                  <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                    {new Date(item.created_at).toLocaleString("en-IN")}
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
