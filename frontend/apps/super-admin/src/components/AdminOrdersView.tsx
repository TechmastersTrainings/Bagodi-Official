import React, { useState } from "react";
import {
  ShoppingBag,
  Search,
  PackageCheck,
  Truck,
  CheckCircle,
  XCircle,
  Clock,
  Eye,
  X,
  CreditCard,
  MapPin,
  Calendar,
} from "lucide-react";
import type { AdminOrder } from "../types";

interface AdminOrdersViewProps {
  orders: AdminOrder[];
  onUpdateOrderStatus: (orderId: string, newStatus: string) => Promise<void>;
}

export const AdminOrdersView: React.FC<AdminOrdersViewProps> = ({
  orders,
  onUpdateOrderStatus,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [selectedOrder, setSelectedOrder] = useState<AdminOrder | null>(null);

  const filteredOrders = orders.filter((o) => {
    const matchesSearch =
      !searchQuery ||
      o.order_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (o.shipping_address?.full_name && o.shipping_address.full_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (o.shipping_address?.phone && o.shipping_address.phone.includes(searchQuery));
    const matchesStatus = statusFilter === "ALL" || o.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const totalValue = orders.reduce((acc, o) => acc + (parseFloat(String(o.total_amount)) || 0), 0);
  const confirmedCount = orders.filter((o) => o.status === "CONFIRMED").length;
  const shippedCount = orders.filter((o) => o.status === "SHIPPED").length;
  const deliveredCount = orders.filter((o) => o.status === "DELIVERED").length;

  return (
    <div className="tab-pane">
      {/* Metric Cards */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Total Platform Orders</span>
            <ShoppingBag size={18} color="var(--brand-terracotta)" />
          </div>
          <div className="metric-value">{orders.length}</div>
          <div className="metric-subtext">Gross Volume: ₹{totalValue.toLocaleString("en-IN")}</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Awaiting Packing</span>
            <PackageCheck size={18} color="#f59e0b" />
          </div>
          <div className="metric-value" style={{ color: "#f59e0b" }}>
            {confirmedCount}
          </div>
          <div className="metric-subtext">Confirmed &amp; ready to pack</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Dispatched / Out for Delivery</span>
            <Truck size={18} color="#2563eb" />
          </div>
          <div className="metric-value" style={{ color: "#2563eb" }}>
            {shippedCount}
          </div>
          <div className="metric-subtext">With Bidar delivery riders</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Completed Deliveries</span>
            <CheckCircle size={18} color="#16a34a" />
          </div>
          <div className="metric-value" style={{ color: "#16a34a" }}>
            {deliveredCount}
          </div>
          <div className="metric-subtext">Fulfilled &amp; settled</div>
        </div>
      </div>

      {/* Controls */}
      <div className="table-controls" style={{ marginTop: "1.5rem" }}>
        <div style={{ display: "flex", gap: "0.75rem", flex: 1, alignItems: "center" }}>
          <div className="search-box" style={{ maxWidth: 360 }}>
            <Search size={16} color="var(--text-secondary)" />
            <input
              type="text"
              placeholder="Search by order ID, customer name, phone..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <select
            className="form-select"
            style={{ width: 180 }}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="ALL">All Order Statuses</option>
            <option value="PENDING">Pending Payment</option>
            <option value="CONFIRMED">Confirmed</option>
            <option value="PROCESSING">Packing</option>
            <option value="SHIPPED">Shipped</option>
            <option value="DELIVERED">Delivered</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>
      </div>

      {/* Orders Table */}
      <div className="table-wrapper" style={{ marginTop: "1rem" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Customer &amp; Shipping</th>
              <th>Items &amp; Sizes</th>
              <th>Payable (₹)</th>
              <th>Payment Status</th>
              <th>Fulfillment Status</th>
              <th style={{ textAlign: "right" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredOrders.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                  <ShoppingBag size={32} style={{ margin: "0 auto 0.75rem", display: "block", opacity: 0.4 }} />
                  <div>No orders found.</div>
                </td>
              </tr>
            ) : (
              filteredOrders.map((o) => (
                <tr key={o.id}>
                  <td>
                    <div style={{ fontWeight: 700, color: "var(--brand-terracotta)" }}>{o.order_number}</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {new Date(o.created_at).toLocaleDateString("en-IN", {
                        day: "numeric",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </div>
                  </td>
                  <td>
                    <div style={{ fontWeight: 600 }}>{o.shipping_address?.full_name || "Customer"}</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                      {o.shipping_address?.city || "Bidar"}, {o.shipping_address?.postal_code || "585401"} | {o.shipping_address?.phone || "—"}
                    </div>
                  </td>
                  <td>
                    <div style={{ fontSize: "0.85rem" }}>
                      {o.items && o.items.length > 0 ? (
                        <div>
                          <strong>{o.items[0].product_name}</strong>
                          {o.items[0].size && ` (${o.items[0].size})`}
                          {o.items.length > 1 && (
                            <span style={{ color: "var(--brand-terracotta)", marginLeft: 4, fontWeight: 600 }}>
                              +{o.items.length - 1} more
                            </span>
                          )}
                        </div>
                      ) : (
                        "—"
                      )}
                    </div>
                  </td>
                  <td style={{ fontWeight: 700, fontSize: "0.95rem" }}>
                    ₹{parseFloat(String(o.total_amount)).toLocaleString("en-IN")}
                  </td>
                  <td>
                    <span
                      className={`badge ${o.payment_status === "CAPTURED" || o.payment_status === "SUCCESS"
                          ? "success"
                          : o.payment_status === "PENDING"
                            ? "warning"
                            : "danger"
                        }`}
                      style={{ fontSize: "0.75rem" }}
                    >
                      {o.payment_status}
                    </span>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: 2 }}>
                      {o.payment_method || "COD"}
                    </div>
                  </td>
                  <td>
                    <span className={`status-pill ${o.status === "DELIVERED" ? "success" : o.status === "CANCELLED" ? "danger" : "warning"}`}>
                      {o.status}
                    </span>
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <div style={{ display: "inline-flex", gap: "6px" }}>
                      <button className="btn btn-secondary btn-sm" onClick={() => setSelectedOrder(o)}>
                        <Eye size={14} />
                        <span>Inspect</span>
                      </button>

                      {o.status === "CONFIRMED" && (
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => onUpdateOrderStatus(o.id, "SHIPPED")}
                          style={{ padding: "4px 8px", fontSize: "0.75rem" }}
                        >
                          Dispatch
                        </button>
                      )}
                      {o.status === "SHIPPED" && (
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => onUpdateOrderStatus(o.id, "DELIVERED")}
                          style={{ padding: "4px 8px", fontSize: "0.75rem", background: "#16a34a", borderColor: "#16a34a" }}
                        >
                          Delivered
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* INSPECT MODAL */}
      {selectedOrder && (
        <div className="modal-overlay" onClick={() => setSelectedOrder(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 600 }}>
            <div className="modal-header">
              <h3 className="modal-title">Order Details: {selectedOrder.order_number}</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setSelectedOrder(null)}>
                <X size={16} />
              </button>
            </div>

            <div className="modal-body">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.25rem" }}>
                <div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Customer Info</div>
                  <div style={{ fontWeight: 600 }}>{selectedOrder.shipping_address?.full_name || "Customer"}</div>
                  <div style={{ fontSize: "0.85rem" }}>{selectedOrder.shipping_address?.phone}</div>
                </div>
                <div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Shipping Address</div>
                  <div style={{ fontSize: "0.85rem" }}>
                    {selectedOrder.shipping_address?.address_line1}, {selectedOrder.shipping_address?.city} - {selectedOrder.shipping_address?.postal_code}
                  </div>
                </div>
              </div>

              <div style={{ borderTop: "1px solid var(--border-light)", paddingTop: "1rem" }}>
                <div style={{ fontWeight: 700, fontSize: "0.85rem", marginBottom: "0.5rem" }}>Ordered Items</div>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {selectedOrder.items?.map((item, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        padding: "8px",
                        background: "var(--bg-app)",
                        borderRadius: 4,
                        fontSize: "0.85rem",
                      }}
                    >
                      <div>
                        <strong>{item.product_name}</strong>
                        {item.size && <span style={{ marginLeft: 6, color: "var(--text-muted)" }}>Size: {item.size}</span>}
                        <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Qty: {item.quantity}</div>
                      </div>
                      <div style={{ fontWeight: 700 }}>
                        ₹{parseFloat(String(item.total_price || item.unit_price)).toLocaleString("en-IN")}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ borderTop: "1px solid var(--border-light)", marginTop: "1rem", paddingTop: "0.75rem", display: "flex", justifyContent: "space-between", fontWeight: 700 }}>
                <span>Final Payable Amount:</span>
                <span style={{ color: "var(--brand-terracotta)", fontSize: "1.1rem" }}>
                  ₹{parseFloat(String(selectedOrder.total_amount)).toLocaleString("en-IN")}
                </span>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setSelectedOrder(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

