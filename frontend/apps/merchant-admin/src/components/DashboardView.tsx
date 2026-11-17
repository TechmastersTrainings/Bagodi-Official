import React from "react";
import {
  ShoppingBag,
  AlertTriangle,
  RotateCcw,
  IndianRupee,
  Clock,
  ArrowRight,
  PlusCircle,
  Shirt,
} from "lucide-react";
import type { DashboardMetrics, MerchantOrder, StockBalance } from "../types";

interface DashboardViewProps {
  metrics: DashboardMetrics;
  recentOrders: MerchantOrder[];
  lowStockItems: StockBalance[];
  onNavigateTab: (tab: any) => void;
  onOpenOrder: (order: MerchantOrder) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  metrics,
  recentOrders,
  lowStockItems,
  onNavigateTab,
  onOpenOrder,
}) => {
  return (
    <div>
      {/* KPI Cards Grid */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Net Sales (Today)</span>
            <div className="kpi-icon terracotta">
              <IndianRupee size={18} />
            </div>
          </div>
          <div className="kpi-value">₹{metrics.net_revenue}</div>
          <div className="kpi-subtitle">Gross: ₹{metrics.total_sales}</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Orders Placed</span>
            <div className="kpi-icon sage">
              <ShoppingBag size={18} />
            </div>
          </div>
          <div className="kpi-value">{metrics.total_orders}</div>
          <div className="kpi-subtitle">AOV: ₹{metrics.average_order_value}</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Pending Packing</span>
            <div className="kpi-icon citrus">
              <Clock size={18} />
            </div>
          </div>
          <div className="kpi-value">{metrics.pending_fulfillment}</div>
          <div className="kpi-subtitle">Requires immediate dispatch</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Returns / Exchanges</span>
            <div className="kpi-icon blue">
              <RotateCcw size={18} />
            </div>
          </div>
          <div className="kpi-value">{metrics.returns_count}</div>
          <div className="kpi-subtitle">Physical inspection queue</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Low Stock SKUs</span>
            <div className="kpi-icon terracotta">
              <AlertTriangle size={18} />
            </div>
          </div>
          <div className="kpi-value">{metrics.low_stock_count}</div>
          <div className="kpi-subtitle">Variants below reorder level</div>
        </div>
      </div>

      {/* Quick Action Shortcuts */}
      <div style={{ marginBottom: "2rem" }}>
        <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: "0.85rem", color: "var(--text-primary)" }}>
          Store Quick Actions
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
          <button
            className="btn btn-secondary"
            onClick={() => onNavigateTab("catalog")}
            style={{ justifyContent: "flex-start", padding: "1rem" }}
          >
            <Shirt size={20} color="var(--brand-terracotta)" />
            <div style={{ textAlign: "left" }}>
              <div style={{ fontWeight: 600 }}>New Apparel Product</div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Add garment & sizes</div>
            </div>
          </button>

          <button
            className="btn btn-secondary"
            onClick={() => onNavigateTab("orders")}
            style={{ justifyContent: "flex-start", padding: "1rem" }}
          >
            <ShoppingBag size={20} color="var(--botanical-sage)" />
            <div style={{ textAlign: "left" }}>
              <div style={{ fontWeight: 600 }}>Pack Orders</div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{metrics.pending_fulfillment} pending dispatch</div>
            </div>
          </button>

          <button
            className="btn btn-secondary"
            onClick={() => onNavigateTab("procurement")}
            style={{ justifyContent: "flex-start", padding: "1rem" }}
          >
            <PlusCircle size={20} color="var(--citrus-warm)" />
            <div style={{ textAlign: "left" }}>
              <div style={{ fontWeight: 600 }}>Inward Stock Receipt</div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Receive goods against PO</div>
            </div>
          </button>

          <button
            className="btn btn-secondary"
            onClick={() => onNavigateTab("returns")}
            style={{ justifyContent: "flex-start", padding: "1rem" }}
          >
            <RotateCcw size={20} color="var(--status-info)" />
            <div style={{ textAlign: "left" }}>
              <div style={{ fontWeight: 600 }}>Inspect Returns</div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Process size exchanges</div>
            </div>
          </button>
        </div>
      </div>

      {/* Two Column Section: Recent Orders & Stock Alerts */}
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "1.5rem" }}>
        {/* Recent Orders Stream */}
        <div className="table-container">
          <div className="table-toolbar">
            <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>Live Store Orders</span>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => onNavigateTab("orders")}
            >
              <span>View All</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {recentOrders.length === 0 ? (
            <div style={{ padding: "2.5rem 1.5rem", textAlign: "center", color: "var(--text-secondary)" }}>
              No orders received yet today. Live orders from the Customer Storefront will appear here.
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order #</th>
                  <th>Customer</th>
                  <th>Status</th>
                  <th>Amount</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {recentOrders.slice(0, 5).map((order) => (
                  <tr key={order.id}>
                    <td style={{ fontWeight: 600 }}>{order.order_number}</td>
                    <td>{order.customer_name || "Guest Customer"}</td>
                    <td>
                      <span className={`status-pill ${
                        order.status === "DELIVERED"
                          ? "success"
                          : order.status === "CANCELLED"
                          ? "danger"
                          : order.status === "PROCESSING" || order.status === "DISPATCHED"
                          ? "info"
                          : "warning"
                      }`}>
                        {order.status}
                      </span>
                    </td>
                    <td style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
                      ₹{parseFloat(order.total_amount).toLocaleString("en-IN")}
                    </td>
                    <td>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => onOpenOrder(order)}
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Low Stock Watchlist */}
        <div className="table-container">
          <div className="table-toolbar">
            <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>Low Stock Alerts</span>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => onNavigateTab("inventory")}
            >
              <span>Ledger</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {lowStockItems.length === 0 ? (
            <div style={{ padding: "2.5rem 1.5rem", textAlign: "center", color: "var(--text-secondary)" }}>
              All fashion SKUs are currently above reorder thresholds.
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Variant / SKU</th>
                  <th>Available</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {lowStockItems.slice(0, 5).map((item) => (
                  <tr key={item.id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{item.sku}</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        {item.product_name || "Apparel Item"}
                      </div>
                    </td>
                    <td style={{ fontWeight: 700, color: item.available_qty <= 2 ? "var(--status-danger)" : "var(--citrus-warm)" }}>
                      {item.available_qty} units
                    </td>
                    <td>
                      <span className="status-pill danger">Reorder</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};
