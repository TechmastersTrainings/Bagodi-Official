import React, { useState } from "react";
import {
  Plus,
  Receipt,
  CheckCircle2,
  X,
} from "lucide-react";
import {
  SubscriptionPlan,
  MerchantSubscription,
  MerchantInvoice,
  TenantOverview,
} from "../types";

interface BillingViewProps {
  plans: SubscriptionPlan[];
  subscriptions: MerchantSubscription[];
  invoices: MerchantInvoice[];
  tenants: TenantOverview[];
  onCreateInvoice: (data: any) => Promise<void>;
  onPayInvoice: (invoiceId: string, reference: string) => Promise<void>;
  onAssignSubscription: (tenantId: string, planId: string) => Promise<void>;
}

export const BillingView: React.FC<BillingViewProps> = ({
  plans,
  subscriptions,
  invoices,
  tenants,
  onCreateInvoice,
  onPayInvoice,
  onAssignSubscription,
}) => {
  const [activeTab, setActiveTab] = useState<"invoices" | "plans" | "subscriptions">("invoices");

  // Generate Invoice Modal
  const [isInvoiceModalOpen, setIsInvoiceModalOpen] = useState(false);
  const [selectedTenantId, setSelectedTenantId] = useState(tenants[0]?.id || "");
  const [invAmount, setInvAmount] = useState("7999.00");
  const [invTax, setInvTax] = useState("1439.82");
  const [invStartDate, setInvStartDate] = useState("2026-11-01");
  const [invEndDate, setInvEndDate] = useState("2026-11-30");
  const [invDueDate, setInvDueDate] = useState("2026-11-15");
  const [invDesc, setInvDesc] = useState("Monthly SaaS Platform Fee — Growth Retail Tier");

  // Mark Paid Modal
  const [payingInvoice, setPayingInvoice] = useState<MerchantInvoice | null>(null);
  const [paymentRef, setPaymentRef] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Assign Plan Modal
  const [isAssignModalOpen, setIsAssignModalOpen] = useState(false);
  const [assignTenantId, setAssignTenantId] = useState(tenants[0]?.id || "");
  const [assignPlanId, setAssignPlanId] = useState(plans[0]?.id || "");

  const handleCreateInvoiceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTenantId || !invAmount) return;

    setIsSubmitting(true);
    try {
      const amt = parseFloat(invAmount);
      const tax = parseFloat(invTax || "0");
      const total = amt + tax;

      await onCreateInvoice({
        tenant_id: selectedTenantId,
        billing_period_start: invStartDate,
        billing_period_end: invEndDate,
        amount: amt.toFixed(2),
        tax_amount: tax.toFixed(2),
        total_amount: total.toFixed(2),
        due_date: invDueDate,
        currency: "INR",
        line_items: [
          { description: invDesc, amount: amt.toFixed(2) },
          { description: "GST @ 18% (CGST + SGST)", amount: tax.toFixed(2) },
        ],
      });
      setIsInvoiceModalOpen(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePayInvoiceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!payingInvoice || !paymentRef.trim()) return;

    setIsSubmitting(true);
    try {
      await onPayInvoice(payingInvoice.id, paymentRef.trim());
      setPayingInvoice(null);
      setPaymentRef("");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAssignPlanSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignTenantId || !assignPlanId) return;

    setIsSubmitting(true);
    try {
      await onAssignSubscription(assignTenantId, assignPlanId);
      setIsAssignModalOpen(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div>
      {/* Sub-navigation tabs */}
      <div className="toolbar-container">
        <div className="filter-group">
          <button
            className={`filter-tab ${activeTab === "invoices" ? "active" : ""}`}
            onClick={() => setActiveTab("invoices")}
          >
            Billing Invoices ({invoices.length})
          </button>
          <button
            className={`filter-tab ${activeTab === "plans" ? "active" : ""}`}
            onClick={() => setActiveTab("plans")}
          >
            Subscription Plans ({plans.length})
          </button>
          <button
            className={`filter-tab ${activeTab === "subscriptions" ? "active" : ""}`}
            onClick={() => setActiveTab("subscriptions")}
          >
            Merchant Subscriptions ({subscriptions.length})
          </button>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          {activeTab === "invoices" && (
            <button
              className="btn btn-primary"
              onClick={() => setIsInvoiceModalOpen(true)}
            >
              <Plus size={16} />
              <span>Generate Invoice</span>
            </button>
          )}

          {activeTab === "subscriptions" && (
            <button
              className="btn btn-primary"
              onClick={() => setIsAssignModalOpen(true)}
            >
              <Plus size={16} />
              <span>Assign / Upgrade Plan</span>
            </button>
          )}
        </div>
      </div>

      {/* 1. INVOICES VIEW */}
      {activeTab === "invoices" && (
        <div className="table-container">
          <div className="table-header-bar">
            <span className="table-header-title">Merchant Subscription Invoices</span>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Invoice Number</th>
                <th>Merchant</th>
                <th>Billing Period</th>
                <th>Amount (INR)</th>
                <th>Status</th>
                <th>Due Date</th>
                <th>Payment Ref</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {invoices.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: "center", padding: "36px", color: "var(--text-muted)" }}>
                    No subscription invoices generated yet.
                  </td>
                </tr>
              ) : (
                invoices.map((inv) => {
                  const tenantName =
                    tenants.find((t) => t.id === inv.tenant_id)?.name || "Merchant";
                  const isPaid = inv.status === "PAID";
                  const total = parseFloat(String(inv.total_amount));

                  return (
                    <tr key={inv.id}>
                      <td style={{ fontFamily: "monospace", fontWeight: 700 }}>
                        {inv.invoice_number}
                      </td>
                      <td style={{ fontWeight: 600 }}>{tenantName}</td>
                      <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                        {inv.billing_period_start} to {inv.billing_period_end}
                      </td>
                      <td className="tabular-nums" style={{ fontWeight: 700 }}>
                        ₹{total.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </td>
                      <td>
                        <span className={`status-pill ${inv.status.toLowerCase()}`}>
                          {inv.status}
                        </span>
                      </td>
                      <td style={{ fontSize: "0.8rem" }}>{inv.due_date}</td>
                      <td style={{ fontSize: "0.78rem", fontFamily: "monospace" }}>
                        {inv.payment_reference || "—"}
                      </td>
                      <td>
                        {!isPaid ? (
                          <button
                            className="btn btn-sage btn-sm"
                            onClick={() => {
                              setPayingInvoice(inv);
                              setPaymentRef(`HDFC-NEFT-${Math.floor(100000 + Math.random() * 900000)}`);
                            }}
                            title="Record payment settlement"
                          >
                            <CheckCircle2 size={13} />
                            <span>Mark Paid</span>
                          </button>
                        ) : (
                          <span style={{ fontSize: "0.75rem", color: "var(--status-success)", fontWeight: 600 }}>
                            Settled
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* 2. PLANS VIEW */}
      {activeTab === "plans" && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: "20px",
            marginBottom: "28px",
          }}
        >
          {plans.map((p) => {
            const price = parseFloat(String(p.price));
            const comm = parseFloat(String(p.commission_rate_percent));

            return (
              <div
                key={p.id}
                style={{
                  backgroundColor: "var(--bg-surface)",
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--border-color)",
                  padding: "24px",
                  display: "flex",
                  flexDirection: "column",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "14px" }}>
                  <div>
                    <h3 style={{ fontSize: "1.1rem", fontWeight: 700 }}>{p.name}</h3>
                    <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontFamily: "monospace" }}>
                      CODE: {p.code}
                    </span>
                  </div>
                  <span className="status-pill active">{p.billing_cycle}</span>
                </div>

                <div style={{ marginBottom: "16px" }}>
                  <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--primary)" }} className="tabular-nums">
                    ₹{price.toLocaleString("en-IN")}
                    <span style={{ fontSize: "0.85rem", fontWeight: 500, color: "var(--text-muted)" }}>
                      /month
                    </span>
                  </div>
                  <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "6px" }}>
                    {p.description}
                  </p>
                </div>

                <div
                  style={{
                    backgroundColor: "var(--bg-surface-elevated)",
                    borderRadius: "var(--radius-md)",
                    padding: "12px",
                    marginBottom: "16px",
                    display: "grid",
                    gridTemplateColumns: "repeat(3, 1fr)",
                    gap: "8px",
                    textAlign: "center",
                  }}
                >
                  <div>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Stores</div>
                    <div style={{ fontSize: "1rem", fontWeight: 700 }} className="tabular-nums">{p.max_stores}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Staff</div>
                    <div style={{ fontSize: "1rem", fontWeight: 700 }} className="tabular-nums">{p.max_staff_users}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Fee</div>
                    <div style={{ fontSize: "1rem", fontWeight: 700 }} className="tabular-nums">{comm}%</div>
                  </div>
                </div>

                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: "8px" }}>
                    Included Capabilities
                  </div>
                  <ul style={{ listStyle: "none", fontSize: "0.82rem", display: "flex", flexDirection: "column", gap: "6px" }}>
                    {p.features?.map((feat, idx) => (
                      <li key={idx} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <CheckCircle2 size={13} color="var(--sage)" />
                        <span>{feat}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 3. SUBSCRIPTIONS VIEW */}
      {activeTab === "subscriptions" && (
        <div className="table-container">
          <div className="table-header-bar">
            <span className="table-header-title">Active Merchant Subscriptions</span>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Merchant</th>
                <th>Assigned Plan</th>
                <th>Status</th>
                <th>Period Start</th>
                <th>Renewal Date</th>
                <th>Auto Renew</th>
              </tr>
            </thead>
            <tbody>
              {subscriptions.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "36px", color: "var(--text-muted)" }}>
                    No active subscriptions assigned yet.
                  </td>
                </tr>
              ) : (
                subscriptions.map((sub) => {
                  const tenantName =
                    tenants.find((t) => t.id === sub.tenant_id)?.name || "Merchant";
                  return (
                    <tr key={sub.id}>
                      <td style={{ fontWeight: 600 }}>{tenantName}</td>
                      <td>
                        <span style={{ fontWeight: 700, color: "var(--primary)" }}>
                          {sub.plan?.name || "Standard Retail"}
                        </span>
                      </td>
                      <td>
                        <span className={`status-pill ${sub.status.toLowerCase()}`}>
                          {sub.status}
                        </span>
                      </td>
                      <td style={{ fontSize: "0.82rem" }}>
                        {new Date(sub.current_period_start).toLocaleDateString("en-IN")}
                      </td>
                      <td style={{ fontSize: "0.82rem" }}>
                        {new Date(sub.current_period_end).toLocaleDateString("en-IN")}
                      </td>
                      <td>
                        <span style={{ fontSize: "0.8rem", color: sub.auto_renew ? "var(--status-success)" : "var(--text-muted)", fontWeight: 600 }}>
                          {sub.auto_renew ? "Enabled" : "Disabled"}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal: Generate Invoice */}
      {isInvoiceModalOpen && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <h2 className="modal-title">Generate Merchant Subscription Invoice</h2>
              <button className="modal-close-btn" onClick={() => setIsInvoiceModalOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleCreateInvoiceSubmit}>
              <div className="modal-body">
                <div className="form-grid">
                  <div className="form-group full-width">
                    <label className="form-label">Merchant Organization *</label>
                    <select
                      className="form-select"
                      value={selectedTenantId}
                      onChange={(e) => setSelectedTenantId(e.target.value)}
                      required
                    >
                      {tenants.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name} ({t.legal_name || t.slug})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Base Amount (₹) *</label>
                    <input
                      type="number"
                      step="0.01"
                      className="form-input"
                      value={invAmount}
                      onChange={(e) => {
                        setInvAmount(e.target.value);
                        const v = parseFloat(e.target.value || "0");
                        setInvTax((v * 0.18).toFixed(2));
                      }}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">GST 18% (₹)</label>
                    <input
                      type="number"
                      step="0.01"
                      className="form-input"
                      value={invTax}
                      onChange={(e) => setInvTax(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Billing Period Start *</label>
                    <input
                      type="date"
                      className="form-input"
                      value={invStartDate}
                      onChange={(e) => setInvStartDate(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Billing Period End *</label>
                    <input
                      type="date"
                      className="form-input"
                      value={invEndDate}
                      onChange={(e) => setInvEndDate(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group full-width">
                    <label className="form-label">Due Date *</label>
                    <input
                      type="date"
                      className="form-input"
                      value={invDueDate}
                      onChange={(e) => setInvDueDate(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group full-width">
                    <label className="form-label">Line Item Description</label>
                    <input
                      type="text"
                      className="form-input"
                      value={invDesc}
                      onChange={(e) => setInvDesc(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsInvoiceModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                  <Receipt size={16} />
                  <span>{isSubmitting ? "Generating..." : "Generate Invoice"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Mark Paid */}
      {payingInvoice && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <h2 className="modal-title">Record Invoice Payment Settlement</h2>
              <button className="modal-close-btn" onClick={() => setPayingInvoice(null)}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handlePayInvoiceSubmit}>
              <div className="modal-body">
                <p style={{ fontSize: "0.85rem", marginBottom: "14px", color: "var(--text-secondary)" }}>
                  Invoice: <strong>{payingInvoice.invoice_number}</strong> — Total: <strong>₹{parseFloat(String(payingInvoice.total_amount)).toLocaleString("en-IN")}</strong>
                </p>

                <div className="form-group">
                  <label className="form-label">Bank Settlement / NEFT / UTR Reference *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. HDFC-NEFT-20261110-12345"
                    value={paymentRef}
                    onChange={(e) => setPaymentRef(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setPayingInvoice(null)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-sage" disabled={isSubmitting}>
                  <CheckCircle2 size={16} />
                  <span>{isSubmitting ? "Settling..." : "Confirm Payment Settlement"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Assign Plan */}
      {isAssignModalOpen && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <h2 className="modal-title">Assign or Upgrade Merchant Plan</h2>
              <button className="modal-close-btn" onClick={() => setIsAssignModalOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleAssignPlanSubmit}>
              <div className="modal-body">
                <div className="form-group" style={{ marginBottom: "16px" }}>
                  <label className="form-label">Select Merchant Organization *</label>
                  <select
                    className="form-select"
                    value={assignTenantId}
                    onChange={(e) => setAssignTenantId(e.target.value)}
                  >
                    {tenants.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} (Current: {t.current_plan_name || "None"})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Target Subscription Tier *</label>
                  <select
                    className="form-select"
                    value={assignPlanId}
                    onChange={(e) => setAssignPlanId(e.target.value)}
                  >
                    {plans.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} — ₹{parseFloat(String(p.price)).toLocaleString("en-IN")}/month
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsAssignModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                  <span>{isSubmitting ? "Assigning..." : "Assign Subscription"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
