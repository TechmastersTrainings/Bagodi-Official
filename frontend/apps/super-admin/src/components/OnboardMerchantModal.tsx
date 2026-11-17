import React, { useState } from "react";
import { X, Building2, ShieldCheck } from "lucide-react";
import { SubscriptionPlan } from "../types";

interface OnboardMerchantModalProps {
  isOpen: boolean;
  onClose: () => void;
  plans: SubscriptionPlan[];
  onSubmit: (data: any) => Promise<void>;
}

export const OnboardMerchantModal: React.FC<OnboardMerchantModalProps> = ({
  isOpen,
  onClose,
  plans,
  onSubmit,
}) => {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [legalName, setLegalName] = useState("");
  const [businessType, setBusinessType] = useState("PRIVATE_LIMITED");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("+91");
  const [gstin, setGstin] = useState("");
  const [panNumber, setPanNumber] = useState("");
  const [address, setAddress] = useState("");
  const [selectedPlanCode, setSelectedPlanCode] = useState(
    plans[0]?.code || "GROWTH_RETAIL"
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleNameChange = (val: string) => {
    setName(val);
    if (!slug || slug === name.toLowerCase().replace(/[^a-z0-9]+/g, "-")) {
      setSlug(val.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !slug.trim()) return;

    setIsSubmitting(true);
    try {
      await onSubmit({
        name: name.trim(),
        slug: slug.trim().toLowerCase(),
        legal_name: legalName.trim() || undefined,
        business_type: businessType,
        contact_email: contactEmail.trim() || undefined,
        contact_phone: contactPhone.trim() || undefined,
        gstin: gstin.trim().toUpperCase() || undefined,
        pan_number: panNumber.trim().toUpperCase() || undefined,
        registered_address: address.trim() || undefined,
        initial_plan_code: selectedPlanCode,
      });
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-card large">
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div className="kpi-icon-wrapper terracotta">
              <Building2 size={18} />
            </div>
            <div>
              <h2 className="modal-title">Onboard New Merchant Organization</h2>
              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Register a new fashion retail partner on the Bagodi multi-tenant platform
              </p>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">Brand / Merchant Trade Name *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Bagodi Heritage Silks"
                  value={name}
                  onChange={(e) => handleNameChange(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Unique Tenant URL Slug *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. bagodi-heritage-silks"
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Registered Legal Entity Name</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Bagodi Handloom Private Limited"
                  value={legalName}
                  onChange={(e) => setLegalName(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Business Constitution</label>
                <select
                  className="form-select"
                  value={businessType}
                  onChange={(e) => setBusinessType(e.target.value)}
                >
                  <option value="PRIVATE_LIMITED">Private Limited Company</option>
                  <option value="PROPRIETORSHIP">Sole Proprietorship</option>
                  <option value="PARTNERSHIP">Partnership Firm</option>
                  <option value="LLP">Limited Liability Partnership (LLP)</option>
                  <option value="PUBLIC_LIMITED">Public Limited Company</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Primary Contact Email</label>
                <input
                  type="email"
                  className="form-input"
                  placeholder="management@bagodi.in"
                  value={contactEmail}
                  onChange={(e) => setContactEmail(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Primary Contact Phone</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="+919845012345"
                  value={contactPhone}
                  onChange={(e) => setContactPhone(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">GSTIN (15 Digits)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="29AAAAA0000A1Z5"
                  value={gstin}
                  onChange={(e) => setGstin(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">PAN Number (10 Digits)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="ABCDE1234F"
                  value={panNumber}
                  onChange={(e) => setPanNumber(e.target.value)}
                />
              </div>

              <div className="form-group full-width">
                <label className="form-label">Registered Office Address</label>
                <textarea
                  className="form-textarea"
                  placeholder="Door No, Street Name, City, State, PIN Code"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                />
              </div>

              <div className="form-group full-width">
                <label className="form-label">Initial Subscription Tier</label>
                <select
                  className="form-select"
                  value={selectedPlanCode}
                  onChange={(e) => setSelectedPlanCode(e.target.value)}
                >
                  {plans.map((p) => (
                    <option key={p.id} value={p.code}>
                      {p.name} — ₹{parseFloat(String(p.price)).toLocaleString("en-IN")}/mo ({p.max_stores} stores, {p.max_staff_users} staff)
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting}
            >
              <ShieldCheck size={16} />
              <span>{isSubmitting ? "Onboarding..." : "Confirm & Onboard Merchant"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

