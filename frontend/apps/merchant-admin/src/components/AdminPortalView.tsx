import React, { useState, useEffect, useCallback } from "react";
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Building2,
  FileText,
  Clock,
  RefreshCw,
  Lock,
} from "lucide-react";
import { client, setTokens, clearAuth, extractApiError } from "@bagodi/api-client";

interface AdminPortalViewProps {
  onNavigateHome: () => void;
}

export const AdminPortalView: React.FC<AdminPortalViewProps> = ({ onNavigateHome }) => {
  // Admin Auth State
  const [adminUser, setAdminUser] = useState<{ id: string; email: string; name: string } | null>(null);
  const [adminEmail, setAdminEmail] = useState("techmastersinnovations@gmail.com");
  const [adminPassword, setAdminPassword] = useState("Fri10Feb@2023");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  // Admin Data State
  const [activeTab, setActiveTab] = useState<"pending" | "directory" | "audit">("pending");
  const [merchants, setMerchants] = useState<any[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleAdminLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    setAuthLoading(true);

    try {
      const resp = await client.POST("/api/v1/auth/login", {
        body: {
          email: adminEmail.trim(),
          password: adminPassword.trim(),
        },
      });

      if (resp.error || !resp.data) {
        const parsed = extractApiError(resp.error);
        setAuthError(parsed.message || "Invalid platform administrator credentials.");
        return;
      }

      setTokens(resp.data.access_token, resp.data.refresh_token);
      setAdminUser({
        id: resp.data.user.id,
        email: resp.data.user.email || adminEmail,
        name: resp.data.user.display_name || "Super Administrator",
      });
      showToast("Super Administrator session authorized.");
    } catch (err) {
      setAuthError(extractApiError(err).message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleAdminLogout = () => {
    clearAuth();
    setAdminUser(null);
    showToast("Signed out of platform governance session.");
  };

  const loadAdminData = useCallback(async () => {
    if (!adminUser) return;
    setIsLoadingData(true);

    try {
      const [merchResp, auditResp] = await Promise.all([
        client.GET("/api/v1/platform/tenants"),
        client.GET("/api/v1/platform/audit-logs"),
      ]);

      if (merchResp.data && Array.isArray(merchResp.data)) {
        setMerchants(merchResp.data);
      }
      if (auditResp.data && Array.isArray(auditResp.data)) {
        setAuditLogs(auditResp.data);
      }
    } catch (err) {
      console.warn("Admin data load notice:", err);
    } finally {
      setIsLoadingData(false);
    }
  }, [adminUser]);

  useEffect(() => {
    if (adminUser) {
      loadAdminData();
    }
  }, [adminUser, loadAdminData]);

  const handleApproveMerchant = async (tenantId: string, brandName: string) => {
    setActionLoadingId(tenantId);
    try {
      const resp = await client.PATCH("/api/v1/platform/tenants/{tenant_id}/status", {
        params: { path: { tenant_id: tenantId } },
        body: {
          status: "active",
          reason: "Approved & Verified by TechMasters Platform Administrator",
        },
      });

      if (resp.error) {
        showToast(extractApiError(resp.error).message);
        return;
      }

      showToast(`Merchant "${brandName}" approved and activated successfully!`);
      loadAdminData();
    } catch (err) {
      showToast(extractApiError(err).message);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleRejectMerchant = async (tenantId: string, brandName: string) => {
    if (!window.confirm(`Are you sure you want to reject the application for "${brandName}"?`)) {
      return;
    }

    setActionLoadingId(tenantId);
    try {
      const resp = await client.PATCH("/api/v1/platform/tenants/{tenant_id}/status", {
        params: { path: { tenant_id: tenantId } },
        body: {
          status: "suspended",
          reason: "Application rejected by TechMasters Platform Administrator",
        },
      });

      if (resp.error) {
        showToast(extractApiError(resp.error).message);
        return;
      }

      showToast(`Merchant "${brandName}" rejected.`);
      loadAdminData();
    } catch (err) {
      showToast(extractApiError(err).message);
    } finally {
      setActionLoadingId(null);
    }
  };

  const pendingMerchants = merchants.filter((m) => m.status === "pending");

  // If Not Authenticated -> Show Admin Login View
  if (!adminUser) {
    return (
      <div className="auth-wrapper">
        <div className="auth-card" style={{ maxWidth: 440 }}>
          <div className="auth-logo" style={{ display: "flex", justifyContent: "center" }}>
            <div className="auth-badge-icon" style={{ background: "rgba(255, 255, 255, 0.08)", color: "#FFFFFF", width: 56, height: 56, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 12, border: "1px solid rgba(255, 255, 255, 0.18)" }}>
              <ShieldAlert size={30} />
            </div>
          </div>
          <h2 style={{ textAlign: "center", fontSize: "1.4rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
            TechMasters Innovations
          </h2>
          <p style={{ textAlign: "center", fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: 20 }}>
            Platform Governance & Merchant Approvals Console
          </p>

          {authError && (
            <div className="auth-error-banner" style={{ marginBottom: 16 }}>
              {authError}
            </div>
          )}

          <form onSubmit={handleAdminLogin}>
            <div className="form-group" style={{ marginBottom: 14 }}>
              <label className="form-label">Administrator Email</label>
              <input
                type="email"
                className="form-input"
                placeholder="techmastersinnovations@gmail.com"
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
                required
              />
            </div>

            <div className="form-group" style={{ marginBottom: 20 }}>
              <label className="form-label">Administrator Password</label>
              <input
                type="password"
                className="form-input"
                placeholder="••••••••"
                value={adminPassword}
                onChange={(e) => setAdminPassword(e.target.value)}
                required
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-full"
              disabled={authLoading}
            >
              <Lock size={16} />
              <span>{authLoading ? "Authenticating Platform Admin..." : "Sign In to Governance Console"}</span>
            </button>
          </form>

          <div style={{ marginTop: 24, textAlign: "center" }}>
            <button type="button" className="btn-link" onClick={onNavigateHome}>
              ← Return to Bagodi Customer Storefront
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Authenticated Admin Console
  return (
    <div className="admin-portal-container">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="storefront-toast">
          <CheckCircle2 size={16} />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Admin Top Banner */}
      <header className="admin-header-bar">
        <div>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: 8 }}>
            <ShieldAlert size={22} color="#FFFFFF" />
            <span>TechMasters Innovations Governance Console</span>
          </h2>
          <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Logged in as {adminUser.name} ({adminUser.email}) • Unrestricted Multi-Tenant Governance
          </span>
        </div>

        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button type="button" className="btn btn-secondary btn-sm" onClick={loadAdminData} disabled={isLoadingData}>
            <RefreshCw size={14} className={isLoadingData ? "animate-spin" : ""} />
            <span>Refresh</span>
          </button>
          <button type="button" className="btn btn-secondary btn-sm" onClick={handleAdminLogout}>
            Sign Out
          </button>
        </div>
      </header>

      {/* Sub Tabs */}
      <div className="filter-tabs" style={{ margin: "1.5rem 0 1rem" }}>
        <button
          type="button"
          className={`filter-tab ${activeTab === "pending" ? "active" : ""}`}
          onClick={() => setActiveTab("pending")}
        >
          <Clock size={16} style={{ display: "inline", marginRight: 6 }} />
          Pending Merchant Approvals ({pendingMerchants.length})
        </button>

        <button
          type="button"
          className={`filter-tab ${activeTab === "directory" ? "active" : ""}`}
          onClick={() => setActiveTab("directory")}
        >
          <Building2 size={16} style={{ display: "inline", marginRight: 6 }} />
          All Registered Merchants ({merchants.length})
        </button>

        <button
          type="button"
          className={`filter-tab ${activeTab === "audit" ? "active" : ""}`}
          onClick={() => setActiveTab("audit")}
        >
          <FileText size={16} style={{ display: "inline", marginRight: 6 }} />
          System Audit Logs ({auditLogs.length})
        </button>
      </div>

      {/* TAB 1: PENDING MERCHANT APPROVALS */}
      {activeTab === "pending" && (
        <div className="table-container">
          <div className="table-toolbar">
            <span style={{ fontWeight: 700, fontSize: "1rem" }}>
              Merchant Onboarding Verification Queue
            </span>
            <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
              Admin approval required before any non-anchor merchant can access the store portal or publish products
            </span>
          </div>

          {pendingMerchants.length === 0 ? (
            <div className="empty-state" style={{ padding: "3rem 1.5rem" }}>
              <CheckCircle2 size={36} color="var(--status-success)" />
              <div className="empty-state-title" style={{ marginTop: 12 }}>
                All Merchant Applications Processed
              </div>
              <div className="empty-state-text">
                There are no merchant boutiques awaiting verification at this time. When a new boutique registers at <code>/merchant</code>, their full legal and banking details will appear here.
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {pendingMerchants.map((m) => (
                <div key={m.id} className="pending-merchant-card" style={{ background: "var(--bg-surface-elevated)", border: "1px solid var(--border-medium)", borderRadius: "var(--radius-md)", padding: "1.25rem", display: "flex", flexDirection: "column", gap: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "1px solid var(--border-light)", paddingBottom: 10 }}>
                    <div>
                      <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-primary)" }}>
                        {m.name}
                      </h3>
                      <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                        Legal Entity: <strong>{m.legal_name || m.name}</strong> • Type: {m.business_type || "Private Limited"}
                      </span>
                    </div>

                    <span className="status-pill warning">
                      Pending Administrator Verification
                    </span>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, fontSize: "0.8125rem" }}>
                    <div>
                      <span style={{ color: "var(--text-muted)", display: "block" }}>Owner / Authorized Representative:</span>
                      <strong>{m.owner_name || "—"}</strong>
                    </div>

                    <div>
                      <span style={{ color: "var(--text-muted)", display: "block" }}>Contact Details:</span>
                      <strong>{m.contact_email}</strong> • {m.contact_phone || "—"}
                    </div>

                    <div>
                      <span style={{ color: "var(--text-muted)", display: "block" }}>Specialization:</span>
                      <strong>{m.category_specialization || "Apparel & Couture"}</strong>
                    </div>

                    <div>
                      <span style={{ color: "var(--text-muted)", display: "block" }}>Tax Identifiers:</span>
                      <span>GSTIN: <strong>{m.gstin || "—"}</strong></span><br />
                      <span>PAN: <strong>{m.pan_number || "—"}</strong></span>
                    </div>

                    <div>
                      <span style={{ color: "var(--text-muted)", display: "block" }}>Bank Disbursal Account:</span>
                      <span>Bank: <strong>{m.bank_name || "—"}</strong></span><br />
                      <span>A/C: <strong>{m.bank_account_number || "—"}</strong> (IFSC: {m.bank_ifsc || "—"})</span>
                    </div>

                    <div>
                      <span style={{ color: "var(--text-muted)", display: "block" }}>Registered Address:</span>
                      <span>{m.registered_address || "—"}</span>
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, borderTop: "1px solid var(--border-light)", paddingTop: 10 }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleRejectMerchant(m.id, m.name)}
                      disabled={actionLoadingId === m.id}
                      style={{ color: "var(--status-danger)" }}
                    >
                      <XCircle size={14} />
                      <span>Reject Application</span>
                    </button>

                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => handleApproveMerchant(m.id, m.name)}
                      disabled={actionLoadingId === m.id}
                      style={{ background: "var(--status-success)", borderColor: "var(--status-success)" }}
                    >
                      <CheckCircle2 size={14} />
                      <span>{actionLoadingId === m.id ? "Activating..." : "Approve & Activate Merchant"}</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: ALL REGISTERED MERCHANTS */}
      {activeTab === "directory" && (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Brand / Store Name</th>
                <th>Legal Name</th>
                <th>Owner Name</th>
                <th>Contact</th>
                <th>GSTIN</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {merchants.map((m) => (
                <tr key={m.id}>
                  <td>
                    <strong>{m.name}</strong>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Slug: /{m.slug}</div>
                  </td>
                  <td>{m.legal_name || m.name}</td>
                  <td>{m.owner_name || "—"}</td>
                  <td>
                    <div>{m.contact_email}</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{m.contact_phone}</div>
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: "0.8125rem" }}>{m.gstin || "—"}</td>
                  <td>
                    <span className={`status-pill ${m.status === "active" ? "success" : (m.status === "pending" ? "warning" : "danger")}`}>
                      {m.status.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    {m.status === "active" ? (
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleRejectMerchant(m.id, m.name)}
                        style={{ fontSize: "0.75rem", padding: "4px 8px", color: "var(--status-danger)" }}
                      >
                        Suspend
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={() => handleApproveMerchant(m.id, m.name)}
                        style={{ fontSize: "0.75rem", padding: "4px 8px", background: "var(--status-success)" }}
                      >
                        Activate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* TAB 3: SYSTEM AUDIT LOGS */}
      {activeTab === "audit" && (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Action</th>
                <th>Target Type</th>
                <th>Actor</th>
                <th>IP Address</th>
              </tr>
            </thead>
            <tbody>
              {auditLogs.map((log) => (
                <tr key={log.id}>
                  <td style={{ fontSize: "0.75rem", whiteSpace: "nowrap" }}>
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td>
                    <span className="status-pill muted">{log.action}</span>
                  </td>
                  <td>{log.target_type} ({log.target_id?.substring(0, 8)}...)</td>
                  <td>{log.actor_email || "System"}</td>
                  <td style={{ fontFamily: "monospace", fontSize: "0.75rem" }}>{log.ip_address || "127.0.0.1"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
