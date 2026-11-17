import React, { useState } from "react";
import {
  Plus,
  Shield,
  UserCheck,
  X,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";
import { PlatformUser, RoleType } from "../types";

interface StaffRbacViewProps {
  staffList: PlatformUser[];
  onCreateStaff: (data: any) => Promise<void>;
  onToggleStatus: (userId: string, currentStatus: "active" | "suspended") => Promise<void>;
}

export const StaffRbacView: React.FC<StaffRbacViewProps> = ({
  staffList,
  onCreateStaff,
  onToggleStatus,
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [phone, setPhone] = useState("+91");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<RoleType>("SUPER_ADMIN");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phone.trim() || !displayName.trim()) return;

    setIsSubmitting(true);
    try {
      await onCreateStaff({
        phone_e164: phone.trim(),
        email: email.trim() || undefined,
        display_name: displayName.trim(),
        role_code: role,
      });
      setIsModalOpen(false);
      setPhone("+91");
      setEmail("");
      setDisplayName("");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div>
      <div className="toolbar-container">
        <div>
          <span style={{ fontSize: "0.95rem", fontWeight: 700 }}>
            Super Admin & Platform Governance Staff ({staffList.length})
          </span>
          <p style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
            Authorized personnel holding platform-level credentials with zero tenant identity spoofing
          </p>
        </div>

        <button className="btn btn-primary" onClick={() => setIsModalOpen(true)}>
          <Plus size={16} />
          <span>Delegate Staff Account</span>
        </button>
      </div>

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Staff Member</th>
              <th>Phone Number</th>
              <th>Email</th>
              <th>Delegated Role</th>
              <th>Status</th>
              <th>Created Date</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {staffList.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: "36px", color: "var(--text-muted)" }}>
                  No platform staff delegated yet.
                </td>
              </tr>
            ) : (
              staffList.map((s) => {
                const isActive = s.status === "active";
                return (
                  <tr key={s.id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <div className="staff-avatar">
                          {s.display_name?.charAt(0).toUpperCase() || "A"}
                        </div>
                        <span style={{ fontWeight: 600 }}>{s.display_name || "Admin"}</span>
                      </div>
                    </td>
                    <td style={{ fontFamily: "monospace" }}>{s.phone_e164 || "—"}</td>
                    <td style={{ fontSize: "0.82rem" }}>{s.email || "—"}</td>
                    <td>
                      <span className="platform-pill">
                        <Shield size={12} />
                        <span>{s.roles?.[0] || "SUPER_ADMIN"}</span>
                      </span>
                    </td>
                    <td>
                      <span className={`status-pill ${isActive ? "active" : "suspended"}`}>
                        {s.status}
                      </span>
                    </td>
                    <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      {new Date(s.created_at).toLocaleDateString("en-IN")}
                    </td>
                    <td>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => onToggleStatus(s.id, s.status)}
                      >
                        {isActive ? (
                          <>
                            <ToggleRight size={15} color="var(--status-success)" />
                            <span>Active</span>
                          </>
                        ) : (
                          <>
                            <ToggleLeft size={15} color="var(--status-error)" />
                            <span>Suspended</span>
                          </>
                        )}
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Modal: Delegate Staff Account */}
      {isModalOpen && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <div className="kpi-icon-wrapper sage">
                  <UserCheck size={18} />
                </div>
                <div>
                  <h2 className="modal-title">Delegate Platform Staff Member</h2>
                  <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    Assign platform administrative permissions with role-based access control
                  </p>
                </div>
              </div>
              <button className="modal-close-btn" onClick={() => setIsModalOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-group" style={{ marginBottom: "14px" }}>
                  <label className="form-label">Full Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Anand Kumar"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group" style={{ marginBottom: "14px" }}>
                  <label className="form-label">Mobile Number (E.164) *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="+919845011223"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group" style={{ marginBottom: "14px" }}>
                  <label className="form-label">Official Email Address</label>
                  <input
                    type="email"
                    className="form-input"
                    placeholder="anand@techmasters.in"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Delegated Administrative Role *</label>
                  <select
                    className="form-select"
                    value={role}
                    onChange={(e) => setRole(e.target.value as any)}
                  >
                    <option value="SUPER_ADMIN">Super Administrator (Full Unrestricted Access)</option>
                    <option value="COMPLIANCE_OFFICER">Compliance Officer (KYC Review & Approvals)</option>
                    <option value="FINANCE_CONTROLLER">Finance Controller (Merchant Billing & Subscriptions)</option>
                    <option value="SUPPORT_OPERATOR">Support Operator (Read-Only Diagnostics)</option>
                  </select>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                  <UserCheck size={16} />
                  <span>{isSubmitting ? "Delegating..." : "Delegate Account"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
