import React, { useState } from "react";
import {
  Truck,
  MapPin,
  Plus,
  Search,
  CheckCircle,
  XCircle,
  UserCheck,
  X,
  Phone,
  Navigation,
} from "lucide-react";
import type { AdminDeliveryZone, AdminDeliveryPersonnel } from "../types";

interface AdminDeliveryViewProps {
  zones: AdminDeliveryZone[];
  personnel: AdminDeliveryPersonnel[];
  onCreateZone: (data: { name: string; description?: string }) => Promise<void>;
  onAddPincodes: (zoneId: string, pincodes: string[]) => Promise<void>;
  onCreatePersonnel: (data: { name: string; phone_number: string; vehicle_type?: string }) => Promise<void>;
  onToggleDuty: (personnelId: string, currentStatus: "ON_DUTY" | "OFF_DUTY") => Promise<void>;
}

export const AdminDeliveryView: React.FC<AdminDeliveryViewProps> = ({
  zones,
  personnel,
  onCreateZone,
  onAddPincodes,
  onCreatePersonnel,
  onToggleDuty,
}) => {
  const [activeTab, setActiveTab] = useState<"zones" | "riders">("zones");
  const [isZoneModalOpen, setIsZoneModalOpen] = useState(false);
  const [isRiderModalOpen, setIsRiderModalOpen] = useState(false);
  const [isPincodeModalOpen, setIsPincodeModalOpen] = useState(false);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);

  // Forms
  const [zoneName, setZoneName] = useState("");
  const [zoneDesc, setZoneDesc] = useState("");
  const [pincodesInput, setPincodesInput] = useState("");
  const [riderName, setRiderName] = useState("");
  const [riderPhone, setRiderPhone] = useState("");
  const [vehicleType, setVehicleType] = useState("Motorcycle / Two-Wheeler");

  const [submitting, setSubmitting] = useState(false);

  const onDutyCount = personnel.filter((p) => p.duty_status === "ON_DUTY").length;
  const totalPincodes = zones.reduce((acc, z) => acc + (z.serviceable_pincodes?.length || 0), 0);

  const handleCreateZoneSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!zoneName.trim()) return;
    setSubmitting(true);
    try {
      await onCreateZone({ name: zoneName.trim(), description: zoneDesc.trim() || undefined });
      setIsZoneModalOpen(false);
      setZoneName("");
      setZoneDesc("");
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddPincodesSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedZoneId || !pincodesInput.trim()) return;
    setSubmitting(true);
    try {
      const pins = pincodesInput
        .split(/[\s,]+/)
        .map((p) => p.trim())
        .filter((p) => /^\d{6}$/.test(p));
      await onAddPincodes(selectedZoneId, pins);
      setIsPincodeModalOpen(false);
      setPincodesInput("");
      setSelectedZoneId(null);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateRiderSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!riderName.trim() || !riderPhone.trim()) return;
    setSubmitting(true);
    try {
      const cleanPhone = riderPhone.startsWith("+") ? riderPhone.trim() : `+91${riderPhone.replace(/\D/g, "")}`;
      await onCreatePersonnel({
        name: riderName.trim(),
        phone_number: cleanPhone,
        vehicle_type: vehicleType,
      });
      setIsRiderModalOpen(false);
      setRiderName("");
      setRiderPhone("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="tab-pane">
      {/* Metric Cards */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Serviceable Delivery Zones</span>
            <MapPin size={18} color="var(--brand-terracotta)" />
          </div>
          <div className="metric-value">{zones.length}</div>
          <div className="metric-subtext">{totalPincodes} serviceable postal PIN codes</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Active Delivery Fleet</span>
            <Truck size={18} color="#2563eb" />
          </div>
          <div className="metric-value" style={{ color: "#2563eb" }}>
            {personnel.length}
          </div>
          <div className="metric-subtext">Registered courier riders</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Riders On-Duty Now</span>
            <CheckCircle size={18} color="#16a34a" />
          </div>
          <div className="metric-value" style={{ color: "#16a34a" }}>
            {onDutyCount}
          </div>
          <div className="metric-subtext">Ready for immediate parcel dispatch</div>
        </div>
      </div>

      {/* Tabs & Actions */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "1.5rem" }}>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            className={`btn btn-sm ${activeTab === "zones" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setActiveTab("zones")}
          >
            <MapPin size={15} />
            <span>Delivery Zones &amp; Pincodes ({zones.length})</span>
          </button>
          <button
            className={`btn btn-sm ${activeTab === "riders" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setActiveTab("riders")}
          >
            <Truck size={15} />
            <span>Delivery Fleet Riders ({personnel.length})</span>
          </button>
        </div>

        {activeTab === "zones" ? (
          <button className="btn btn-primary" onClick={() => setIsZoneModalOpen(true)}>
            <Plus size={16} />
            <span>Add Delivery Zone</span>
          </button>
        ) : (
          <button className="btn btn-primary" onClick={() => setIsRiderModalOpen(true)}>
            <Plus size={16} />
            <span>Onboard Delivery Rider</span>
          </button>
        )}
      </div>

      {/* Zones Table */}
      {activeTab === "zones" && (
        <div className="table-wrapper" style={{ marginTop: "1rem" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Delivery Zone Name</th>
                <th>Coverage Description</th>
                <th>Serviceable Pincodes</th>
                <th>Status</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {zones.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                    <MapPin size={32} style={{ margin: "0 auto 0.75rem", display: "block", opacity: 0.4 }} />
                    <div>No delivery zones configured. Click &quot;Add Delivery Zone&quot; to configure.</div>
                  </td>
                </tr>
              ) : (
                zones.map((z) => (
                  <tr key={z.id}>
                    <td style={{ fontWeight: 600 }}>{z.name}</td>
                    <td style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>{z.description || "—"}</td>
                    <td>
                      <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", maxWidth: 350 }}>
                        {z.serviceable_pincodes && z.serviceable_pincodes.length > 0 ? (
                          z.serviceable_pincodes.map((pin) => (
                            <span key={pin} className="badge" style={{ fontSize: "0.75rem" }}>
                              {pin}
                            </span>
                          ))
                        ) : (
                          <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>No pincodes assigned</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className="status-pill success">Serviceable</span>
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                          setSelectedZoneId(z.id);
                          setIsPincodeModalOpen(true);
                        }}
                      >
                        <Plus size={14} />
                        <span>Add Pincodes</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Riders Table */}
      {activeTab === "riders" && (
        <div className="table-wrapper" style={{ marginTop: "1rem" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Rider Name</th>
                <th>Contact Phone</th>
                <th>Vehicle Type</th>
                <th>Duty Status</th>
                <th style={{ textAlign: "right" }}>Duty Toggle</th>
              </tr>
            </thead>
            <tbody>
              {personnel.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                    <Truck size={32} style={{ margin: "0 auto 0.75rem", display: "block", opacity: 0.4 }} />
                    <div>No delivery fleet personnel onboarded yet.</div>
                  </td>
                </tr>
              ) : (
                personnel.map((p) => (
                  <tr key={p.id}>
                    <td style={{ fontWeight: 600 }}>{p.name}</td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "0.85rem" }}>
                        <Phone size={13} color="var(--text-muted)" />
                        <span>{p.phone_number}</span>
                      </div>
                    </td>
                    <td style={{ fontSize: "0.85rem" }}>{p.vehicle_type || "Two-Wheeler"}</td>
                    <td>
                      <span className={`status-pill ${p.duty_status === "ON_DUTY" ? "success" : "warning"}`}>
                        {p.duty_status === "ON_DUTY" ? "On Duty" : "Off Duty"}
                      </span>
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => onToggleDuty(p.id, p.duty_status)}
                      >
                        {p.duty_status === "ON_DUTY" ? (
                          <>
                            <XCircle size={14} color="#dc2626" />
                            <span>Mark Off Duty</span>
                          </>
                        ) : (
                          <>
                            <CheckCircle size={14} color="#16a34a" />
                            <span>Mark On Duty</span>
                          </>
                        )}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* CREATE ZONE MODAL */}
      {isZoneModalOpen && (
        <div className="modal-overlay" onClick={() => setIsZoneModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <h3 className="modal-title">Create Delivery Zone</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsZoneModalOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleCreateZoneSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Zone Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Bidar Central &amp; Old City"
                    value={zoneName}
                    onChange={(e) => setZoneName(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Zone Description</label>
                  <textarea
                    className="form-textarea"
                    rows={2}
                    placeholder="Main town market, fort circle, and central avenues..."
                    value={zoneDesc}
                    onChange={(e) => setZoneDesc(e.target.value)}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsZoneModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  Create Zone
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ADD PINCODES MODAL */}
      {isPincodeModalOpen && (
        <div className="modal-overlay" onClick={() => setIsPincodeModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <h3 className="modal-title">Assign Serviceable Pincodes</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsPincodeModalOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleAddPincodesSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Pincodes (Comma or Space Separated) *</label>
                  <textarea
                    className="form-textarea"
                    rows={3}
                    placeholder="585401, 585402, 585403..."
                    value={pincodesInput}
                    onChange={(e) => setPincodesInput(e.target.value)}
                    required
                  />
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
                    Must be valid 6-digit Indian postal codes
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsPincodeModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  Save Pincodes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CREATE RIDER MODAL */}
      {isRiderModalOpen && (
        <div className="modal-overlay" onClick={() => setIsRiderModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <h3 className="modal-title">Onboard Delivery Rider</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsRiderModalOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleCreateRiderSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Rider Full Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Anand Shinde"
                    value={riderName}
                    onChange={(e) => setRiderName(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Mobile Contact Number *</label>
                  <input
                    type="tel"
                    className="form-input"
                    placeholder="9876543210"
                    value={riderPhone}
                    onChange={(e) => setRiderPhone(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Vehicle Type</label>
                  <input
                    type="text"
                    className="form-input"
                    value={vehicleType}
                    onChange={(e) => setVehicleType(e.target.value)}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsRiderModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  Onboard Rider
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

