import React, { useState } from "react";
import { Store, Plus, MapPin, Phone, CheckCircle, XCircle, X } from "lucide-react";
import type { PhysicalStore } from "../types";

interface StoreViewProps {
  stores: PhysicalStore[];
  activeStore: PhysicalStore | null;
  onSelectStore: (store: PhysicalStore) => void;
  onCreateStore: (data: any) => Promise<void>;
  onToggleStoreStatus: (storeId: string, currentStatus: string) => Promise<void>;
}

export const StoreView: React.FC<StoreViewProps> = ({
  stores,
  activeStore,
  onSelectStore,
  onCreateStore,
  onToggleStoreStatus,
}) => {
  const [isNewStoreOpen, setIsNewStoreOpen] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [city, setCity] = useState("Bidar");
  const [state, setState] = useState("Karnataka");
  const [postalCode, setPostalCode] = useState("585401");
  const [phone, setPhone] = useState("+91");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !code.trim() || !addressLine.trim()) return;

    await onCreateStore({
      name: name.trim(),
      code: code.trim().toUpperCase(),
      address_line: addressLine.trim(),
      city: city.trim(),
      state: state.trim(),
      postal_code: postalCode.trim(),
      phone: phone.trim() || null,
      status: "active",
    });

    setIsNewStoreOpen(false);
    setName("");
    setCode("");
    setAddressLine("");
  };

  return (
    <div>
      <div className="table-container">
        <div className="table-toolbar">
          <div>
            <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>Physical Retail Branches & Boutiques</span>
            <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
              Manage physical anchor store and planned branch network across Karnataka.
            </div>
          </div>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => setIsNewStoreOpen(true)}
          >
            <Plus size={16} />
            <span>Open New Branch</span>
          </button>
        </div>

        {stores.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">
              <Store size={28} />
            </div>
            <div className="empty-state-title">No Physical Stores Configured</div>
            <div className="empty-state-text">
              Set up the Bagodi flagship retail store in Bidar to manage localized apparel inventory and dispatches.
            </div>
            <button
              className="btn btn-primary"
              onClick={() => setIsNewStoreOpen(true)}
            >
              <Plus size={16} />
              <span>Configure Anchor Flagship</span>
            </button>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.25rem", padding: "1.25rem" }}>
            {stores.map((s) => {
              const isSelected = activeStore?.id === s.id;
              const isActive = s.status === "active";

              return (
                <div
                  key={s.id}
                  style={{
                    background: "white",
                    border: isSelected ? "2px solid var(--brand-terracotta)" : "1px solid var(--border-light)",
                    borderRadius: "var(--radius-md)",
                    padding: "1.25rem",
                    boxShadow: isSelected ? "var(--shadow-card)" : "var(--shadow-sm)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.85rem",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <div style={{ fontWeight: 750, fontSize: "1.1rem", color: "var(--text-primary)" }}>
                        {s.name}
                      </div>
                      <div style={{ fontFamily: "monospace", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        Branch Code: {s.code}
                      </div>
                    </div>
                    <span className={`status-pill ${isActive ? "success" : "muted"}`}>
                      {s.status}
                    </span>
                  </div>

                  <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                      <MapPin size={14} color="var(--brand-terracotta)" />
                      <span>{s.address_line}, {s.city}, {s.state} - {s.postal_code}</span>
                    </div>
                    {s.phone && (
                      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                        <Phone size={14} color="var(--text-muted)" />
                        <span>{s.phone}</span>
                      </div>
                    )}
                  </div>

                  <div style={{ display: "flex", gap: "0.5rem", marginTop: "auto", paddingTop: "0.5rem", borderTop: "1px solid var(--border-light)" }}>
                    <button
                      className={`btn btn-sm ${isSelected ? "btn-primary" : "btn-secondary"}`}
                      style={{ flex: 1 }}
                      onClick={() => onSelectStore(s)}
                    >
                      {isSelected ? "Active Store Context" : "Switch to this Branch"}
                    </button>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => onToggleStoreStatus(s.id, s.status)}
                      title={isActive ? "Deactivate Branch" : "Activate Branch"}
                    >
                      {isActive ? <XCircle size={15} color="var(--status-danger)" /> : <CheckCircle size={15} color="var(--status-success)" />}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* CREATE STORE MODAL */}
      {isNewStoreOpen && (
        <div className="modal-overlay" onClick={() => setIsNewStoreOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Open Physical Store Branch</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsNewStoreOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Store / Boutique Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Bagodi Heritage Flagship"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Store Branch Code *</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. BGD-STR-01"
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Contact Phone</label>
                    <input
                      type="text"
                      className="form-input"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Street Address *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Near Bidar Fort, Main Road"
                    value={addressLine}
                    onChange={(e) => setAddressLine(e.target.value)}
                    required
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">City *</label>
                    <input
                      type="text"
                      className="form-input"
                      value={city}
                      onChange={(e) => setCity(e.target.value)}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">State *</label>
                    <input
                      type="text"
                      className="form-input"
                      value={state}
                      onChange={(e) => setState(e.target.value)}
                      required
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Postal Code (PIN) *</label>
                  <input
                    type="text"
                    className="form-input"
                    value={postalCode}
                    onChange={(e) => setPostalCode(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsNewStoreOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Register Branch
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
