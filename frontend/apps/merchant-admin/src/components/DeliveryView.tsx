import React, { useState } from "react";
import {
  MapPin,
  Users,
  Car,
  Plus,
  ToggleLeft,
  ToggleRight,
  ShieldCheck,
  X,
  Navigation,
} from "lucide-react";
import type { DeliveryZone, DeliveryPersonnel, DeliveryVehicle } from "../types";

interface DeliveryViewProps {
  zones: DeliveryZone[];
  personnel: DeliveryPersonnel[];
  vehicles: DeliveryVehicle[];
  onCreateZone: (data: any) => Promise<void>;
  onAddPincodesToZone: (zoneId: string, pincodes: string[]) => Promise<void>;
  onCreatePersonnel: (data: any) => Promise<void>;
  onCreateVehicle: (data: any) => Promise<void>;
  onToggleDutyStatus: (personnelId: string, currentStatus: string) => Promise<void>;
}

export const DeliveryView: React.FC<DeliveryViewProps> = ({
  zones,
  personnel,
  vehicles,
  onCreateZone,
  onAddPincodesToZone,
  onCreatePersonnel,
  onCreateVehicle,
  onToggleDutyStatus,
}) => {
  const [activeTab, setActiveTab] = useState<"zones" | "personnel" | "vehicles" | "rider_mode">("zones");

  // Modals
  const [isNewZoneOpen, setIsNewZoneOpen] = useState(false);
  const [isNewPersonnelOpen, setIsNewPersonnelOpen] = useState(false);
  const [isNewVehicleOpen, setIsNewVehicleOpen] = useState(false);
  const [selectedZoneForPincodes, setSelectedZoneForPincodes] = useState<DeliveryZone | null>(null);

  // New Zone form
  const [zoneName, setZoneName] = useState("");
  const [zoneCode, setZoneCode] = useState("");
  const [zoneFee, setZoneFee] = useState("49.00");
  const [zoneThreshold, setZoneThreshold] = useState("1999.00");
  const [zoneHours, setZoneHours] = useState("24");

  // Pincode add form
  const [newPincodeInput, setNewPincodeInput] = useState("");

  // New personnel form
  const [staffName, setStaffName] = useState("");
  const [staffPhone, setStaffPhone] = useState("+91");

  // New vehicle form
  const [vehicleReg, setVehicleReg] = useState("");
  const [vehicleType, setVehicleType] = useState<"TWO_WHEELER" | "THREE_WHEELER" | "VAN">("TWO_WHEELER");
  const [vehicleCapacity, setVehicleCapacity] = useState("30");

  const handleCreateZoneSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!zoneName.trim() || !zoneCode.trim()) return;

    await onCreateZone({
      name: zoneName.trim(),
      code: zoneCode.trim().toUpperCase(),
      base_delivery_fee: zoneFee,
      free_delivery_threshold: zoneThreshold,
      estimated_delivery_hours: parseInt(zoneHours, 10),
      is_active: true,
    });

    setIsNewZoneOpen(false);
    setZoneName("");
    setZoneCode("");
  };

  const handleAddPincodesSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedZoneForPincodes || !newPincodeInput.trim()) return;

    const pincodes = newPincodeInput
      .split(/[\s,]+/)
      .map((p) => p.trim())
      .filter((p) => p.length === 6);

    await onAddPincodesToZone(selectedZoneForPincodes.id, pincodes);
    setSelectedZoneForPincodes(null);
    setNewPincodeInput("");
  };

  const handleCreatePersonnelSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!staffName.trim() || !staffPhone.trim()) return;

    await onCreatePersonnel({
      name: staffName.trim(),
      phone: staffPhone.trim(),
      duty_status: "ON_DUTY",
      is_active: true,
    });

    setIsNewPersonnelOpen(false);
    setStaffName("");
    setStaffPhone("+91");
  };

  const handleCreateVehicleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vehicleReg.trim()) return;

    await onCreateVehicle({
      registration_number: vehicleReg.trim().toUpperCase(),
      vehicle_type: vehicleType,
      capacity_kg: parseFloat(vehicleCapacity),
      status: "ACTIVE",
    });

    setIsNewVehicleOpen(false);
    setVehicleReg("");
  };

  return (
    <div>
      {/* Sub Tabs */}
      <div className="filter-tabs">
        <button
          className={`filter-tab ${activeTab === "zones" ? "active" : ""}`}
          onClick={() => setActiveTab("zones")}
        >
          <MapPin size={16} style={{ display: "inline", verticalAlign: "text-bottom", marginRight: 6 }} />
          Serviceable Zones & PINs ({zones.length})
        </button>
        <button
          className={`filter-tab ${activeTab === "personnel" ? "active" : ""}`}
          onClick={() => setActiveTab("personnel")}
        >
          <Users size={16} style={{ display: "inline", verticalAlign: "text-bottom", marginRight: 6 }} />
          Delivery Riders ({personnel.length})
        </button>
        <button
          className={`filter-tab ${activeTab === "vehicles" ? "active" : ""}`}
          onClick={() => setActiveTab("vehicles")}
        >
          <Car size={16} style={{ display: "inline", verticalAlign: "text-bottom", marginRight: 6 }} />
          Fleet Vehicles ({vehicles.length})
        </button>
        <button
          className={`filter-tab ${activeTab === "rider_mode" ? "active" : ""}`}
          onClick={() => setActiveTab("rider_mode")}
        >
          <Navigation size={16} style={{ display: "inline", verticalAlign: "text-bottom", marginRight: 6 }} />
          Rider View Simulator
        </button>
      </div>

      {/* ZONES SUBVIEW */}
      {activeTab === "zones" && (
        <div className="table-container">
          <div className="table-toolbar">
            <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>Configured Delivery Zones & Postal Codes</span>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setIsNewZoneOpen(true)}
            >
              <Plus size={16} />
              <span>New Delivery Zone</span>
            </button>
          </div>

          {zones.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                <MapPin size={28} />
              </div>
              <div className="empty-state-title">No Delivery Zones Configured</div>
              <div className="empty-state-text">
                Define delivery boundaries and serviceable Indian PIN codes (e.g. Bidar Fort, Gandhi Gunj, Naubad).
              </div>
              <button
                className="btn btn-primary"
                onClick={() => setIsNewZoneOpen(true)}
              >
                <Plus size={16} />
                <span>Configure Delivery Zone</span>
              </button>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Zone Name</th>
                  <th>Code</th>
                  <th>Base Fee</th>
                  <th>Free Threshold</th>
                  <th>Est. Delivery Time</th>
                  <th>PIN Code Coverage</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {zones.map((z) => (
                  <tr key={z.id}>
                    <td style={{ fontWeight: 600 }}>{z.name}</td>
                    <td style={{ fontFamily: "monospace", fontWeight: 700 }}>{z.code}</td>
                    <td>₹{parseFloat(z.base_delivery_fee).toLocaleString("en-IN")}</td>
                    <td>₹{parseFloat(z.free_delivery_threshold).toLocaleString("en-IN")}</td>
                    <td>{z.estimated_delivery_hours} hours</td>
                    <td>
                      <div style={{ display: "flex", gap: "0.25rem", flexWrap: "wrap", maxWidth: 260 }}>
                        {z.pincodes && z.pincodes.length > 0 ? (
                          z.pincodes.map((pin) => (
                            <span key={pin} className="variant-tag">{pin}</span>
                          ))
                        ) : (
                          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>None registered</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => setSelectedZoneForPincodes(z)}
                      >
                        <Plus size={14} />
                        <span>Add PINs</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* PERSONNEL SUBVIEW */}
      {activeTab === "personnel" && (
        <div className="table-container">
          <div className="table-toolbar">
            <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>Delivery Staff & Riders</span>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setIsNewPersonnelOpen(true)}
            >
              <Plus size={16} />
              <span>Add Delivery Staff</span>
            </button>
          </div>

          {personnel.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                <Users size={28} />
              </div>
              <div className="empty-state-title">No Delivery Personnel Registered</div>
              <div className="empty-state-text">
                Register store riders and delivery associates for internal fulfillment in Bidar.
              </div>
              <button
                className="btn btn-primary"
                onClick={() => setIsNewPersonnelOpen(true)}
              >
                <Plus size={16} />
                <span>Register Rider</span>
              </button>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rider Name</th>
                  <th>Phone Number</th>
                  <th>Duty Status</th>
                  <th>Assigned Vehicle</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {personnel.map((p) => {
                  const isOnDuty = p.duty_status === "ON_DUTY";
                  return (
                    <tr key={p.id}>
                      <td style={{ fontWeight: 600 }}>{p.name}</td>
                      <td>{p.phone}</td>
                      <td>
                        <span className={`status-pill ${isOnDuty ? "success" : "muted"}`}>
                          {p.duty_status}
                        </span>
                      </td>
                      <td>{p.vehicle_type || "Two Wheeler"}</td>
                      <td>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => onToggleDutyStatus(p.id, p.duty_status)}
                        >
                          {isOnDuty ? <ToggleRight size={16} color="var(--status-success)" /> : <ToggleLeft size={16} />}
                          <span>{isOnDuty ? "Mark Off Duty" : "Mark On Duty"}</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* VEHICLES SUBVIEW */}
      {activeTab === "vehicles" && (
        <div className="table-container">
          <div className="table-toolbar">
            <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>Delivery Fleet Vehicles</span>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setIsNewVehicleOpen(true)}
            >
              <Plus size={16} />
              <span>Register Vehicle</span>
            </button>
          </div>

          {vehicles.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                <Car size={28} />
              </div>
              <div className="empty-state-title">No Delivery Vehicles Registered</div>
              <div className="empty-state-text">
                Register two-wheelers, electric delivery bikes, or store delivery vans.
              </div>
              <button
                className="btn btn-primary"
                onClick={() => setIsNewVehicleOpen(true)}
              >
                <Plus size={16} />
                <span>Add Vehicle</span>
              </button>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Registration #</th>
                  <th>Vehicle Type</th>
                  <th>Max Capacity</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {vehicles.map((v) => (
                  <tr key={v.id}>
                    <td style={{ fontWeight: 700, fontFamily: "monospace" }}>{v.registration_number}</td>
                    <td>{v.vehicle_type.replace(/_/g, " ")}</td>
                    <td>{v.capacity_kg} kg</td>
                    <td>
                      <span className="status-pill success">{v.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* RIDER VIEW SIMULATOR */}
      {activeTab === "rider_mode" && (
        <div style={{ maxWidth: 540, margin: "0 auto", background: "white", borderRadius: "var(--radius-lg)", border: "1px solid var(--border-light)", padding: "1.5rem", boxShadow: "var(--shadow-card)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid var(--border-light)", paddingBottom: "1rem", marginBottom: "1rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Navigation size={20} color="var(--brand-terracotta)" />
              <div>
                <h4 style={{ fontWeight: 700 }}>Bidar Rider Dispatch Terminal</h4>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Simulated Field App Interface</div>
              </div>
            </div>
            <span className="status-pill success">ON DUTY</span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div style={{ padding: "0.85rem", background: "var(--bg-subtle)", borderRadius: "var(--radius-sm)" }}>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>ACTIVE RUN</div>
              <div style={{ fontWeight: 700, fontSize: "1rem", marginTop: "0.2rem" }}>Route: Bidar Fort → Gole Khana → Naubad</div>
              <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
                Vehicle: KA-38-E-1234 (Hero Electric Scooter)
              </div>
            </div>

            <div style={{ border: "1px solid var(--border-light)", borderRadius: "var(--radius-sm)", padding: "0.85rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 700 }}>Shipment # BGD-SHP-8841</div>
                  <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                    Recipient: Ramesh Patil • +91 9876543210
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    Flat 302, Royal Residency, Near Fort Road, Bidar - 585401
                  </div>
                </div>
                <span className="status-pill info">OUT FOR DELIVERY</span>
              </div>

              <div style={{ marginTop: "0.85rem", display: "flex", gap: "0.5rem" }}>
                <button
                  className="btn btn-botanical btn-sm"
                  style={{ flex: 1 }}
                  onClick={() => alert("Simulated: Delivery confirmed successfully via Delivery OTP verification!")}
                >
                  <ShieldCheck size={14} />
                  <span>Verify OTP & Mark Delivered</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CREATE ZONE MODAL */}
      {isNewZoneOpen && (
        <div className="modal-overlay" onClick={() => setIsNewZoneOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Configure Delivery Zone</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsNewZoneOpen(false)}>
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
                    placeholder="e.g. Bidar Central (Flagship Express)"
                    value={zoneName}
                    onChange={(e) => setZoneName(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Zone Code *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. BIDAR-CITY"
                    value={zoneCode}
                    onChange={(e) => setZoneCode(e.target.value)}
                    required
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Base Delivery Fee (₹)</label>
                    <input
                      type="number"
                      step="0.01"
                      className="form-input"
                      value={zoneFee}
                      onChange={(e) => setZoneFee(e.target.value)}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Free Delivery Threshold (₹)</label>
                    <input
                      type="number"
                      step="0.01"
                      className="form-input"
                      value={zoneThreshold}
                      onChange={(e) => setZoneThreshold(e.target.value)}
                      required
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Estimated Fulfillment Hours</label>
                  <input
                    type="number"
                    className="form-input"
                    value={zoneHours}
                    onChange={(e) => setZoneHours(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsNewZoneOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Zone
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ADD PINCODES MODAL */}
      {selectedZoneForPincodes && (
        <div className="modal-overlay" onClick={() => setSelectedZoneForPincodes(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <h3 className="modal-title">Add PIN Codes to {selectedZoneForPincodes.name}</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setSelectedZoneForPincodes(null)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleAddPincodesSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">6-Digit PIN Codes (Comma or Space Separated) *</label>
                  <textarea
                    className="form-textarea"
                    rows={3}
                    placeholder="e.g. 585401, 585402, 585403"
                    value={newPincodeInput}
                    onChange={(e) => setNewPincodeInput(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setSelectedZoneForPincodes(null)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Add Postal Codes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CREATE PERSONNEL MODAL */}
      {isNewPersonnelOpen && (
        <div className="modal-overlay" onClick={() => setIsNewPersonnelOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="modal-header">
              <h3 className="modal-title">Register Delivery Staff</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsNewPersonnelOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleCreatePersonnelSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Full Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Anand Kumar"
                    value={staffName}
                    onChange={(e) => setStaffName(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Phone Number *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="+919876543210"
                    value={staffPhone}
                    onChange={(e) => setStaffPhone(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsNewPersonnelOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Rider
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CREATE VEHICLE MODAL */}
      {isNewVehicleOpen && (
        <div className="modal-overlay" onClick={() => setIsNewVehicleOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="modal-header">
              <h3 className="modal-title">Register Fleet Vehicle</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsNewVehicleOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleCreateVehicleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Vehicle Registration Number *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. KA-38-E-4567"
                    value={vehicleReg}
                    onChange={(e) => setVehicleReg(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Vehicle Type *</label>
                  <select
                    className="form-select"
                    value={vehicleType}
                    onChange={(e) => setVehicleType(e.target.value as any)}
                  >
                    <option value="TWO_WHEELER">Two Wheeler (Bike / Scooter)</option>
                    <option value="THREE_WHEELER">Three Wheeler (Auto)</option>
                    <option value="VAN">Delivery Van</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Carrying Capacity (kg) *</label>
                  <input
                    type="number"
                    className="form-input"
                    value={vehicleCapacity}
                    onChange={(e) => setVehicleCapacity(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsNewVehicleOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Vehicle
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
