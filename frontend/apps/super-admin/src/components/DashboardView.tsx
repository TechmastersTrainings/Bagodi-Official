import React from "react";
import {
  TrendingUp,
  Building2,
  Store as StoreIcon,
  ShoppingBag,
  FileCheck2,
  Receipt,
  Activity,
  ArrowUpRight,
  UserCheck,
} from "lucide-react";
import { TenantOverview, PlatformOverviewMetrics, SystemHealth } from "../types";

interface DashboardViewProps {
  metrics: PlatformOverviewMetrics | null;
  systemHealth: SystemHealth | null;
  tenants: TenantOverview[];
  pendingKycCount: number;
  overdueInvoicesCount: number;
  onNavigate: (tab: any) => void;
  onOpenOnboard: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  metrics,
  systemHealth,
  tenants,
  pendingKycCount,
  overdueInvoicesCount,
  onNavigate,
  onOpenOnboard,
}) => {
  const gmv = metrics ? parseFloat(String(metrics.platform_gmv || 0)) : 0;
  const aov = metrics ? parseFloat(String(metrics.platform_average_order_value || 0)) : 0;
  const totalOrders = metrics?.platform_total_orders || 0;
  const activeTenants = tenants.filter((t) => t.status === "active").length;
  const totalStores = tenants.reduce((acc, t) => acc + (t.store_count || 0), 0);

  return (
    <div>
      {/* Platform KPIs */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Platform GMV</span>
            <div className="kpi-icon-wrapper terracotta">
              <TrendingUp size={18} />
            </div>
          </div>
          <div className="kpi-value tabular-nums">
            ₹{gmv.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="kpi-subtext">Cumulative gross fashion merchandise volume</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Total Orders</span>
            <div className="kpi-icon-wrapper sage">
              <ShoppingBag size={18} />
            </div>
          </div>
          <div className="kpi-value tabular-nums">{totalOrders.toLocaleString("en-IN")}</div>
          <div className="kpi-subtext">
            Average Order Value: ₹{aov.toLocaleString("en-IN", { minimumFractionDigits: 0 })}
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Active Merchants</span>
            <div className="kpi-icon-wrapper citrus">
              <Building2 size={18} />
            </div>
          </div>
          <div className="kpi-value tabular-nums">{activeTenants}</div>
          <div className="kpi-subtext">{tenants.length} total registered organizations</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Physical Stores</span>
            <div className="kpi-icon-wrapper neutral">
              <StoreIcon size={18} />
            </div>
          </div>
          <div className="kpi-value tabular-nums">{totalStores}</div>
          <div className="kpi-subtext">Active retail branches & boutiques</div>
        </div>
      </div>

      {/* Operational Attention Grid */}
      <div className="kpi-grid">
        <div
          className="kpi-card"
          style={{ cursor: "pointer", borderColor: pendingKycCount > 0 ? "var(--citrus)" : "var(--border-color)" }}
          onClick={() => onNavigate("kyc")}
        >
          <div className="kpi-header">
            <span className="kpi-title">Pending KYC Verification</span>
            <div className="kpi-icon-wrapper citrus">
              <FileCheck2 size={18} />
            </div>
          </div>
          <div className="kpi-value tabular-nums">{pendingKycCount}</div>
          <div className="kpi-subtext">Merchant compliance documents awaiting approval</div>
        </div>

        <div
          className="kpi-card"
          style={{ cursor: "pointer", borderColor: overdueInvoicesCount > 0 ? "var(--status-error)" : "var(--border-color)" }}
          onClick={() => onNavigate("billing")}
        >
          <div className="kpi-header">
            <span className="kpi-title">Overdue Invoices</span>
            <div className="kpi-icon-wrapper terracotta">
              <Receipt size={18} />
            </div>
          </div>
          <div className="kpi-value tabular-nums">{overdueInvoicesCount}</div>
          <div className="kpi-subtext">Merchant subscription billing settlements pending</div>
        </div>

        <div
          className="kpi-card"
          style={{ cursor: "pointer" }}
          onClick={() => onNavigate("system")}
        >
          <div className="kpi-header">
            <span className="kpi-title">Transactional Outbox Queue</span>
            <div className="kpi-icon-wrapper sage">
              <Activity size={18} />
            </div>
          </div>
          <div className="kpi-value tabular-nums">
            {systemHealth?.pending_outbox_events || 0}
          </div>
          <div className="kpi-subtext">
            {systemHealth?.failed_outbox_events || 0} failed events requiring retry
          </div>
        </div>

        <div
          className="kpi-card"
          style={{ cursor: "pointer" }}
          onClick={() => onNavigate("staff")}
        >
          <div className="kpi-header">
            <span className="kpi-title">Super Admin Governance</span>
            <div className="kpi-icon-wrapper neutral">
              <UserCheck size={18} />
            </div>
          </div>
          <div className="kpi-value tabular-nums">RBAC Active</div>
          <div className="kpi-subtext">Compliance, finance & platform controller roles</div>
        </div>
      </div>

      {/* Quick Action Bar */}
      <div className="table-container" style={{ padding: "18px 24px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "14px" }}>
          <div>
            <h3 style={{ fontSize: "1rem", fontWeight: 700 }}>Platform Governance Quick Actions</h3>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "2px" }}>
              Execute administrative operations across multi-tenant retail partners
            </p>
          </div>
          <div style={{ display: "flex", gap: "12px" }}>
            <button className="btn btn-primary" onClick={onOpenOnboard}>
              <Building2 size={16} />
              <span>Onboard New Merchant</span>
            </button>
            <button className="btn btn-sage" onClick={() => onNavigate("kyc")}>
              <FileCheck2 size={16} />
              <span>Review KYC Documents</span>
            </button>
            <button className="btn btn-secondary" onClick={() => onNavigate("billing")}>
              <Receipt size={16} />
              <span>View Billing Invoices</span>
            </button>
          </div>
        </div>
      </div>

      {/* Recent Merchants Table */}
      <div className="table-container">
        <div className="table-header-bar">
          <span className="table-header-title">Recent Merchant Organizations</span>
          <button className="btn btn-secondary btn-sm" onClick={() => onNavigate("tenants")}>
            <span>View All Merchants</span>
            <ArrowUpRight size={14} />
          </button>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Merchant Name</th>
              <th>Legal Entity & GSTIN</th>
              <th>Status</th>
              <th>KYC Compliance</th>
              <th>Subscription Plan</th>
              <th>Stores</th>
              <th>Onboarded Date</th>
            </tr>
          </thead>
          <tbody>
            {tenants.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: "32px", color: "var(--text-muted)" }}>
                  No merchant organizations registered yet.
                </td>
              </tr>
            ) : (
              tenants.slice(0, 6).map((t) => (
                <tr key={t.id}>
                  <td style={{ fontWeight: 600 }}>{t.name}</td>
                  <td>
                    <div>{t.legal_name || "—"}</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      GST: {t.gstin || "Not provided"}
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
                  <td style={{ fontWeight: 500 }}>{t.current_plan_name || "Standard"}</td>
                  <td className="tabular-nums" style={{ fontWeight: 600 }}>{t.store_count}</td>
                  <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                    {new Date(t.created_at).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
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
