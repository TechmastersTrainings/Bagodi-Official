import React, { useState } from "react";
import {
  Boxes,
  History,
  Search,
  ArrowUpDown,
  X,
} from "lucide-react";
import type { StockBalance, LedgerEntry } from "../types";

interface InventoryViewProps {
  balances: StockBalance[];
  ledger: LedgerEntry[];
  onAdjustStock: (data: any) => Promise<void>;
}

export const InventoryView: React.FC<InventoryViewProps> = ({
  balances,
  ledger,
  onAdjustStock,
}) => {
  const [activeTab, setActiveTab] = useState<"balances" | "ledger">("balances");
  const [searchQuery, setSearchQuery] = useState("");
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [isAdjustModalOpen, setIsAdjustModalOpen] = useState(false);

  // Adjustment form state
  const [selectedVariantId, setSelectedVariantId] = useState("");
  const [adjustType, setAdjustType] = useState<"damage" | "loss" | "reconciliation_gain" | "reconciliation_loss">("damage");
  const [adjustQuantity, setAdjustQuantity] = useState("1");
  const [adjustReason, setAdjustReason] = useState("");

  const filteredBalances = balances.filter((b) => {
    const matchesSearch =
      b.sku.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (b.variant_name && b.variant_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (b.product_name && b.product_name.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesLowStock = !lowStockOnly || b.available_qty <= b.reorder_level;
    return matchesSearch && matchesLowStock;
  });

  const filteredLedger = ledger.filter((l) => {
    return (
      (l.sku && l.sku.toLowerCase().includes(searchQuery.toLowerCase())) ||
      l.movement_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (l.reference_id && l.reference_id.toLowerCase().includes(searchQuery.toLowerCase()))
    );
  });

  const handleAdjustSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedVariantId || !adjustQuantity) return;

    const qty = parseInt(adjustQuantity, 10);
    await onAdjustStock({
      variant_id: selectedVariantId,
      quantity: Math.abs(qty),
      reason: adjustType,
      notes: adjustReason.trim() || `Manual store stock adjustment: ${adjustType}`,
    });

    setIsAdjustModalOpen(false);
    setSelectedVariantId("");
    setAdjustQuantity("1");
    setAdjustReason("");
  };

  return (
    <div>
      {/* Sub Tabs */}
      <div className="filter-tabs">
        <button
          className={`filter-tab ${activeTab === "balances" ? "active" : ""}`}
          onClick={() => setActiveTab("balances")}
        >
          <Boxes size={16} style={{ display: "inline", verticalAlign: "text-bottom", marginRight: 6 }} />
          Variant Stock Balances ({balances.length})
        </button>
        <button
          className={`filter-tab ${activeTab === "ledger" ? "active" : ""}`}
          onClick={() => setActiveTab("ledger")}
        >
          <History size={16} style={{ display: "inline", verticalAlign: "text-bottom", marginRight: 6 }} />
          Immutable Audit Ledger ({ledger.length})
        </button>
      </div>

      {/* BALANCES SUBVIEW */}
      {activeTab === "balances" && (
        <div className="table-container">
          <div className="table-toolbar">
            <div className="table-toolbar-left">
              <div className="search-box" style={{ width: 260 }}>
                <Search size={16} color="var(--text-secondary)" />
                <input
                  type="text"
                  placeholder="Search SKU or Garment..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.8125rem", cursor: "pointer", userSelect: "none" }}>
                <input
                  type="checkbox"
                  checked={lowStockOnly}
                  onChange={(e) => setLowStockOnly(e.target.checked)}
                />
                <span style={{ fontWeight: 600, color: lowStockOnly ? "var(--brand-terracotta)" : "var(--text-secondary)" }}>
                  Low Stock Alerts Only
                </span>
              </label>
            </div>

            <div className="table-toolbar-right">
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setIsAdjustModalOpen(true)}
              >
                <ArrowUpDown size={16} />
                <span>Adjust Stock (Audit/Damage)</span>
              </button>
            </div>
          </div>

          {filteredBalances.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                <Boxes size={28} />
              </div>
              <div className="empty-state-title">No Stock Balances Recorded</div>
              <div className="empty-state-text">
                Stock is recorded atomically when Purchase Orders are received via Inward Goods Receipt.
              </div>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Variant SKU</th>
                  <th>Garment & Spec</th>
                  <th>On Hand</th>
                  <th>Reserved (Hold)</th>
                  <th>Available to Sell</th>
                  <th>Damaged</th>
                  <th>Reorder Level</th>
                  <th>Stock Health</th>
                </tr>
              </thead>
              <tbody>
                {filteredBalances.map((b) => {
                  const isLow = b.available_qty <= b.reorder_level;
                  return (
                    <tr key={b.id || `${b.store_id}-${b.variant_id}`}>
                      <td style={{ fontWeight: 700, fontFamily: "monospace" }}>{b.sku}</td>
                      <td>
                        <div style={{ fontWeight: 600 }}>{b.product_name || "Apparel Item"}</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                          {b.variant_name || "Variant"}
                        </div>
                      </td>
                      <td style={{ fontWeight: 600 }}>{b.on_hand_qty}</td>
                      <td style={{ color: b.reserved_qty > 0 ? "var(--status-info)" : "var(--text-muted)" }}>
                        {b.reserved_qty}
                      </td>
                      <td style={{ fontWeight: 750, color: isLow ? "var(--status-danger)" : "var(--status-success)" }}>
                        {b.available_qty}
                      </td>
                      <td style={{ color: b.damaged_qty > 0 ? "var(--status-danger)" : "var(--text-muted)" }}>
                        {b.damaged_qty}
                      </td>
                      <td>{b.reorder_level}</td>
                      <td>
                        <span className={`status-pill ${isLow ? "danger" : "success"}`}>
                          {isLow ? "Low Stock" : "Healthy"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* IMMUTABLE LEDGER SUBVIEW */}
      {activeTab === "ledger" && (
        <div className="table-container">
          <div className="table-toolbar">
            <div className="table-toolbar-left">
              <div className="search-box" style={{ width: 300 }}>
                <Search size={16} color="var(--text-secondary)" />
                <input
                  type="text"
                  placeholder="Filter by Movement Type, SKU or Ref..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              🔒 Double-entry audit ledger entries are permanent and cryptographically immutable.
            </div>
          </div>

          {filteredLedger.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                <History size={28} />
              </div>
              <div className="empty-state-title">Audit Ledger is Empty</div>
              <div className="empty-state-text">
                Every purchase receipt, checkout reservation, dispatch, inspection, and damage write-off writes an immutable ledger entry.
              </div>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Variant SKU</th>
                  <th>Movement Type</th>
                  <th>Change Qty</th>
                  <th>Balance (Before → After)</th>
                  <th>Reference ID</th>
                  <th>Audit Notes</th>
                </tr>
              </thead>
              <tbody>
                {filteredLedger.map((entry) => {
                  const isPositive = entry.quantity > 0;
                  return (
                    <tr key={entry.id}>
                      <td style={{ fontSize: "0.75rem", color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                        {new Date(entry.created_at).toLocaleString("en-IN", {
                          dateStyle: "short",
                          timeStyle: "medium",
                        })}
                      </td>
                      <td style={{ fontFamily: "monospace", fontWeight: 700 }}>
                        {entry.sku || entry.variant_id.substring(0, 8)}
                      </td>
                      <td>
                        <span className="status-pill muted" style={{ fontSize: "0.7rem" }}>
                          {entry.movement_type}
                        </span>
                      </td>
                      <td style={{ fontWeight: 750, color: isPositive ? "var(--status-success)" : "var(--status-danger)" }}>
                        {isPositive ? `+${entry.quantity}` : entry.quantity}
                      </td>
                      <td style={{ fontVariantNumeric: "tabular-nums" }}>
                        {entry.balance_before} → <strong>{entry.balance_after}</strong>
                      </td>
                      <td style={{ fontFamily: "monospace", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                        {entry.reference_id || "—"}
                      </td>
                      <td style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                        {entry.notes || "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* STOCK ADJUSTMENT MODAL */}
      {isAdjustModalOpen && (
        <div className="modal-overlay" onClick={() => setIsAdjustModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Record Stock Adjustment</h3>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setIsAdjustModalOpen(false)}
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleAdjustSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Garment Variant *</label>
                  <select
                    className="form-select"
                    value={selectedVariantId}
                    onChange={(e) => setSelectedVariantId(e.target.value)}
                    required
                  >
                    <option value="">Select Variant SKU...</option>
                    {balances.map((b) => (
                      <option key={b.variant_id} value={b.variant_id}>
                        {b.sku} — {b.product_name} ({b.available_qty} available)
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Adjustment Reason Type *</label>
                    <select
                      className="form-select"
                      value={adjustType}
                      onChange={(e) => setAdjustType(e.target.value as any)}
                      required
                    >
                      <option value="damage">Damaged Garment / Defect Write-off</option>
                      <option value="loss">Shrinkage / Inventory Loss</option>
                      <option value="reconciliation_gain">Cycle Count Surplus (+)</option>
                      <option value="reconciliation_loss">Cycle Count Shortage (-)</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Units Quantity *</label>
                    <input
                      type="number"
                      min="1"
                      className="form-input"
                      value={adjustQuantity}
                      onChange={(e) => setAdjustQuantity(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Audit Notes & Inspection Reference</label>
                  <textarea
                    className="form-textarea"
                    rows={3}
                    placeholder="Provide justification for stock adjustment (e.g., Zari thread pull defect noted during rack audit)..."
                    value={adjustReason}
                    onChange={(e) => setAdjustReason(e.target.value)}
                  />
                </div>

                <div style={{ padding: "0.75rem", background: "var(--bg-subtle)", borderRadius: "var(--radius-sm)", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                  ⚠️ This action immediately posts an auditable transaction to the double-entry inventory ledger and updates available stock.
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsAdjustModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Commit Stock Adjustment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
