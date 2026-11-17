import React, { useState } from "react";
import { ShieldAlert, ArrowRight, CheckCircle2, Shield, Mail, Phone } from "lucide-react";
import { RoleType } from "../types";

interface AuthViewProps {
  onLogin: (identifier: string, otp: string, role?: RoleType) => Promise<void>;
  isLoading: boolean;
}

export const AuthView: React.FC<AuthViewProps> = ({ onLogin, isLoading }) => {
  const [authMode, setAuthMode] = useState<"email" | "phone">("email");
  const [identifier, setIdentifier] = useState("admin@techmasters.in");
  const [otp, setOtp] = useState("123456");
  const [step, setStep] = useState<"input" | "otp">("input");
  const [selectedRole, setSelectedRole] = useState<RoleType>("SUPER_ADMIN");

  const handleSendOtp = (e: React.FormEvent) => {
    e.preventDefault();
    if (!identifier.trim()) return;
    setStep("otp");
  };

  const handleVerifyOtp = (e: React.FormEvent) => {
    e.preventDefault();
    if (!otp.trim()) return;
    onLogin(identifier.trim(), otp.trim(), selectedRole);
  };

  const handleQuickRole = (role: RoleType, value: string, mode: "email" | "phone") => {
    setSelectedRole(role);
    setAuthMode(mode);
    setIdentifier(value);
    setOtp("123456");
    setStep("otp");
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="auth-logo-badge">
            <ShieldAlert size={28} />
          </div>
          <h1 className="auth-title">TechMasters Innovations</h1>
          <p className="auth-desc">Platform Governance & Super Admin Console</p>
        </div>

        {/* Dual Mode Switcher */}
        <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
          <button
            type="button"
            onClick={() => {
              setAuthMode("email");
              setIdentifier("admin@techmasters.in");
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
              setIdentifier("+919999900001");
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

        {step === "input" ? (
          <form onSubmit={handleSendOtp}>
            <div className="form-group" style={{ marginBottom: "20px" }}>
              <label className="form-label">
                {authMode === "email" ? "Authorized Platform Email" : "Authorized Mobile Number"}
              </label>
              <input
                type={authMode === "email" ? "email" : "text"}
                className="form-input"
                placeholder={authMode === "email" ? "admin@techmasters.in" : "+919999900001"}
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                required
              />
              <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                Platform credentials will be verified against governance registry
              </span>
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: "100%", padding: "12px" }}
              disabled={isLoading}
            >
              <span>Continue with Verification Code</span>
              <ArrowRight size={16} />
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerifyOtp}>
            <div className="form-group" style={{ marginBottom: "16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <label className="form-label">6-Digit OTP Code</label>
                <button
                  type="button"
                  style={{
                    background: "none",
                    border: "none",
                    color: "#FFFFFF",
                    fontSize: "0.75rem",
                    cursor: "pointer",
                    fontWeight: 600,
                  }}
                  onClick={() => setStep("input")}
                >
                  Change Credential
                </button>
              </div>
              <input
                type="text"
                className="form-input"
                placeholder="123456"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                maxLength={6}
                required
                style={{ textAlign: "center", letterSpacing: "0.2em", fontSize: "1.2rem", fontWeight: 700 }}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: "100%", padding: "12px", marginBottom: "16px" }}
              disabled={isLoading}
            >
              <CheckCircle2 size={16} />
              <span>{isLoading ? "Authenticating..." : "Authorize & Enter Console"}</span>
            </button>
          </form>
        )}

        {/* Quick Role Switcher for Test / Demo */}
        <div style={{ marginTop: "24px", paddingTop: "20px", borderTop: "1px solid var(--border-color)" }}>
          <div style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: "10px", textAlign: "center" }}>
            Quick Persona Switcher (Development Preview)
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <button
              type="button"
              className={`btn btn-secondary btn-sm ${identifier === "admin@techmasters.in" ? "active" : ""}`}
              onClick={() => handleQuickRole("SUPER_ADMIN", "admin@techmasters.in", "email")}
              style={{ justifyContent: "flex-start", gap: "8px" }}
            >
              <Shield size={14} color="var(--primary)" />
              <div style={{ textAlign: "left" }}>
                <div style={{ fontWeight: 600 }}>Super Administrator (Email)</div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>admin@techmasters.in • Unrestricted Platform Control</div>
              </div>
            </button>

            <button
              type="button"
              className={`btn btn-secondary btn-sm ${identifier === "+919999900001" ? "active" : ""}`}
              onClick={() => handleQuickRole("SUPER_ADMIN", "+919999900001", "phone")}
              style={{ justifyContent: "flex-start", gap: "8px" }}
            >
              <Shield size={14} color="var(--primary)" />
              <div style={{ textAlign: "left" }}>
                <div style={{ fontWeight: 600 }}>Super Administrator (Phone)</div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>+919999900001 • Unrestricted Platform Control</div>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
