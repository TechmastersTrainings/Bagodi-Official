import React, { useState } from "react";
import {
  ShoppingBag,
  Package,
  Truck,
  CheckCircle,
  XCircle,
  Clock,
  Search,
  Eye,
  X,
  MapPin,
} from "lucide-react";
import type { MerchantOrder } from "../types";

interface OrdersViewProps {
  orders: MerchantOrder[];
  onUpdateOrderStatus: (orderId: string, status: string, notes?: string) => Promise<void>;
  onCancelOrder: (orderId: string, reason: string) => Promise<void>;
  selectedOrder: MerchantOrder | null;
  onSelectOrder: (order: MerchantOrder | null) => void;
}

export const OrdersView: React.FC<OrdersViewProps> = ({
  orders,
  onUpdateOrderStatus,
  onCancelOrder,
  selectedOrder,
  onSelectOrder,
}) => {
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [isCancelModalOpen, setIsCancelModalOpen] = useState(false);

  const filteredOrders = orders.filter((o) => {
    const matchesStatus = statusFilter === "ALL" || o.status === statusFilter;
    const matchesSearch =
      o.order_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (o.customer_name && o.customer_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (o.customer_phone && o.customer_phone.includes(searchQuery));
    return matchesStatus && matchesSearch;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "CONFIRMED":
        return <span className="status-pill warning"><Clock size={12} /> New (Unpacked)</span>;
      case "PROCESSING":
        return <span className="status-pill info"><Package size={12} /> Packed (Ready)</span>;
      case "DISPATCHED":
        return <span className="status-pill info"><Truck size={12} /> Dispatched</span>;
      case "DELIVERED":
        return <span className="status-pill success"><CheckCircle size={12} /> Delivered</span>;
      case "CANCELLED":
        return <span className="status-pill danger"><XCircle size={12} /> Cancelled</span>;
      default:
        return <span className="status-pill muted">{status}</span>;
    }
  };

  const handleStatusTransition = async (newStatus: string) => {
    if (!selectedOrder) return;
    await onUpdateOrderStatus(selectedOrder.id, newStatus, `Transitioned to ${newStatus} by store staff`);
  };

  const handleCancelSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrder || !cancelReason.trim()) return;
    await onCancelOrder(selectedOrder.id, cancelReason.trim());
    setIsCancelModalOpen(false);
    setCancelReason("");
  };

  return (
    <div>
      {/* Status Filter Tabs */}
      <div className="filter-tabs">
        <button
          className={`filter-tab ${statusFilter === "ALL" ? "active" : ""}`}
          onClick={() => setStatusFilter("ALL")}
        >
          All Orders ({orders.length})
        </button>
        <button
          className={`filter-tab ${statusFilter === "CONFIRMED" ? "active" : ""}`}
          onClick={() => setStatusFilter("CONFIRMED")}
        >
          New / To Pack ({orders.filter((o) => o.status === "CONFIRMED").length})
        </button>
        <button
          className={`filter-tab ${statusFilter === "PROCESSING" ? "active" : ""}`}
          onClick={() => setStatusFilter("PROCESSING")}
        >
          Packed ({orders.filter((o) => o.status === "PROCESSING").length})
        </button>
        <button
          className={`filter-tab ${statusFilter === "DISPATCHED" ? "active" : ""}`}
          onClick={() => setStatusFilter("DISPATCHED")}
        >
          Dispatched ({orders.filter((o) => o.status === "DISPATCHED").length})
        </button>
        <button
          className={`filter-tab ${statusFilter === "DELIVERED" ? "active" : ""}`}
          onClick={() => setStatusFilter("DELIVERED")}
        >
          Delivered ({orders.filter((o) => o.status === "DELIVERED").length})
        </button>
      </div>

      <div className="table-container">
        <div className="table-toolbar">
          <div className="table-toolbar-left">
            <div className="search-box" style={{ width: 280 }}>
              <Search size={16} color="var(--text-secondary)" />
              <input
                type="text"
                placeholder="Search Order # or Customer Phone..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>
          <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
            Showing {filteredOrders.length} orders
          </div>
        </div>

        {filteredOrders.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">
              <ShoppingBag size={28} />
            </div>
            <div className="empty-state-title">No Orders Found</div>
            <div className="empty-state-text">
              Orders placed by customers on the Bagodi Storefront will appear here for packing and dispatch.
            </div>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Order #</th>
                <th>Order Date</th>
                <th>Customer & Address</th>
                <th>Garment Line Items</th>
                <th>Payment</th>
                <th>Total</th>
                <th>Fulfillment</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredOrders.map((order) => (
                <tr key={order.id}>
                  <td style={{ fontWeight: 700, fontFamily: "monospace" }}>
                    {order.order_number}
                  </td>
                  <td style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                    {new Date(order.created_at).toLocaleString("en-IN", {
                      dateStyle: "short",
                      timeStyle: "short",
                    })}
                  </td>
                  <td>
                    <div style={{ fontWeight: 600 }}>{order.customer_name || "Valued Customer"}</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {order.customer_phone || (order.shipping_address?.phone) || "—"}
                    </div>
                  </td>
                  <td>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                      {order.items?.map((item, idx) => (
                        <div key={idx} style={{ fontSize: "0.8125rem" }}>
                          {item.product_name}{" "}
                          <span className="variant-tag" style={{ marginLeft: 4 }}>
                            {item.size ? `Size ${item.size}` : item.variant_name}
                          </span>{" "}
                          × <strong>{item.quantity}</strong>
                        </div>
                      ))}
                    </div>
                  </td>
                  <td>
                    <span className={`status-pill ${order.payment_status === "CAPTURED" ? "success" : "warning"}`}>
                      {order.payment_method === "COD" ? "COD Pending" : "Paid Online"}
                    </span>
                  </td>
                  <td style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
                    ₹{parseFloat(order.total_amount).toLocaleString("en-IN")}
                  </td>
                  <td>{getStatusBadge(order.status)}</td>
                  <td>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => onSelectOrder(order)}
                    >
                      <Eye size={14} />
                      <span>Inspect</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ORDER INSPECTION DRAWER / MODAL */}
      {selectedOrder && (
        <div className="modal-overlay" onClick={() => onSelectOrder(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 640 }}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">Order {selectedOrder.order_number}</h3>
                <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                  Placed on {new Date(selectedOrder.created_at).toLocaleString("en-IN")}
                </div>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => onSelectOrder(null)}>
                <X size={16} />
              </button>
            </div>

            <div className="modal-body">
              {/* Delivery Address & Contact */}
              <div style={{ padding: "0.85rem", background: "var(--bg-subtle)", borderRadius: "var(--radius-sm)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontWeight: 700, fontSize: "0.875rem", marginBottom: "0.4rem" }}>
                  <MapPin size={16} color="var(--brand-terracotta)" />
                  <span>Delivery Destination</span>
                </div>
                <div style={{ fontSize: "0.875rem", color: "var(--text-primary)" }}>
                  {selectedOrder.shipping_address ? (
                    <>
                      <div><strong>{selectedOrder.shipping_address.full_name}</strong> • {selectedOrder.shipping_address.phone}</div>
                      <div>{selectedOrder.shipping_address.address_line1}</div>
                      {selectedOrder.shipping_address.landmark && (
                        <div>Landmark: {selectedOrder.shipping_address.landmark}</div>
                      )}
                      <div>{selectedOrder.shipping_address.city}, {selectedOrder.shipping_address.state} - {selectedOrder.shipping_address.postal_code}</div>
                    </>
                  ) : (
                    <div>Bidar Standard Delivery • Contact: {selectedOrder.customer_phone || "+91 9876543210"}</div>
                  )}
                </div>
              </div>

              {/* Items List */}
              <div>
                <div style={{ fontWeight: 700, fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                  Garments in this Shipment ({selectedOrder.items?.length || 0})
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Item Description</th>
                      <th>Qty</th>
                      <th>Unit Price</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedOrder.items?.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <div style={{ fontWeight: 600 }}>{item.product_name}</div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            Size: {item.size || "—"} | SKU: {item.sku}
                          </div>
                        </td>
                        <td style={{ fontWeight: 700 }}>{item.quantity}</td>
                        <td>₹{parseFloat(item.unit_price).toLocaleString("en-IN")}</td>
                        <td style={{ fontWeight: 600 }}>₹{parseFloat(item.total_price).toLocaleString("en-IN")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Order Financials */}
              <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem", padding: "0.85rem", background: "var(--bg-subtle)", borderRadius: "var(--radius-sm)", fontSize: "0.875rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>Bag Subtotal:</span>
                  <span>₹{parseFloat(selectedOrder.subtotal_amount).toLocaleString("en-IN")}</span>
                </div>
                {parseFloat(selectedOrder.discount_amount) > 0 && (
                  <div style={{ display: "flex", justifyContent: "space-between", color: "var(--status-success)" }}>
                    <span>Promotional Discount:</span>
                    <span>- ₹{parseFloat(selectedOrder.discount_amount).toLocaleString("en-IN")}</span>
                  </div>
                )}
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>Delivery Charges:</span>
                  <span>{parseFloat(selectedOrder.delivery_fee) > 0 ? `₹${parseFloat(selectedOrder.delivery_fee).toLocaleString("en-IN")}` : "FREE"}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 750, fontSize: "1.05rem", borderTop: "1px solid var(--border-light)", paddingTop: "0.4rem", marginTop: "0.2rem" }}>
                  <span>Net Payable ({selectedOrder.payment_method}):</span>
                  <span style={{ color: "var(--brand-terracotta)" }}>
                    ₹{parseFloat(selectedOrder.total_amount).toLocaleString("en-IN")}
                  </span>
                </div>
              </div>

              {/* Status Action Workflow Banner */}
              <div style={{ padding: "1rem", background: "var(--brand-terracotta-light)", borderRadius: "var(--radius-sm)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>CURRENT STATE</div>
                  <div style={{ fontWeight: 700, color: "var(--brand-terracotta)" }}>{selectedOrder.status}</div>
                </div>

                <div style={{ display: "flex", gap: "0.5rem" }}>
                  {selectedOrder.status === "CONFIRMED" && (
                    <button
                      className="btn btn-primary"
                      onClick={() => handleStatusTransition("PROCESSING")}
                    >
                      <Package size={16} />
                      <span>Pack & Prepare</span>
                    </button>
                  )}

                  {selectedOrder.status === "PROCESSING" && (
                    <button
                      className="btn btn-botanical"
                      onClick={() => handleStatusTransition("DISPATCHED")}
                    >
                      <Truck size={16} />
                      <span>Mark Dispatched</span>
                    </button>
                  )}

                  {selectedOrder.status === "DISPATCHED" && (
                    <button
                      className="btn btn-primary"
                      onClick={() => handleStatusTransition("DELIVERED")}
                    >
                      <CheckCircle size={16} />
                      <span>Confirm Delivery</span>
                    </button>
                  )}

                  {selectedOrder.status !== "DELIVERED" && selectedOrder.status !== "CANCELLED" && (
                    <button
                      className="btn btn-secondary"
                      onClick={() => setIsCancelModalOpen(true)}
                      style={{ color: "var(--status-danger)" }}
                    >
                      Cancel Order
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => onSelectOrder(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CANCEL ORDER MODAL */}
      {isCancelModalOpen && selectedOrder && (
        <div className="modal-overlay" onClick={() => setIsCancelModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 460 }}>
            <div className="modal-header">
              <h3 className="modal-title">Cancel Order {selectedOrder.order_number}</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsCancelModalOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleCancelSubmit}>
              <div className="modal-body">
                <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                  Cancelling an order immediately releases all reserved apparel variants back into available store stock.
                </p>
                <div className="form-group">
                  <label className="form-label">Cancellation Reason *</label>
                  <textarea
                    className="form-textarea"
                    rows={3}
                    placeholder="e.g. Customer requested cancellation / address unreachable..."
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsCancelModalOpen(false)}>
                  Go Back
                </button>
                <button type="submit" className="btn btn-primary" style={{ backgroundColor: "var(--status-danger)" }}>
                  Confirm Cancellation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
