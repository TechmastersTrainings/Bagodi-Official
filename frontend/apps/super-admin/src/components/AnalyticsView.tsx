import React, { useState } from "react";
import {
  TrendingUp,
  Download,
  ShoppingBag,
  Store,
  Layers,
} from "lucide-react";
import { PlatformOverviewMetrics } from "../types";

interface AnalyticsViewProps {
  metrics: PlatformOverviewMetrics | null;
  onExportCsv: () => void;
}

export const AnalyticsView: React.FC<AnalyticsViewProps> = ({
  metrics,
  onExportCsv,
}) => {
  const [timeWindow, setTimeWindow] = useState("last_30_days");

  const gmv = metrics ? parseFloat(String(metrics.platform_gmv || 0)) : 0;
  const aov = metrics ? parseFloat(String(metrics.platform_average_order_value || 0)) : 0;
  const orders = metrics?.platform_total_orders || 0;
  const activeTenants = metrics?.total_active_tenants || 0;
  const stores = metrics?.total_physical_stores || 0;

  return (
    <div>
      {/* Top Filter & Export Bar */}
      <div className="toolbar-container">
        <div className="filter-group">
          <button
            className={`filter-tab ${timeWindow === "last_7_days" ? "active" : ""}`}
            onClick={() => setTimeWindow("last_7_days")}
          >
            Last 7 Days
          </button>
          <button
            className={`filter-tab ${timeWindow === "last_30_days" ? "active" : ""}`}
            onClick={() => setTimeWindow("last_30_days")}
          >
            Last 30 Days
          </button>
          <button
            className={`filter-tab ${timeWindow === "this_month" ? "active" : ""}`}
            onClick={() => setTimeWindow("this_month")}
          >
            This Month
          </button>
          <button
            className={`filter-tab ${timeWindow === "all_time" ? "active" : ""}`}
            onClick={() => setTimeWindow("all_time")}
          >
            All Time
          </button>
        </div>

        <button className="btn btn-secondary" onClick={onExportCsv}>
          <Download size={16} />
          <span>Export Comparative CSV</span>
        </button>
      </div>

      {/* Analytics KPI Cards */}
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
          <div className="kpi-subtext">Gross apparel merchandise turnover</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Orders Processed</span>
            <div className="kpi-icon-wrapper sage">
              <ShoppingBag size={18} />
            </div>
          </div>
          <div className="kpi-value tabular-nums">{orders.toLocaleString("en-IN")}</div>
          <div className="kpi-subtext">Across customer web & store orders</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Average Order Value</span>
            <div className="kpi-icon-wrapper citrus">
              <Layers size={18} />
            </div>
          </div>
          <div className="kpi-value tabular-nums">
            ₹{aov.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </div>
          <div className="kpi-subtext">Basket size per checkout transaction</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Ecosystem Footprint</span>
            <div className="kpi-icon-wrapper neutral">
              <Store size={18} />
            </div>
          </div>
          <div className="kpi-value tabular-nums">{stores} Stores</div>
          <div className="kpi-subtext">{activeTenants} active merchant partners</div>
        </div>
      </div>

      {/* Comparative Merchant Table */}
      <div className="table-container">
        <div className="table-header-bar">
          <span className="table-header-title">Comparative Merchant Turnover & Store Performance</span>
          <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
            Period: {metrics ? new Date(metrics.start_date).toLocaleDateString() : ""} to{" "}
            {metrics ? new Date(metrics.end_date).toLocaleDateString() : ""}
          </span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Merchant Name</th>
              <th>Status</th>
              <th>Stores</th>
              <th>Total Orders</th>
              <th>Gross Merchandise Value</th>
              <th>Active SKUs</th>
              <th>Onboarded Date</th>
            </tr>
          </thead>
          <tbody>
            {!metrics?.tenants || metrics.tenants.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: "36px", color: "var(--text-muted)" }}>
                  No comparative merchant turnover data available for this time window.
                </td>
              </tr>
            ) : (
              metrics.tenants.map((t) => {
                const tenantGmv = parseFloat(String(t.gross_merchandise_value || 0));

                return (
                  <tr key={t.tenant_id}>
                    <td style={{ fontWeight: 700 }}>{t.tenant_name}</td>
                    <td>
                      <span className={`status-pill ${t.status}`}>
                        {t.status}
                      </span>
                    </td>
                    <td className="tabular-nums" style={{ fontWeight: 600 }}>
                      {t.store_count}
                    </td>
                    <td className="tabular-nums">{t.total_orders}</td>
                    <td className="tabular-nums" style={{ fontWeight: 700, color: "var(--primary)" }}>
                      ₹{tenantGmv.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                    </td>
                    <td className="tabular-nums">{t.active_products_count}</td>
                    <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      {new Date(t.created_at).toLocaleDateString("en-IN")}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

