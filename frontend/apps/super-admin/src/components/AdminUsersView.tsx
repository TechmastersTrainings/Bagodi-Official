import React, { useState } from "react";
import {
  Users,
  Search,
  CheckCircle,
  XCircle,
  ShieldCheck,
  Store,
  UserCheck,
  Building,
  Mail,
  Phone,
  Clock,
  AlertCircle,
} from "lucide-react";
import type { AllPlatformUser, TenantOverview } from "../types";

interface AdminUsersViewProps {
  users: AllPlatformUser[];
  merchants: TenantOverview[];
  onApproveMerchant: (tenantId: string) => Promise<void>;
  onToggleUserStatus: (userId: string, currentStatus: string) => Promise<void>;
}

export const AdminUsersView: React.FC<AdminUsersViewProps> = ({
  users,
  merchants,
  onApproveMerchant,
  onToggleUserStatus,
}) => {
  const [activeTab, setActiveTab] = useState<"all" | "merchants" | "customers" | "admins">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [approvingTenantId, setApprovingTenantId] = useState<string | null>(null);

  const pendingMerchants = merchants.filter((m) => m.status === "pending");
  const activeMerchants = merchants.filter((m) => m.status === "active");
  const customers = users.filter((u) => u.roles.includes("CUSTOMER") || (!u.is_platform_user && !u.tenant_id));
  const admins = users.filter((u) => u.is_platform_user || u.roles.includes("SUPER_ADMIN"));

  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      !searchQuery ||
      (u.display_name && u.display_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (u.email && u.email.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (u.phone_e164 && u.phone_e164.includes(searchQuery)) ||
      (u.tenant_name && u.tenant_name.toLowerCase().includes(searchQuery.toLowerCase()));

    if (!matchesSearch) return false;

    if (activeTab === "customers") return u.roles.includes("CUSTOMER") || (!u.is_platform_user && !u.tenant_id);
    if (activeTab === "merchants") return u.tenant_id !== null || u.roles.some((r) => r.includes("MERCHANT"));
    if (activeTab === "admins") return u.is_platform_user || u.roles.includes("SUPER_ADMIN");
    return true;
  });

  const handleApprove = async (tenantId: string) => {
    setApprovingTenantId(tenantId);
    try {
      await onApproveMerchant(tenantId);
    } finally {
      setApprovingTenantId(null);
    }
  };

  return (
    <div className="tab-pane">
      {/* Metric Cards */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Total Platform Users</span>
            <Users size={18} color="var(--brand-terracotta)" />
          </div>
          <div className="metric-value">{users.length}</div>
          <div className="metric-subtext">Across all platform personas</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Active Retail Customers</span>
            <UserCheck size={18} color="#16a34a" />
          </div>
          <div className="metric-value" style={{ color: "#16a34a" }}>
            {customers.length}
          </div>
          <div className="metric-subtext">Registered shopping accounts</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Active Merchant Boutiques</span>
            <Store size={18} color="#2563eb" />
          </div>
          <div className="metric-value" style={{ color: "#2563eb" }}>
            {activeMerchants.length}
          </div>
          <div className="metric-subtext">Authorized store brands</div>
        </div>

        <div className="metric-card" style={{ borderColor: pendingMerchants.length > 0 ? "#dc2626" : undefined }}>
          <div className="metric-header">
            <span className="metric-label">Pending Boutique Approvals</span>
            <AlertCircle size={18} color={pendingMerchants.length > 0 ? "#dc2626" : "var(--text-muted)"} />
          </div>
          <div className="metric-value" style={{ color: pendingMerchants.length > 0 ? "#dc2626" : "inherit" }}>
            {pendingMerchants.length}
          </div>
          <div className="metric-subtext">
            {pendingMerchants.length > 0 ? "Requires Admin Verification" : "All applications verified"}
          </div>
        </div>
      </div>

      {/* Pending Merchants Action Section (High Priority if any exist) */}
      {pendingMerchants.length > 0 && (
        <div
          style={{
            marginTop: "1.5rem",
            background: "var(--bg-surface)",
            border: "1px solid var(--border-medium)",
            borderRadius: "var(--radius-md)",
            padding: "1.25rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "0.75rem" }}>
            <AlertCircle size={18} color="#F59E0B" />
            <h4 style={{ margin: 0, color: "var(--text-primary)", fontSize: "1rem", fontWeight: 700 }}>
              Pending Merchant Registrations ({pendingMerchants.length})
            </h4>
          </div>
          <p style={{ margin: "0 0 1rem 0", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
            The following boutiques submitted official business registration details and require TechMasters admin approval to activate catalog management and order fulfillment.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {pendingMerchants.map((m) => (
              <div
                key={m.id}
                style={{
                  background: "var(--bg-surface-elevated)",
                  border: "1px solid var(--border-light)",
                  borderRadius: "var(--radius-sm)",
                  padding: "1rem",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "1rem",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>{m.name}</span>
                    <span className="badge warning">PENDING APPROVAL</span>
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "4px" }}>
                    Legal Name: <strong>{m.legal_name || m.name}</strong> | Type: {m.business_type || "Private Limited"}
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                    Email: {m.contact_email} | Phone: {m.contact_phone} | Address: {m.registered_address || "Bidar"}
                  </div>
                </div>

                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    className="btn btn-primary"
                    disabled={approvingTenantId === m.id}
                    onClick={() => handleApprove(m.id)}
                    style={{ background: "#16a34a", borderColor: "#16a34a" }}
                  >
                    <CheckCircle size={15} />
                    <span>{approvingTenantId === m.id ? "Approving..." : "Approve Boutique & Activate"}</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tabs & Controls */}
      <div className="table-controls" style={{ marginTop: "1.5rem" }}>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            className={`btn btn-sm ${activeTab === "all" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setActiveTab("all")}
          >
            All Users ({users.length})
          </button>
          <button
            className={`btn btn-sm ${activeTab === "merchants" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setActiveTab("merchants")}
          >
            Merchants ({merchants.length})
          </button>
          <button
            className={`btn btn-sm ${activeTab === "customers" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setActiveTab("customers")}
          >
            Customers ({customers.length})
          </button>
          <button
            className={`btn btn-sm ${activeTab === "admins" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setActiveTab("admins")}
          >
            Admins ({admins.length})
          </button>
        </div>

        <div className="search-box" style={{ maxWidth: 360 }}>
          <Search size={16} color="var(--text-secondary)" />
          <input
            type="text"
            placeholder="Search users by name, email, phone, tenant..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Users Table */}
      <div className="table-wrapper" style={{ marginTop: "1rem" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>User / Persona</th>
              <th>Contact Details</th>
              <th>Roles &amp; Scopes</th>
              <th>Tenant / Store Context</th>
              <th>Status</th>
              <th>Created Date</th>
              <th style={{ textAlign: "right" }}>Account Status</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                  <Users size={32} style={{ margin: "0 auto 0.75rem", display: "block", opacity: 0.4 }} />
                  <div>No platform users found matching the query.</div>
                </td>
              </tr>
            ) : (
              filteredUsers.map((u) => (
                <tr key={u.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: "50%",
                          background: u.is_platform_user ? "var(--brand-terracotta)" : "#3b82f6",
                          color: "#fff",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontWeight: 700,
                          fontSize: "0.9rem",
                        }}
                      >
                        {(u.display_name || "U").charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600 }}>{u.display_name || "Platform User"}</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>ID: {u.id.slice(0, 8)}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div style={{ fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: "2px" }}>
                      {u.email && (
                        <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                          <Mail size={12} color="var(--text-muted)" />
                          <span>{u.email}</span>
                        </div>
                      )}
                      {u.phone_e164 && (
                        <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                          <Phone size={12} color="var(--text-muted)" />
                          <span>{u.phone_e164}</span>
                        </div>
                      )}
                    </div>
                  </td>
                  <td>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                      {u.roles && u.roles.length > 0 ? (
                        u.roles.map((r) => (
                          <span key={r} className="badge" style={{ fontSize: "0.7rem" }}>
                            {r.replace(/_/g, " ")}
                          </span>
                        ))
                      ) : (
                        <span className="badge" style={{ fontSize: "0.7rem" }}>
                          CUSTOMER
                        </span>
                      )}
                    </div>
                  </td>
                  <td>
                    {u.tenant_name ? (
                      <div style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "0.85rem" }}>
                        <Store size={13} color="var(--brand-terracotta)" />
                        <span style={{ fontWeight: 500 }}>{u.tenant_name}</span>
                      </div>
                    ) : (
                      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Platform Global</span>
                    )}
                  </td>
                  <td>
                    <span className={`status-pill ${u.status === "active" ? "success" : "warning"}`}>
                      {u.status === "active" ? "Active" : "Suspended"}
                    </span>
                  </td>
                  <td style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                    {new Date(u.created_at).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => onToggleUserStatus(u.id, u.status)}
                      title={u.status === "active" ? "Suspend user access" : "Activate user"}
                    >
                      {u.status === "active" ? <XCircle size={14} color="#dc2626" /> : <CheckCircle size={14} color="#16a34a" />}
                      <span style={{ fontSize: "0.75rem" }}>
                        {u.status === "active" ? "Suspend" : "Activate"}
                      </span>
                    </button>
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

