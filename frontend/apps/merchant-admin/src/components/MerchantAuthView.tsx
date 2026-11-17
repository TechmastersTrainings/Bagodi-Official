import React, { useState } from "react";
import { Store, ShieldCheck, ArrowRight, CheckCircle2 } from "lucide-react";
import { client, setTokens, extractApiError } from "@bagodi/api-client";
import type { StaffUser } from "../types";

interface MerchantAuthViewProps {
  onSuccess: (user: StaffUser) => void;
  onNavigateHome: () => void;
}

export const MerchantAuthView: React.FC<MerchantAuthViewProps> = ({
  onSuccess,
  onNavigateHome,
}) => {
  const [activeTab, setActiveTab] = useState<"signin" | "register">("signin");

  // Sign In Form
  const [loginEmail, setLoginEmail] = useState("merchant@bagodi.in");
  const [loginPassword, setLoginPassword] = useState("Fri10Feb@2023");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  // Merchant Registration Form (Full Real Information)
  const [brandName, setBrandName] = useState("");
  const [legalName, setLegalName] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [businessType, setBusinessType] = useState("Private Limited");
  const [categorySpec, setCategorySpec] = useState("Handloom Silks & Sarees");
  const [addressLine, setAddressLine] = useState("");
  const [city, setCity] = useState("Bidar");
  const [state, setState] = useState("Karnataka");
  const [postalCode, setPostalCode] = useState("585401");
  const [gstin, setGstin] = useState("");
  const [panNumber, setPanNumber] = useState("");
  const [bankAccount, setBankAccount] = useState("");
  const [bankName, setBankName] = useState("");
  const [bankIfsc, setBankIfsc] = useState("");
  const [regLoading, setRegLoading] = useState(false);
  const [regError, setRegError] = useState<string | null>(null);
  const [regSuccessMessage, setRegSuccessMessage] = useState<string | null>(null);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    setLoginLoading(true);

    try {
      const resp = await client.POST("/api/v1/auth/login", {
        body: {
          email: loginEmail.trim(),
          password: loginPassword.trim(),
        },
      });

      if (resp.error || !resp.data) {
        const parsed = extractApiError(resp.error);
        setLoginError(parsed.message || "Invalid merchant credentials.");
        return;
      }

      setTokens(resp.data.access_token, resp.data.refresh_token);

      const staff: StaffUser = {
        id: resp.data.user.id,
        phone_e164: resp.data.user.phone_e164 || "",
        email: resp.data.user.email || undefined,
        display_name: resp.data.user.display_name || "Merchant Owner",
        role: "STORE_MANAGER",
        tenant_id: resp.data.user.tenant_id || "11111111-1111-1111-1111-111111111111",
        permissions: resp.data.user.permissions || [],
      };

      onSuccess(staff);
    } catch (err) {
      setLoginError(extractApiError(err).message);
    } finally {
      setLoginLoading(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegError(null);
    setRegLoading(true);
    setRegSuccessMessage(null);

    try {
      const resp = await client.POST("/api/v1/auth/merchant/register", {
        body: {
          brand_name: brandName.trim(),
          business_legal_name: legalName.trim(),
          owner_name: ownerName.trim(),
          email: email.trim(),
          phone_e164: phone.startsWith("+") ? phone.trim() : `+91${phone.replace(/\D/g, "")}`,
          password: password.trim(),
          business_type: businessType,
          category_specialization: categorySpec,
          address_line: addressLine.trim(),
          city: city.trim(),
          state: state.trim(),
          postal_code: postalCode.trim(),
          gstin: gstin.trim().toUpperCase() || null,
          pan_number: panNumber.trim().toUpperCase() || null,
          bank_account_number: bankAccount.trim() || null,
          bank_name: bankName.trim() || null,
          bank_ifsc: bankIfsc.trim().toUpperCase() || null,
        },
      });

      if (resp.error || !resp.data) {
        const parsed = extractApiError(resp.error);
        setRegError(parsed.message || "Registration failed.");
        return;
      }

      setRegSuccessMessage(
        resp.data.message ||
          "Merchant application submitted successfully! TechMasters Administrator approval is required before your store portal is activated."
      );
      // Switch back to sign-in tab with email prefilled
      setLoginEmail(email.trim());
      setLoginPassword("");
    } catch (err) {
      setRegError(extractApiError(err).message);
    } finally {
      setRegLoading(false);
    }
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-card" style={{ maxWidth: activeTab === "register" ? 640 : 440 }}>
        <div className="auth-logo" style={{ display: "flex", justifyContent: "center" }}>
          <div
            style={{
              background: "var(--brand-terracotta-light)",
              color: "var(--brand-terracotta)",
              width: 54,
              height: 54,
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: 12,
            }}
          >
            <Store size={28} />
          </div>
        </div>

        <h2 style={{ textAlign: "center", fontSize: "1.4rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
          Bagodi Merchant Operations
        </h2>
        <p style={{ textAlign: "center", fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: 20 }}>
          Fashion Retail Management & Live Store Catalogue Portal
        </p>

        {regSuccessMessage && (
          <div style={{ padding: "0.85rem 1rem", background: "var(--status-success-bg)", border: "1px solid var(--status-success)", borderRadius: "var(--radius-sm)", color: "var(--status-success)", fontSize: "0.85rem", marginBottom: 16, display: "flex", gap: 8, alignItems: "flex-start" }}>
            <CheckCircle2 size={18} style={{ flexShrink: 0, marginTop: 2 }} />
            <div>{regSuccessMessage}</div>
          </div>
        )}

        {/* Tab Selector */}
        <div className="auth-tab-row" style={{ marginBottom: 20 }}>
          <button
            type="button"
            className={`auth-tab-btn ${activeTab === "signin" ? "active" : ""}`}
            onClick={() => setActiveTab("signin")}
          >
            Merchant Sign In
          </button>
          <button
            type="button"
            className={`auth-tab-btn ${activeTab === "register" ? "active" : ""}`}
            onClick={() => setActiveTab("register")}
          >
            Register New Merchant
          </button>
        </div>

        {/* TAB 1: MERCHANT SIGN IN */}
        {activeTab === "signin" && (
          <form onSubmit={handleLoginSubmit}>
            {loginError && (
              <div className="auth-error-banner" style={{ marginBottom: 16 }}>
                {loginError}
              </div>
            )}

            <div className="form-group" style={{ marginBottom: 14 }}>
              <label className="form-label">Merchant Account Email</label>
              <input
                type="email"
                className="form-input"
                placeholder="merchant@bagodi.in"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                required
              />
            </div>

            <div className="form-group" style={{ marginBottom: 20 }}>
              <label className="form-label">Password</label>
              <input
                type="password"
                className="form-input"
                placeholder="••••••••"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                required
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-full"
              disabled={loginLoading}
            >
              <ShieldCheck size={16} />
              <span>{loginLoading ? "Verifying Credentials..." : "Sign In to Store Portal"}</span>
            </button>
          </form>
        )}

        {/* TAB 2: REGISTER NEW MERCHANT (FULL REAL ONBOARDING DATA) */}
        {activeTab === "register" && (
          <form onSubmit={handleRegisterSubmit}>
            {regError && (
              <div className="auth-error-banner" style={{ marginBottom: 16 }}>
                {regError}
              </div>
            )}

            <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginBottom: 16, background: "var(--bg-subtle)", padding: "8px 12px", borderRadius: 6 }}>
              ℹ️ Provide complete business, tax, and banking details. All new boutique applications require approval from TechMasters Platform Administration before activation.
            </div>

            {/* Basic Info */}
            <div className="form-row" style={{ marginBottom: 10 }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Brand / Boutique Name *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Kalyana Silks"
                  value={brandName}
                  onChange={(e) => setBrandName(e.target.value)}
                  required
                />
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Business Legal Entity Name *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Kalyana Textiles Pvt Ltd"
                  value={legalName}
                  onChange={(e) => setLegalName(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="form-row" style={{ marginBottom: 10 }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Owner / Representative Full Name *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Basavaraj Patil"
                  value={ownerName}
                  onChange={(e) => setOwnerName(e.target.value)}
                  required
                />
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Business Type</label>
                <select
                  className="form-select"
                  value={businessType}
                  onChange={(e) => setBusinessType(e.target.value)}
                >
                  <option value="Private Limited">Private Limited</option>
                  <option value="Sole Proprietorship">Sole Proprietorship</option>
                  <option value="Partnership">Partnership</option>
                  <option value="LLP">LLP</option>
                </select>
              </div>
            </div>

            <div className="form-row" style={{ marginBottom: 10 }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Official Email Address *</label>
                <input
                  type="email"
                  className="form-input"
                  placeholder="contact@brand.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Mobile Contact Number *</label>
                <input
                  type="tel"
                  className="form-input"
                  placeholder="9876543210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="form-row" style={{ marginBottom: 10 }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Account Password *</label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="Minimum 6 characters"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                />
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Fashion Specialization *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Handloom Silks, Sherwanis"
                  value={categorySpec}
                  onChange={(e) => setCategorySpec(e.target.value)}
                  required
                />
              </div>
            </div>

            {/* Address */}
            <div className="form-group" style={{ marginBottom: 10 }}>
              <label className="form-label">Physical Store / Office Address *</label>
              <input
                type="text"
                className="form-input"
                placeholder="Shop No. 4, Fort Market Road"
                value={addressLine}
                onChange={(e) => setAddressLine(e.target.value)}
                required
              />
            </div>

            <div className="form-row" style={{ marginBottom: 10 }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">City *</label>
                <input
                  type="text"
                  className="form-input"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  required
                />
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">State *</label>
                <input
                  type="text"
                  className="form-input"
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                  required
                />
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Postal PIN Code *</label>
                <input
                  type="text"
                  className="form-input"
                  value={postalCode}
                  onChange={(e) => setPostalCode(e.target.value)}
                  required
                />
              </div>
            </div>

            {/* Tax IDs */}
            <div className="form-row" style={{ marginBottom: 10 }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">GSTIN (15 Digits)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="29ABCDE1234F1Z5"
                  value={gstin}
                  onChange={(e) => setGstin(e.target.value)}
                  maxLength={15}
                />
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Business PAN Number</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="ABCDE1234F"
                  value={panNumber}
                  onChange={(e) => setPanNumber(e.target.value)}
                  maxLength={10}
                />
              </div>
            </div>

            {/* Banking Details */}
            <div className="form-row" style={{ marginBottom: 16 }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Bank Name</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="State Bank of India"
                  value={bankName}
                  onChange={(e) => setBankName(e.target.value)}
                />
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Account Number</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Account Number"
                  value={bankAccount}
                  onChange={(e) => setBankAccount(e.target.value)}
                />
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">IFSC Code</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="SBIN0001234"
                  value={bankIfsc}
                  onChange={(e) => setBankIfsc(e.target.value)}
                />
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-full"
              disabled={regLoading}
            >
              <ArrowRight size={16} />
              <span>{regLoading ? "Submitting Application..." : "Submit Application for Admin Approval"}</span>
            </button>
          </form>
        )}

        <div style={{ marginTop: 24, textAlign: "center" }}>
          <button type="button" className="btn-link" onClick={onNavigateHome}>
            ← Return to Bagodi Customer Storefront
          </button>
        </div>
      </div>
    </div>
  );
};
