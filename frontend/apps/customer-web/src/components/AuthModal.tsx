import { useState, useEffect, useRef, type FormEvent, type KeyboardEvent } from "react";
import { client, setTokens, setUser, clearAuth, getRefreshToken, extractApiError, type AuthUser } from "@bagodi/api-client";
import { X, CheckCircle, LogOut, ArrowRight, RefreshCw, AlertCircle } from "lucide-react";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: AuthUser | null;
  onAuthSuccess: (user: AuthUser) => void;
  onLogout: () => void;
}

export function AuthModal({ isOpen, onClose, currentUser, onAuthSuccess, onLogout }: AuthModalProps) {
  const [step, setStep] = useState<"phone" | "otp" | "profile">("phone");
  const [phone, setPhone] = useState("");
  const [otpCode, setOtpCode] = useState(["", "", "", "", "", ""]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);

  const otpInputsRef = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (currentUser) {
      setStep("profile");
    } else {
      setStep("phone");
    }
    setErrorMsg(null);
  }, [currentUser, isOpen]);

  // Countdown timer for OTP resend
  useEffect(() => {
    if (countdown <= 0) return;
    const timer = setInterval(() => {
      setCountdown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [countdown]);

  if (!isOpen) return null;

  const handlePhoneSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    const cleanPhone = phone.trim().replace(/\s+/g, "");
    if (!/^\d{10}$/.test(cleanPhone)) {
      setErrorMsg("Please enter a valid 10-digit mobile number.");
      return;
    }

    const fullPhone = `+91${cleanPhone}`;
    setLoading(true);

    try {
      const { error, response } = await client.POST("/api/v1/auth/otp/send", {
        body: { phone_e164: fullPhone, purpose: "login" },
      });

      if (error || !response.ok) {
        const parsed = extractApiError(error, response?.status);
        setErrorMsg(parsed.message);
        setLoading(false);
        return;
      }

      setCountdown(60);
      setStep("otp");
      setOtpCode(["", "", "", "", "", ""]);
      setTimeout(() => otpInputsRef.current[0]?.focus(), 100);
    } catch (err) {
      setErrorMsg(extractApiError(err).message);
    } finally {
      setLoading(false);
    }
  };

  const handleOtpChange = (index: number, value: string) => {
    if (!/^\d*$/.test(value)) return;

    const newCode = [...otpCode];
    // Handle paste of complete 6 digits
    if (value.length > 1) {
      const pasted = value.slice(0, 6).split("");
      for (let i = 0; i < 6; i++) {
        newCode[i] = pasted[i] || "";
      }
      setOtpCode(newCode);
      const nextIdx = Math.min(pasted.length, 5);
      otpInputsRef.current[nextIdx]?.focus();
      return;
    }

    newCode[index] = value;
    setOtpCode(newCode);

    if (value && index < 5) {
      otpInputsRef.current[index + 1]?.focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !otpCode[index] && index > 0) {
      otpInputsRef.current[index - 1]?.focus();
    }
  };

  const handleVerifyOtp = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    const completeOtp = otpCode.join("");
    if (completeOtp.length !== 6) {
      setErrorMsg("Please enter the complete 6-digit verification code.");
      return;
    }

    const fullPhone = `+91${phone.trim().replace(/\s+/g, "")}`;
    setLoading(true);

    try {
      const { data, error, response } = await client.POST("/api/v1/auth/otp/verify", {
        body: { phone_e164: fullPhone, otp: completeOtp },
      });

      if (error || !response.ok || !data) {
        const parsed = extractApiError(error, response?.status);
        setErrorMsg(parsed.message);
        setLoading(false);
        return;
      }

      // Store tokens
      setTokens(data.access_token, data.refresh_token);

      // Fetch user profile
      const meResp = await client.GET("/api/v1/auth/me", {});
      const userProfile: AuthUser = meResp.data
        ? {
            id: meResp.data.id,
            phone: meResp.data.phone_e164 || fullPhone,
            email: meResp.data.email,
            full_name: meResp.data.display_name,
            role: meResp.data.roles?.[0] || "CUSTOMER",
            tenant_id: meResp.data.tenant_id,
          }
        : {
            id: data.user.id,
            phone: fullPhone,
            role: "CUSTOMER",
          };

      setUser(userProfile);
      onAuthSuccess(userProfile);
      setStep("profile");
    } catch (err) {
      setErrorMsg(extractApiError(err).message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogoutClick = async () => {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        await client.POST("/api/v1/auth/logout", {
          body: { refresh_token: refreshToken },
        });
      } catch {
        // Continue with local cleanup regardless
      }
    }
    clearAuth();
    onLogout();
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            {step === "profile" ? "Your Account" : "Sign In to Bagodi"}
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close modal">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {errorMsg && (
            <div className="alert-notice error" role="alert">
              <AlertCircle size={18} />
              <span>{errorMsg}</span>
            </div>
          )}

          {step === "phone" && (
            <form onSubmit={handlePhoneSubmit}>
              <p className="description" style={{ marginBottom: "16px", color: "var(--text-secondary)", fontSize: "0.9375rem" }}>
                Enter your mobile number to receive a secure, provider-independent one-time passcode.
              </p>

              <div className="form-group">
                <label className="form-label" htmlFor="phone-input">
                  Mobile Number (India)
                </label>
                <div className="phone-input-group">
                  <span className="phone-prefix">+91</span>
                  <input
                    id="phone-input"
                    type="tel"
                    className="phone-field"
                    placeholder="98765 43210"
                    maxLength={10}
                    value={phone}
                    onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
                    autoFocus
                  />
                </div>
              </div>

              <button
                type="submit"
                className="btn-primary-action"
                disabled={loading || phone.trim().length !== 10}
              >
                {loading ? (
                  <>
                    <RefreshCw size={18} className="animate-spin" />
                    Sending Code...
                  </>
                ) : (
                  <>
                    Send Verification Code
                    <ArrowRight size={18} />
                  </>
                )}
              </button>

              <p style={{ marginTop: "14px", fontSize: "0.75rem", color: "var(--text-muted)", textAlign: "center" }}>
                By signing in, you agree to Bagodi's Terms of Service and Privacy Policy.
              </p>
            </form>
          )}

          {step === "otp" && (
            <form onSubmit={handleVerifyOtp}>
              <p className="description" style={{ marginBottom: "8px", color: "var(--text-secondary)", fontSize: "0.9375rem" }}>
                Enter the 6-digit verification code sent to <strong>+91 {phone}</strong>.
              </p>

              <button
                type="button"
                className="btn-secondary-link"
                onClick={() => setStep("phone")}
                style={{ marginBottom: "12px" }}
              >
                Change mobile number
              </button>

              <div className="otp-inputs-row">
                {otpCode.map((digit, idx) => (
                  <input
                    key={idx}
                    ref={(el) => (otpInputsRef.current[idx] = el)}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    className="otp-digit-field"
                    value={digit}
                    onChange={(e) => handleOtpChange(idx, e.target.value)}
                    onKeyDown={(e) => handleOtpKeyDown(idx, e)}
                  />
                ))}
              </div>

              <button
                type="submit"
                className="btn-primary-action"
                disabled={loading || otpCode.join("").length !== 6}
              >
                {loading ? (
                  <>
                    <RefreshCw size={18} className="animate-spin" />
                    Verifying...
                  </>
                ) : (
                  <>
                    <CheckCircle size={18} />
                    Verify & Continue
                  </>
                )}
              </button>

              <div style={{ marginTop: "16px", textAlign: "center" }}>
                {countdown > 0 ? (
                  <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                    Resend code in {countdown}s
                  </span>
                ) : (
                  <button
                    type="button"
                    className="btn-secondary-link"
                    onClick={handlePhoneSubmit}
                    disabled={loading}
                  >
                    Resend verification code
                  </button>
                )}
              </div>
            </form>
          )}

          {step === "profile" && (
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "14px", marginBottom: "20px" }}>
                <div
                  style={{
                    width: "52px",
                    height: "52px",
                    borderRadius: "var(--radius-full)",
                    background: "var(--color-botanical-subtle)",
                    color: "var(--color-botanical)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 700,
                    fontSize: "1.25rem",
                  }}
                >
                  {currentUser?.full_name ? currentUser.full_name.charAt(0).toUpperCase() : "B"}
                </div>
                <div>
                  <h3 style={{ fontSize: "1.125rem", fontWeight: 700 }}>
                    {currentUser?.full_name || "Bagodi Customer"}
                  </h3>
                  <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                    {currentUser?.phone || "+91 Mobile Customer"}
                  </p>
                </div>
              </div>

              <div
                style={{
                  background: "var(--bg-subtle)",
                  borderRadius: "var(--radius-md)",
                  padding: "14px",
                  marginBottom: "20px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px", fontSize: "0.875rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>Account Role</span>
                  <strong style={{ color: "var(--color-botanical)" }}>{currentUser?.role || "CUSTOMER"}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.875rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>Fulfillment Hub</span>
                  <strong>Bidar Main Store (Karnataka)</strong>
                </div>
              </div>

              <button
                type="button"
                className="btn-primary-action"
                onClick={handleLogoutClick}
                style={{ background: "#C03522" }}
              >
                <LogOut size={18} />
                Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
