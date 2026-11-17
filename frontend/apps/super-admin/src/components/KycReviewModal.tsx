import React, { useState } from "react";
import {
  X,
  FileCheck2,
  CheckCircle2,
  XCircle,
  ExternalLink,
  UploadCloud,
  AlertCircle,
} from "lucide-react";
import { TenantOverview, KYCDocument } from "../types";

interface KycReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  tenant: TenantOverview | null;
  documents: KYCDocument[];
  onReviewDocument: (
    docId: string,
    status: "VERIFIED" | "REJECTED",
    rejectionReason?: string
  ) => Promise<void>;
  onUploadDocument: (data: any) => Promise<void>;
}

export const KycReviewModal: React.FC<KycReviewModalProps> = ({
  isOpen,
  onClose,
  tenant,
  documents,
  onReviewDocument,
  onUploadDocument,
}) => {
  const [rejectingDocId, setRejectingDocId] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Upload form state
  const [docType, setDocType] = useState<
    "GST_CERTIFICATE" | "PAN_CARD" | "TRADE_LICENSE" | "BANK_STATEMENT" | "IDENTITY_PROOF"
  >("GST_CERTIFICATE");
  const [docNumber, setDocNumber] = useState("");
  const [docUrl, setDocUrl] = useState("");
  const [fileName, setFileName] = useState("");

  if (!isOpen || !tenant) return null;

  const handleVerify = async (docId: string) => {
    setIsSubmitting(true);
    try {
      await onReviewDocument(docId, "VERIFIED");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRejectSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rejectingDocId || !rejectionReason.trim()) return;

    setIsSubmitting(true);
    try {
      await onReviewDocument(rejectingDocId, "REJECTED", rejectionReason.trim());
      setRejectingDocId(null);
      setRejectionReason("");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docNumber.trim() || !docUrl.trim()) return;

    setIsSubmitting(true);
    try {
      await onUploadDocument({
        document_type: docType,
        document_number: docNumber.trim().toUpperCase(),
        document_url: docUrl.trim(),
        file_name: fileName.trim() || `${docType.toLowerCase()}_${tenant.slug}.pdf`,
        file_size_bytes: 250000,
      });
      setDocNumber("");
      setDocUrl("");
      setFileName("");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-card large">
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div className="kpi-icon-wrapper sage">
              <FileCheck2 size={18} />
            </div>
            <div>
              <h2 className="modal-title">KYC Document Compliance Review</h2>
              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                {tenant.name} ({tenant.legal_name || tenant.slug}) — GST: {tenant.gstin || "N/A"}
              </p>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          {/* Compliance Checklist Summary */}
          <div
            style={{
              padding: "14px 18px",
              backgroundColor: "var(--bg-surface-elevated)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-color)",
              marginBottom: "20px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div>
              <div style={{ fontSize: "0.85rem", fontWeight: 700 }}>
                Compliance Status:{" "}
                <span className={`status-pill ${tenant.kyc_status.toLowerCase()}`}>
                  {tenant.kyc_status.replace("_", " ")}
                </span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                Mandatory documents: GST Certificate and PAN Card must be verified before retail activation.
              </div>
            </div>
          </div>

          {/* Documents Table */}
          <h4 style={{ fontSize: "0.9rem", fontWeight: 700, marginBottom: "12px" }}>
            Submitted Verification Documents ({documents.length})
          </h4>

          {documents.length === 0 ? (
            <div
              style={{
                textAlign: "center",
                padding: "36px",
                backgroundColor: "var(--bg-surface-elevated)",
                borderRadius: "var(--radius-md)",
                border: "1px dashed var(--border-color)",
                marginBottom: "24px",
              }}
            >
              <AlertCircle size={24} color="var(--text-muted)" style={{ margin: "0 auto 8px" }} />
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                No compliance documents have been submitted yet for this merchant.
              </p>
            </div>
          ) : (
            <div className="table-container" style={{ marginBottom: "24px" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Document Type</th>
                    <th>Document Number</th>
                    <th>File</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.id}>
                      <td style={{ fontWeight: 600 }}>
                        {doc.document_type.replace(/_/g, " ")}
                      </td>
                      <td style={{ fontFamily: "monospace", fontSize: "0.82rem" }}>
                        {doc.document_number}
                      </td>
                      <td>
                        <a
                          href={doc.document_url}
                          target="_blank"
                          rel="noreferrer"
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "5px",
                            color: "var(--primary)",
                            fontSize: "0.8rem",
                            textDecoration: "none",
                            fontWeight: 500,
                          }}
                        >
                          <span>{doc.file_name}</span>
                          <ExternalLink size={12} />
                        </a>
                      </td>
                      <td>
                        <span className={`status-pill ${doc.status.toLowerCase()}`}>
                          {doc.status}
                        </span>
                        {doc.rejection_reason && (
                          <div style={{ fontSize: "0.7rem", color: "var(--status-error)", marginTop: "3px" }}>
                            Reason: {doc.rejection_reason}
                          </div>
                        )}
                      </td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          {doc.status !== "VERIFIED" && (
                            <button
                              className="btn btn-sage btn-sm"
                              onClick={() => handleVerify(doc.id)}
                              disabled={isSubmitting}
                              title="Verify & Approve this document"
                            >
                              <CheckCircle2 size={13} />
                              <span>Verify</span>
                            </button>
                          )}

                          {doc.status !== "REJECTED" && (
                            <button
                              className="btn btn-danger btn-sm"
                              onClick={() => setRejectingDocId(doc.id)}
                              disabled={isSubmitting}
                              title="Reject document with feedback"
                            >
                              <XCircle size={13} />
                              <span>Reject</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Rejection Sub-Form Modal */}
          {rejectingDocId && (
            <form
              onSubmit={handleRejectSubmit}
              style={{
                padding: "16px",
                backgroundColor: "var(--status-error-bg)",
                border: "1px solid rgba(198, 40, 40, 0.25)",
                borderRadius: "var(--radius-md)",
                marginBottom: "24px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--status-error)" }}>
                  Document Rejection Feedback
                </span>
                <button
                  type="button"
                  style={{ background: "none", border: "none", cursor: "pointer", color: "var(--status-error)" }}
                  onClick={() => setRejectingDocId(null)}
                >
                  <X size={14} />
                </button>
              </div>
              <textarea
                className="form-textarea"
                placeholder="State clear reason for rejection (e.g. illegible scan, name mismatch with PAN)..."
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                required
              />
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setRejectingDocId(null)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-danger btn-sm" disabled={isSubmitting}>
                  Confirm Rejection
                </button>
              </div>
            </form>
          )}

          {/* Upload New Document Form */}
          <div
            style={{
              padding: "18px",
              backgroundColor: "var(--bg-surface-elevated)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-color)",
            }}
          >
            <h4 style={{ fontSize: "0.88rem", fontWeight: 700, marginBottom: "14px" }}>
              Upload / Record KYC Document on Behalf of Merchant
            </h4>
            <form onSubmit={handleUploadSubmit}>
              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">Document Type *</label>
                  <select
                    className="form-select"
                    value={docType}
                    onChange={(e) => setDocType(e.target.value as any)}
                  >
                    <option value="GST_CERTIFICATE">GST Certificate</option>
                    <option value="PAN_CARD">Company / Proprietor PAN Card</option>
                    <option value="TRADE_LICENSE">Trade / Municipal License</option>
                    <option value="BANK_STATEMENT">Cancelled Cheque / Bank Statement</option>
                    <option value="IDENTITY_PROOF">Director / Proprietor ID Proof</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Document Identification Number *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. 29AAAAA1234A1Z5 or PAN"
                    value={docNumber}
                    onChange={(e) => setDocNumber(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Document URL / Storage Reference *</label>
                  <input
                    type="url"
                    className="form-input"
                    placeholder="https://storage.bagodi.in/kyc/filename.pdf"
                    value={docUrl}
                    onChange={(e) => setDocUrl(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">File Display Name</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. gst_certificate.pdf"
                    value={fileName}
                    onChange={(e) => setFileName(e.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "14px" }}>
                <button type="submit" className="btn btn-secondary btn-sm" disabled={isSubmitting}>
                  <UploadCloud size={14} />
                  <span>Upload & Register Document</span>
                </button>
              </div>
            </form>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

