import React, { useState } from "react";
import { Barcode, RefreshCw, X, Loader2 } from "lucide-react";
import { client } from "@bagodi/api-client";

interface TopHeaderProps {
  title: string;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const TopHeader: React.FC<TopHeaderProps> = ({
  title,
  onRefresh,
  isRefreshing,
}) => {
  const [barcodeInput, setBarcodeInput] = useState("");
  const [lookupResult, setLookupResult] = useState<any | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);

  const handleBarcodeLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!barcodeInput.trim()) return;

    setIsSearching(true);
    setLookupError(null);
    try {
      const { data, error, response } = await client.GET(
        "/api/v1/barcodes/{barcode}",
        {
          params: {
            path: { barcode: barcodeInput.trim() },
          },
        }
      );

      if (error || !response.ok) {
        setLookupError("Barcode not found in active inventory.");
        setLookupResult(null);
      } else {
        setLookupResult(data);
      }
    } catch {
      setLookupError("Error querying barcode database.");
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <header className="top-bar">
      <h1 className="page-title">{title}</h1>

      <div className="top-actions">
        {/* Quick Barcode & SKU Lookup */}
        <form onSubmit={handleBarcodeLookup} className="search-box">
          {isSearching ? (
            <Loader2 size={18} className="spin" color="var(--brand-terracotta)" />
          ) : (
            <Barcode size={18} color="var(--text-secondary)" />
          )}
          <input
            type="text"
            placeholder="Scan Barcode / Enter SKU..."
            value={barcodeInput}
            onChange={(e) => setBarcodeInput(e.target.value)}
          />
          {barcodeInput && (
            <button
              type="button"
              onClick={() => {
                setBarcodeInput("");
                setLookupResult(null);
                setLookupError(null);
              }}
              style={{ background: "none", border: "none", cursor: "pointer", display: "flex" }}
            >
              <X size={14} color="var(--text-muted)" />
            </button>
          )}
        </form>

        {onRefresh && (
          <button
            className="btn btn-secondary btn-sm"
            onClick={onRefresh}
            disabled={isRefreshing}
            title="Refresh View"
          >
            <RefreshCw size={15} className={isRefreshing ? "spin" : ""} />
            <span>Sync</span>
          </button>
        )}
      </div>

      {/* Barcode Quick Inspection Modal */}
      {(lookupResult || lookupError) && (
        <div className="modal-overlay" onClick={() => { setLookupResult(null); setLookupError(null); }}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Barcode size={20} color="var(--brand-terracotta)" />
                <h3 className="modal-title">Barcode Scan Result</h3>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => { setLookupResult(null); setLookupError(null); }}
              >
                <X size={16} />
              </button>
            </div>

            <div className="modal-body">
              {lookupError ? (
                <div style={{ padding: "1rem", background: "var(--status-danger-bg)", color: "var(--status-danger)", borderRadius: "var(--radius-sm)" }}>
                  {lookupError}
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-primary)" }}>
                    {lookupResult.product_name || "Bagodi Apparel Item"}
                  </div>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    <span className="variant-tag">Size: {lookupResult.size || "Standard"}</span>
                    <span className="variant-tag">Color: {lookupResult.color || "Standard"}</span>
                    <span className="variant-tag">SKU: {lookupResult.sku}</span>
                    <span className="variant-tag">Barcode: {lookupResult.barcode}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: "0.5rem", padding: "0.75rem", background: "var(--bg-subtle)", borderRadius: "var(--radius-sm)" }}>
                    <div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>SELLING PRICE</div>
                      <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--brand-terracotta)" }}>
                        ₹{parseFloat(lookupResult.base_price || "0").toLocaleString("en-IN")}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>MRP</div>
                      <div style={{ fontSize: "1rem", color: "var(--text-secondary)", textDecoration: "line-through" }}>
                        ₹{parseFloat(lookupResult.mrp || "0").toLocaleString("en-IN")}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => { setLookupResult(null); setLookupError(null); }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
