import React, { useState } from "react";
import {
  PackagePlus,
  Users,
  Plus,
  FileCheck,
  Building,
  X,
} from "lucide-react";
import type { Supplier, PurchaseOrder, PhysicalStore } from "../types";
import type { ProductDetail } from "@bagodi/api-client";

interface ProcurementViewProps {
  suppliers: Supplier[];
  purchaseOrders: PurchaseOrder[];
  products: ProductDetail[];
  activeStore: PhysicalStore | null;
  onCreateSupplier: (data: any) => Promise<void>;
  onCreatePurchaseOrder: (data: any) => Promise<void>;
  onReceiveGoods: (data: any) => Promise<void>;
}

export const ProcurementView: React.FC<ProcurementViewProps> = ({
  suppliers,
  purchaseOrders,
  products,
  activeStore,
  onCreateSupplier,
  onCreatePurchaseOrder,
  onReceiveGoods,
}) => {
  const [activeTab, setActiveTab] = useState<"pos" | "suppliers">("pos");

  // Modals
  const [isNewSupplierOpen, setIsNewSupplierOpen] = useState(false);
  const [isNewPOOpen, setIsNewPOOpen] = useState(false);
  const [receivingPO, setReceivingPO] = useState<PurchaseOrder | null>(null);

  // New Supplier form
  const [supName, setSupName] = useState("");
  const [supCode, setSupCode] = useState("");
  const [supContact, setSupContact] = useState("");
  const [supPhone, setSupPhone] = useState("+91");
  const [supEmail, setSupEmail] = useState("");
  const [supGstin, setSupGstin] = useState("");
  const [supCity, setSupCity] = useState("Bidar");

  // New PO form
  const [poSupplierId, setPoSupplierId] = useState("");
  const [poVariantId, setPoVariantId] = useState("");
  const [poQuantity, setPoQuantity] = useState("50");
  const [poUnitCost, setPoUnitCost] = useState("1200.00");

  // Receipt form
  const [receiptInvoice, setReceiptInvoice] = useState("");
  const [receiptQty, setReceiptQty] = useState("");

  const handleCreateSupplierSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supName.trim() || !supCode.trim() || !supPhone.trim()) return;

    await onCreateSupplier({
      name: supName.trim(),
      code: supCode.trim().toUpperCase(),
      contact_person: supContact.trim() || null,
      phone: supPhone.trim(),
      email: supEmail.trim() || null,
      gstin: supGstin.trim() || null,
      city: supCity.trim() || "Bidar",
      state: "Karnataka",
      is_active: true,
    });

    setIsNewSupplierOpen(false);
    setSupName("");
    setSupCode("");
    setSupContact("");
    setSupPhone("+91");
    setSupEmail("");
    setSupGstin("");
  };

  const handleCreatePOSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!poSupplierId || !poVariantId || !activeStore) return;

    await onCreatePurchaseOrder({
      store_id: activeStore.id,
      supplier_id: poSupplierId,
      po_number: `PO-BGD-${Date.now().toString().slice(-6)}`,
      items: [
        {
          variant_id: poVariantId,
          quantity_ordered: parseInt(poQuantity, 10),
          unit_cost: poUnitCost,
        },
      ],
    });

    setIsNewPOOpen(false);
    setPoSupplierId("");
    setPoVariantId("");
    setPoQuantity("50");
    setPoUnitCost("1200.00");
  };

  const handleReceiveGoodsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!receivingPO || !receiptInvoice.trim()) return;

    const firstItem = receivingPO.items[0];
    const qty = parseInt(receiptQty, 10) || firstItem?.quantity_ordered || 1;

    await onReceiveGoods({
      purchase_order_id: receivingPO.id,
      store_id: receivingPO.store_id,
      receipt_number: `RCP-BGD-${Date.now().toString().slice(-6)}`,
      invoice_number: receiptInvoice.trim(),
      items: [
        {
          variant_id: firstItem.variant_id,
          quantity_received: qty,
          unit_cost: firstItem.unit_cost,
        },
      ],
    });

    setReceivingPO(null);
    setReceiptInvoice("");
    setReceiptQty("");
  };

  // Flatten available variants for selection
  const allVariants = products.flatMap((p) =>
    (p.variants || []).map((v: any) => ({
      ...v,
      product_name: p.name,
    }))
  );

  return (
    <div>
      {/* Sub Tabs */}
      <div className="filter-tabs">
        <button
          className={`filter-tab ${activeTab === "pos" ? "active" : ""}`}
          onClick={() => setActiveTab("pos")}
        >
          <PackagePlus size={16} style={{ display: "inline", verticalAlign: "text-bottom", marginRight: 6 }} />
          Purchase Orders ({purchaseOrders.length})
        </button>
        <button
          className={`filter-tab ${activeTab === "suppliers" ? "active" : ""}`}
          onClick={() => setActiveTab("suppliers")}
        >
          <Users size={16} style={{ display: "inline", verticalAlign: "text-bottom", marginRight: 6 }} />
          Suppliers Directory ({suppliers.length})
        </button>
      </div>

      {/* PURCHASE ORDERS TAB */}
      {activeTab === "pos" && (
        <div className="table-container">
          <div className="table-toolbar">
            <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>Inward Procurement Orders</span>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setIsNewPOOpen(true)}
            >
              <Plus size={16} />
              <span>Raise Purchase Order</span>
            </button>
          </div>

          {purchaseOrders.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                <PackagePlus size={28} />
              </div>
              <div className="empty-state-title">No Purchase Orders Found</div>
              <div className="empty-state-text">
                Raise purchase orders to artisan handloom clusters or garment suppliers to replenish stock.
              </div>
              <button
                className="btn btn-primary"
                onClick={() => setIsNewPOOpen(true)}
              >
                <Plus size={16} />
                <span>Create Purchase Order</span>
              </button>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>PO Number</th>
                  <th>Supplier</th>
                  <th>Line Items</th>
                  <th>Total Cost</th>
                  <th>PO Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {purchaseOrders.map((po) => {
                  const sup = suppliers.find((s) => s.id === po.supplier_id);
                  return (
                    <tr key={po.id}>
                      <td style={{ fontWeight: 700, fontFamily: "monospace" }}>{po.po_number}</td>
                      <td>
                        <div style={{ fontWeight: 600 }}>{sup?.name || po.supplier_name || "Supplier"}</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{sup?.code}</div>
                      </td>
                      <td>
                        {po.items.map((item, idx) => (
                          <div key={idx} style={{ fontSize: "0.8125rem" }}>
                            {item.sku} × <strong>{item.quantity_ordered}</strong> pcs
                            {item.quantity_received > 0 && (
                              <span style={{ color: "var(--status-success)", marginLeft: 6 }}>
                                (Received: {item.quantity_received})
                              </span>
                            )}
                          </div>
                        ))}
                      </td>
                      <td style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
                        ₹{parseFloat(po.total_amount).toLocaleString("en-IN")}
                      </td>
                      <td>
                        <span className={`status-pill ${
                          po.status === "COMPLETED"
                            ? "success"
                            : po.status === "APPROVED" || po.status === "PARTIALLY_RECEIVED"
                            ? "info"
                            : "warning"
                        }`}>
                          {po.status}
                        </span>
                      </td>
                      <td>
                        {po.status !== "COMPLETED" && (
                          <button
                            className="btn btn-botanical btn-sm"
                            onClick={() => {
                              setReceivingPO(po);
                              setReceiptQty(po.items[0]?.quantity_ordered?.toString() || "10");
                            }}
                          >
                            <FileCheck size={14} />
                            <span>Receive Goods</span>
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* SUPPLIERS TAB */}
      {activeTab === "suppliers" && (
        <div className="table-container">
          <div className="table-toolbar">
            <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>Apparel & Fabric Suppliers</span>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setIsNewSupplierOpen(true)}
            >
              <Plus size={16} />
              <span>Register Supplier</span>
            </button>
          </div>

          {suppliers.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                <Building size={28} />
              </div>
              <div className="empty-state-title">No Suppliers Registered</div>
              <div className="empty-state-text">
                Register weaver cooperatives, Chanderi fabric mills, or ethnic apparel manufacturers.
              </div>
              <button
                className="btn btn-primary"
                onClick={() => setIsNewSupplierOpen(true)}
              >
                <Plus size={16} />
                <span>Register Supplier</span>
              </button>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Supplier Name</th>
                  <th>Code</th>
                  <th>Contact Person</th>
                  <th>Phone / Email</th>
                  <th>City / State</th>
                  <th>GSTIN</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {suppliers.map((s) => (
                  <tr key={s.id}>
                    <td style={{ fontWeight: 600 }}>{s.name}</td>
                    <td style={{ fontFamily: "monospace", fontWeight: 700 }}>{s.code}</td>
                    <td>{s.contact_person || "—"}</td>
                    <td>
                      <div>{s.phone}</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{s.email || "—"}</div>
                    </td>
                    <td>{s.city || "Bidar"}, Karnataka</td>
                    <td style={{ fontFamily: "monospace", fontSize: "0.75rem" }}>{s.gstin || "—"}</td>
                    <td>
                      <span className="status-pill success">Active</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* CREATE SUPPLIER MODAL */}
      {isNewSupplierOpen && (
        <div className="modal-overlay" onClick={() => setIsNewSupplierOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Register Procurement Supplier</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsNewSupplierOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleCreateSupplierSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Supplier / Mill Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Bidar Handloom Weavers Cooperative"
                    value={supName}
                    onChange={(e) => setSupName(e.target.value)}
                    required
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Supplier Code *</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. BGD-SUP-01"
                      value={supCode}
                      onChange={(e) => setSupCode(e.target.value)}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Contact Person</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. Raghavendra Rao"
                      value={supContact}
                      onChange={(e) => setSupContact(e.target.value)}
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Phone *</label>
                    <input
                      type="text"
                      className="form-input"
                      value={supPhone}
                      onChange={(e) => setSupPhone(e.target.value)}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Email</label>
                    <input
                      type="email"
                      className="form-input"
                      placeholder="accounts@supplier.in"
                      value={supEmail}
                      onChange={(e) => setSupEmail(e.target.value)}
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">GSTIN</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="29AAAAA0000A1Z5"
                      value={supGstin}
                      onChange={(e) => setSupGstin(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">City</label>
                    <input
                      type="text"
                      className="form-input"
                      value={supCity}
                      onChange={(e) => setSupCity(e.target.value)}
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsNewSupplierOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Supplier
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* RAISE PO MODAL */}
      {isNewPOOpen && (
        <div className="modal-overlay" onClick={() => setIsNewPOOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Raise Purchase Order</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsNewPOOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleCreatePOSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Destination Store Branch *</label>
                  <input
                    type="text"
                    className="form-input"
                    value={activeStore?.name || "Bagodi Heritage Flagship (Bidar)"}
                    disabled
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Supplier *</label>
                  <select
                    className="form-select"
                    value={poSupplierId}
                    onChange={(e) => setPoSupplierId(e.target.value)}
                    required
                  >
                    <option value="">Select Supplier...</option>
                    {suppliers.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.code})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Garment Variant *</label>
                  <select
                    className="form-select"
                    value={poVariantId}
                    onChange={(e) => setPoVariantId(e.target.value)}
                    required
                  >
                    <option value="">Select Apparel Variant...</option>
                    {allVariants.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.product_name} — Size {v.size} / {v.color} ({v.sku})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Units to Order *</label>
                    <input
                      type="number"
                      min="1"
                      className="form-input"
                      value={poQuantity}
                      onChange={(e) => setPoQuantity(e.target.value)}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Unit Cost (₹) *</label>
                    <input
                      type="number"
                      step="0.01"
                      className="form-input"
                      value={poUnitCost}
                      onChange={(e) => setPoUnitCost(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div style={{ padding: "0.75rem", background: "var(--bg-subtle)", borderRadius: "var(--radius-sm)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>Estimated Total PO Cost:</span>
                  <span style={{ fontSize: "1.1rem", fontWeight: 750, color: "var(--brand-terracotta)" }}>
                    ₹{(parseInt(poQuantity || "0", 10) * parseFloat(poUnitCost || "0")).toLocaleString("en-IN")}
                  </span>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsNewPOOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Raise Purchase Order
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* GOODS RECEIPT MODAL */}
      {receivingPO && (
        <div className="modal-overlay" onClick={() => setReceivingPO(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">Inward Goods Receipt</h3>
                <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                  Against PO: {receivingPO.po_number}
                </div>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setReceivingPO(null)}>
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleReceiveGoodsSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Supplier Invoice / Delivery Challan # *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. INV-BGD-2026-889"
                    value={receiptInvoice}
                    onChange={(e) => setReceiptInvoice(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Quantity Accepted into Physical Stock *</label>
                  <input
                    type="number"
                    min="1"
                    className="form-input"
                    value={receiptQty}
                    onChange={(e) => setReceiptQty(e.target.value)}
                    required
                  />
                </div>

                <div style={{ padding: "0.75rem", background: "var(--botanical-light)", color: "var(--botanical-sage)", borderRadius: "var(--radius-sm)", fontSize: "0.8125rem" }}>
                  ✓ Inward receipt posts an atomic <strong>PURCHASE_RECEIPT</strong> entry to the immutable ledger and immediately increases available stock for online customer checkout.
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setReceivingPO(null)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-botanical">
                  Accept Stock Receipt
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
