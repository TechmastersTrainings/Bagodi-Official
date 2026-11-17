import React, { useState } from "react";
import {
  Search,
  Plus,
  ShieldCheck,
  ShieldAlert,
  FileCheck2,
  Store,
} from "lucide-react";
import { TenantOverview } from "../types";

interface TenantsViewProps {
  tenants: TenantOverview[];
  onOpenOnboard: () => void;
  onOpenKyc: (tenant: TenantOverview) => void;
  onOpenLifecycle: (tenant: TenantOverview) => void;
}

export const TenantsView: React.FC<TenantsViewProps> = ({
  tenants,
  onOpenOnboard,
  onOpenKyc,
  onOpenLifecycle,
}) => {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const filtered = tenants.filter((t) => {
    const matchesStatus =
      statusFilter === "ALL" || t.status.toUpperCase() === statusFilter;
    const s = search.toLowerCase();
    const matchesSearch =
      !s ||
      t.name.toLowerCase().includes(s) ||
      t.slug.toLowerCase().includes(s) ||
      (t.legal_name && t.legal_name.toLowerCase().includes(s)) ||
      (t.gstin && t.gstin.toLowerCase().includes(s));
    return matchesStatus && matchesSearch;
  });

  return (
    <div>
      {/* Toolbar */}
      <div className="toolbar-container">
        <div className="filter-group">
          <div className="search-input-wrapper">
            <Search size={16} />
            <input
              type="text"
              className="search-input"
              placeholder="Search by merchant, slug, or GSTIN..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <button
            className={`filter-tab ${statusFilter === "ALL" ? "active" : ""}`}
            onClick={() => setStatusFilter("ALL")}
          >
            All ({tenants.length})
          </button>
          <button
            className={`filter-tab ${statusFilter === "ACTIVE" ? "active" : ""}`}
            onClick={() => setStatusFilter("ACTIVE")}
          >
            Active ({tenants.filter((t) => t.status === "active").length})
          </button>
          <button
            className={`filter-tab ${statusFilter === "PENDING" ? "active" : ""}`}
            onClick={() => setStatusFilter("PENDING")}
          >
            Pending ({tenants.filter((t) => t.status === "pending").length})
          </button>
          <button
            className={`filter-tab ${statusFilter === "SUSPENDED" ? "active" : ""}`}
            onClick={() => setStatusFilter("SUSPENDED")}
          >
            Suspended ({tenants.filter((t) => t.status === "suspended").length})
          </button>
        </div>

        <button className="btn btn-primary" onClick={onOpenOnboard}>
          <Plus size={16} />
          <span>Onboard Merchant</span>
        </button>
      </div>

      {/* Tenants Table */}
      <div className="table-container">
        <div className="table-header-bar">
          <span className="table-header-title">
            Registered Merchant Organizations ({filtered.length})
          </span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Merchant Name & Slug</th>
              <th>Legal Entity & Business Type</th>
              <th>GSTIN / PAN</th>
              <th>Status</th>
              <th>KYC Compliance</th>
              <th>Subscription</th>
              <th>Stores</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
                  No merchant organizations match your filter criteria.
                </td>
              </tr>
            ) : (
              filtered.map((t) => (
                <tr key={t.id}>
                  <td>
                    <div style={{ fontWeight: 700, color: "var(--text-primary)" }}>{t.name}</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{t.slug}</div>
                  </td>
                  <td>
                    <div style={{ fontWeight: 500 }}>{t.legal_name || "—"}</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {t.business_type?.replace("_", " ") || "Private Limited"}
                    </div>
                  </td>
                  <td>
                    <div style={{ fontFamily: "monospace", fontSize: "0.8rem", fontWeight: 600 }}>
                      {t.gstin || "No GSTIN"}
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      PAN: {t.pan_number || "—"}
                    </div>
                  </td>
                  <td>
                    <span className={`status-pill ${t.status}`}>
                      {t.status}
                    </span>
                  </td>
                  <td>
                    <span className={`status-pill ${t.kyc_status.toLowerCase()}`}>
                      {t.kyc_status.replace("_", " ")}
                    </span>
                  </td>
                  <td>
                    <span style={{ fontWeight: 600, color: "var(--sage)" }}>
                      {t.current_plan_name || "Starter Retail"}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <Store size={14} color="var(--text-muted)" />
                      <span className="tabular-nums" style={{ fontWeight: 700 }}>
                        {t.store_count}
                      </span>
                    </div>
                  </td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => onOpenKyc(t)}
                        title="Manage KYC verification documents"
                      >
                        <FileCheck2 size={14} />
                        <span>KYC</span>
                      </button>

                      <button
                        className={`btn btn-sm ${t.status === "active" ? "btn-secondary" : "btn-primary"}`}
                        onClick={() => onOpenLifecycle(t)}
                        title="Change activation status or view audit lifecycle history"
                      >
                        {t.status === "active" ? (
                          <>
                            <ShieldAlert size={14} color="var(--status-error)" />
                            <span>Lifecycle</span>
                          </>
                        ) : (
                          <>
                            <ShieldCheck size={14} />
                            <span>Review Status</span>
                          </>
                        )}
                      </button>
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
