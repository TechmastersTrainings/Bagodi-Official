import React, { useState } from "react";
import {
  Users,
  UserPlus,
  Search,
  Shield,
  Phone,
  Mail,
  CheckCircle,
  XCircle,
  Trash2,
  X,
  Store,
} from "lucide-react";
import type { MerchantStaffMember } from "../types";

interface MerchantUsersViewProps {
  staffMembers: MerchantStaffMember[];
  onCreateStaff: (data: {
    display_name: string;
    email: string;
    phone_e164: string;
    password: string;
    role: string;
  }) => Promise<void>;
  onToggleStatus: (userId: string) => Promise<void>;
  onDeleteStaff: (userId: string) => Promise<void>;
}

export const MerchantUsersView: React.FC<MerchantUsersViewProps> = ({
  staffMembers,
  onCreateStaff,
  onToggleStatus,
  onDeleteStaff,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("ALL");
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Form State
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("STORE_MANAGER");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const filteredStaff = staffMembers.filter((m) => {
    const matchesSearch =
      !searchQuery ||
      (m.display_name && m.display_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (m.email && m.email.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (m.phone_e164 && m.phone_e164.includes(searchQuery));

    const matchesRole = roleFilter === "ALL" || m.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  const activeCount = staffMembers.filter((m) => m.status === "active").length;
  const managersCount = staffMembers.filter((m) => m.role.includes("MANAGER") || m.role.includes("OWNER")).length;
  const staffCount = staffMembers.filter((m) => !m.role.includes("MANAGER") && !m.role.includes("OWNER")).length;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSubmitting(true);
    try {
      const cleanPhone = phone.startsWith("+") ? phone.trim() : `+91${phone.replace(/\D/g, "")}`;
      await onCreateStaff({
        display_name: displayName.trim(),
        email: email.trim(),
        phone_e164: cleanPhone,
        password: password.trim(),
        role,
      });
      setIsModalOpen(false);
      setDisplayName("");
      setEmail("");
      setPhone("");
      setPassword("");
      setRole("STORE_MANAGER");
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to add staff member.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="tab-pane">
      {/* Metrics Row */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Total Store Personnel</span>
            <Users size={18} color="var(--brand-terracotta)" />
          </div>
          <div className="metric-value">{staffMembers.length}</div>
          <div className="metric-subtext">Registered boutique staff</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Active &amp; On-Duty</span>
            <CheckCircle size={18} color="#16a34a" />
          </div>
          <div className="metric-value" style={{ color: "#16a34a" }}>
            {activeCount}
          </div>
          <div className="metric-subtext">Authorized to operate till &amp; orders</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Store Managers</span>
            <Shield size={18} color="#2563eb" />
          </div>
          <div className="metric-value" style={{ color: "#2563eb" }}>
            {managersCount}
          </div>
          <div className="metric-subtext">Store leadership &amp; supervisory</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Floor Associates</span>
            <Store size={18} color="var(--brand-gold)" />
          </div>
          <div className="metric-value" style={{ color: "var(--brand-gold)" }}>
            {staffCount}
          </div>
          <div className="metric-subtext">Sales, stock &amp; customer service</div>
        </div>
      </div>

      {/* Action Bar */}
      <div className="table-controls" style={{ marginTop: "1.5rem" }}>
        <div style={{ display: "flex", gap: "0.75rem", flex: 1, alignItems: "center" }}>
          <div className="search-box" style={{ maxWidth: 360 }}>
            <Search size={16} color="var(--text-secondary)" />
            <input
              type="text"
              placeholder="Search staff by name, email, phone..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <select
            className="form-select"
            style={{ width: 180 }}
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
          >
            <option value="ALL">All Store Roles</option>
            <option value="MERCHANT_OWNER">Merchant Owner</option>
            <option value="STORE_MANAGER">Store Manager</option>
            <option value="SALES_ASSOCIATE">Sales Associate</option>
            <option value="CASHIER">Cashier</option>
            <option value="STAFF">Staff Associate</option>
          </select>
        </div>

        <button className="btn btn-primary" onClick={() => setIsModalOpen(true)}>
          <UserPlus size={16} />
          <span>Add Boutique Staff</span>
        </button>
      </div>

      {/* Staff Table */}
      <div className="table-wrapper" style={{ marginTop: "1rem" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Staff Member</th>
              <th>Contact Details</th>
              <th>Boutique Role</th>
              <th>Status</th>
              <th>Onboarded Date</th>
              <th style={{ textAlign: "right" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredStaff.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                  <Users size={32} style={{ margin: "0 auto 0.75rem", display: "block", opacity: 0.4 }} />
                  <div>No boutique personnel found matching the query.</div>
                  <div style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                    Click &quot;Add Boutique Staff&quot; above to onboard store attendants.
                  </div>
                </td>
              </tr>
            ) : (
              filteredStaff.map((staff) => (
                <tr key={staff.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: "50%",
                          background: "var(--brand-terracotta)",
                          color: "#fff",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontWeight: 700,
                          fontSize: "0.9rem",
                        }}
                      >
                        {(staff.display_name || "S").charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600 }}>{staff.display_name || "Staff Member"}</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>ID: {staff.id.slice(0, 8)}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div style={{ fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: "2px" }}>
                      {staff.email && (
                        <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                          <Mail size={12} color="var(--text-muted)" />
                          <span>{staff.email}</span>
                        </div>
                      )}
                      {staff.phone_e164 && (
                        <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                          <Phone size={12} color="var(--text-muted)" />
                          <span>{staff.phone_e164}</span>
                        </div>
                      )}
                    </div>
                  </td>
                  <td>
                    <span className="badge" style={{ textTransform: "uppercase", fontSize: "0.75rem" }}>
                      {staff.role.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td>
                    <span className={`status-pill ${staff.status === "active" ? "success" : "warning"}`}>
                      {staff.status === "active" ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                    {new Date(staff.created_at).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <div style={{ display: "inline-flex", gap: "6px" }}>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => onToggleStatus(staff.id)}
                        title={staff.status === "active" ? "Deactivate Staff" : "Activate Staff"}
                      >
                        {staff.status === "active" ? <XCircle size={14} color="#dc2626" /> : <CheckCircle size={14} color="#16a34a" />}
                        <span style={{ fontSize: "0.75rem" }}>
                          {staff.status === "active" ? "Deactivate" : "Activate"}
                        </span>
                      </button>

                      {staff.role !== "MERCHANT_OWNER" && (
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            if (window.confirm(`Are you sure you want to remove ${staff.display_name || "this staff member"}?`)) {
                              onDeleteStaff(staff.id);
                            }
                          }}
                          title="Remove Staff Member"
                          style={{ color: "#dc2626" }}
                        >
                          <Trash2 size={14} />
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

      {/* ADD STAFF MODAL */}
      {isModalOpen && (
        <div className="modal-overlay" onClick={() => setIsModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 520 }}>
            <div className="modal-header">
              <h3 className="modal-title">Add Boutique Staff Member</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setIsModalOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {errorMsg && (
                  <div className="notice warning" style={{ marginBottom: "1rem", color: "#dc2626" }}>
                    {errorMsg}
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">Full Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Ramesh Kulkarni"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    required
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Official Email Address *</label>
                    <input
                      type="email"
                      className="form-input"
                      placeholder="ramesh@bagodi.in"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Mobile Contact Number *</label>
                    <input
                      type="tel"
                      className="form-input"
                      placeholder="9880768222"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Boutique Role *</label>
                    <select
                      className="form-select"
                      value={role}
                      onChange={(e) => setRole(e.target.value)}
                      required
                    >
                      <option value="STORE_MANAGER">Store Manager (Full Store Access)</option>
                      <option value="SALES_ASSOCIATE">Sales Associate (Orders &amp; Catalog)</option>
                      <option value="CASHIER">Cashier (Till &amp; Billing)</option>
                      <option value="STAFF">General Store Staff</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Temporary Account Password *</label>
                    <input
                      type="password"
                      className="form-input"
                      placeholder="Min 6 characters"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      minLength={6}
                      required
                    />
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? "Onboarding..." : "Onboard Staff Member"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

