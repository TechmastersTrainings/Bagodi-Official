import React, { useState } from "react";
import { ShieldCheck, Sparkles, AlertCircle, Mail, Phone } from "lucide-react";
import type { RoleType } from "../types";

interface AuthViewProps {
  onLogin: (identifier: string, otp: string, role?: RoleType) => Promise<void>;
  isLoading: boolean;
  error: string | null;
}

export const AuthView: React.FC<AuthViewProps> = ({
  onLogin,
  isLoading,
  error,
}) => {
  const [authMode, setAuthMode] = useState<"email" | "phone">("email");
  const [identifier, setIdentifier] = useState("merchant@bagodi.in");
  const [otp, setOtp] = useState("123456");
  const [selectedRole, setSelectedRole] = useState<RoleType>("STORE_MANAGER");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onLogin(identifier.trim(), otp.trim(), selectedRole);
  };

  const handleQuickSelect = (type: "email" | "phone", value: string, role: RoleType) => {
    setAuthMode(type);
    setIdentifier(value);
    setSelectedRole(role);
    setOtp("123456");
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-card">
        <div className="auth-logo">Bagodi</div>
        <div className="auth-subtitle">
          Merchant Operations & Store Management Portal
        </div>

        {error && (
          <div
            style={{
              padding: "0.75rem 1rem",
              background: "var(--status-danger-bg)",
              color: "var(--status-danger)",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.8125rem",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              marginBottom: "1.25rem",
            }}
          >
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Dual Mode Switcher: Email or Phone */}
        <div style={{ display: "flex", gap: "8px", marginBottom: "1.25rem" }}>
          <button
            type="button"
            onClick={() => {
              setAuthMode("email");
              setIdentifier("merchant@bagodi.in");
            }}
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
              padding: "8px 12px",
              fontSize: "0.8125rem",
              fontWeight: 600,
              borderRadius: "var(--radius-sm)",
              border: authMode === "email" ? "1px solid #635BFF" : "1px solid #CBD5E1",
              background: authMode === "email" ? "#635BFF" : "#FFFFFF",
              color: authMode === "email" ? "#FFFFFF" : "var(--text-secondary)",
              cursor: "pointer",
            }}
          >
            <Mail size={15} />
            <span>Email Address</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setAuthMode("phone");
              setIdentifier("+919876500002");
            }}
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
              padding: "8px 12px",
              fontSize: "0.8125rem",
              fontWeight: 600,
              borderRadius: "var(--radius-sm)",
              border: authMode === "phone" ? "1px solid #635BFF" : "1px solid #CBD5E1",
              background: authMode === "phone" ? "#635BFF" : "#FFFFFF",
              color: authMode === "phone" ? "#FFFFFF" : "var(--text-secondary)",
              cursor: "pointer",
            }}
          >
            <Phone size={15} />
            <span>Mobile Phone</span>
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group" style={{ marginBottom: "1rem" }}>
            <label className="form-label">
              {authMode === "email" ? "Merchant Staff Email Address" : "Registered Mobile Number"}
            </label>
            <input
              type={authMode === "email" ? "email" : "text"}
              className="form-input"
              placeholder={authMode === "email" ? "merchant@bagodi.in" : "+919876500002"}
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              required
            />
          </div>

          <div className="form-group" style={{ marginBottom: "1.5rem" }}>
            <label className="form-label">6-Digit Secure OTP</label>
            <input
              type="text"
              maxLength={6}
              className="form-input"
              placeholder="123456"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              required
              style={{ letterSpacing: "0.3em", fontSize: "1.1rem", fontWeight: 700, textAlign: "center" }}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: "100%", padding: "0.75rem" }}
            disabled={isLoading}
          >
            <ShieldCheck size={18} />
            <span>{isLoading ? "Authenticating Staff..." : "Sign In to Store Portal"}</span>
          </button>
        </form>

        {/* Quick Staff Profiles for Dev / Demo Evaluation */}
        <div className="role-switcher-card">
          <div className="role-switcher-title">
            <Sparkles size={13} style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} />
            Quick Test Profiles (Merchant Persona)
          </div>

          <div className="role-pills">
            <button
              type="button"
              className={`role-pill ${identifier === "merchant@bagodi.in" ? "selected" : ""}`}
              onClick={() => handleQuickSelect("email", "merchant@bagodi.in", "STORE_MANAGER")}
            >
              Merchant Email (merchant@bagodi.in)
            </button>
            <button
              type="button"
              className={`role-pill ${identifier === "+919876500002" ? "selected" : ""}`}
              onClick={() => handleQuickSelect("phone", "+919876500002", "STORE_MANAGER")}
            >
              Merchant Phone (+919876500002)
            </button>
          </div>
        </div>

        <div style={{ marginTop: "1.5rem", textAlign: "center", fontSize: "0.75rem", color: "var(--text-muted)" }}>
          Bagodi Flagship Retail Store • Bidar, Karnataka • Protected by Authoritative JWT & RBAC
        </div>
      </div>
    </div>
  );
};
