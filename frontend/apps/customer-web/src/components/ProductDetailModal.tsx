import { useState, useEffect } from "react";
import { X, Plus, Minus, ShoppingBag, Check, Tag } from "lucide-react";
import type { paths } from "@bagodi/api-client";

type ProductSummary = paths["/api/v1/catalog/products"]["get"]["responses"][200]["content"]["application/json"][number];

interface ProductDetailModalProps {
  product: ProductSummary | null;
  onClose: () => void;
  onAddToCart: (product: ProductSummary, variantId: string, quantity: number) => void;
}

export function ProductDetailModal({ product, onClose, onAddToCart }: ProductDetailModalProps) {
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [addedToast, setAddedToast] = useState(false);

  useEffect(() => {
    if (product && product.variants?.length) {
      setSelectedVariantId(product.variants[0].id);
      setQuantity(1);
      setAddedToast(false);
    }
  }, [product]);

  if (!product) return null;

  const activeVariant =
    product.variants?.find((v) => v.id === selectedVariantId) || product.variants?.[0];

  const primaryImage = product.images?.[0]?.url;
  const currentPrice = activeVariant ? parseFloat(activeVariant.base_price) : 0;
  const regularPrice = activeVariant?.mrp ? parseFloat(activeVariant.mrp) : null;
  const hasDiscount = regularPrice && regularPrice > currentPrice;

  const handleAdd = () => {
    if (activeVariant) {
      onAddToCart(product, activeVariant.id, quantity);
      setAddedToast(true);
      setTimeout(() => setAddedToast(false), 2000);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-dialog pdp-dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="modal-header">
          <div className="modal-title">Product Details</div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close product details">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <div className="pdp-grid">
            <div className="pdp-image-container">
              {primaryImage ? (
                <img
                  src={primaryImage}
                  alt={product.name}
                  className="product-image"
                />
              ) : (
                <div className="product-image-placeholder">
                  <Tag size={40} />
                  <span>Bagodi Fresh</span>
                </div>
              )}
            </div>

            <div className="pdp-details">
              <h2 className="pdp-title">{product.name}</h2>

              {product.description && (
                <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>
                  {product.description}
                </p>
              )}

              <div className="pdp-pricing-box">
                <span className="current-price" style={{ fontSize: "1.375rem" }}>
                  ₹{(currentPrice * quantity).toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}
                </span>
                {hasDiscount && (
                  <span className="regular-price" style={{ fontSize: "0.9375rem" }}>
                    ₹{(regularPrice * quantity).toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}
                  </span>
                )}
                {hasDiscount && (
                  <span className="product-badge-discount" style={{ position: "static" }}>
                    {Math.round(((regularPrice - currentPrice) / regularPrice) * 100)}% OFF
                  </span>
                )}
              </div>

              {/* Variant Selector */}
              {product.variants && product.variants.length > 1 && (
                <div>
                  <div className="pdp-variants-label" style={{ marginBottom: "8px" }}>
                    Select Size / Option:
                  </div>
                  <div className="variant-chips">
                    {product.variants.map((v) => {
                      const label = v.size || (v.attributes ? Object.values(v.attributes).join(" ") : v.name);
                      return (
                        <button
                          key={v.id}
                          type="button"
                          className={`variant-chip ${v.id === selectedVariantId ? "active" : ""}`}
                          onClick={() => setSelectedVariantId(v.id)}
                        >
                          {label} • ₹{parseFloat(v.base_price).toFixed(0)}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              <div className="pdp-meta-row">
                <span className="badge-in-stock">
                  <Check size={16} /> In Stock (Bidar)
                </span>
                {activeVariant?.sku && (
                  <span>SKU: {activeVariant.sku}</span>
                )}
                {activeVariant?.barcode && (
                  <span>Barcode: {activeVariant.barcode}</span>
                )}
              </div>

              {/* Quantity Stepper & Add to Cart */}
              <div style={{ display: "flex", alignItems: "center", gap: "14px", marginTop: "14px" }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    border: "1px solid var(--border-medium)",
                    borderRadius: "var(--radius-md)",
                    overflow: "hidden",
                  }}
                >
                  <button
                    type="button"
                    style={{ padding: "10px 14px", color: "var(--text-secondary)" }}
                    onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                    aria-label="Decrease quantity"
                  >
                    <Minus size={16} />
                  </button>
                  <span style={{ minWidth: "32px", textAlign: "center", fontWeight: 700 }}>
                    {quantity}
                  </span>
                  <button
                    type="button"
                    style={{ padding: "10px 14px", color: "var(--text-secondary)" }}
                    onClick={() => setQuantity((q) => q + 1)}
                    aria-label="Increase quantity"
                  >
                    <Plus size={16} />
                  </button>
                </div>

                <button
                  type="button"
                  className="btn-primary-action"
                  onClick={handleAdd}
                  style={{ flex: 1 }}
                >
                  {addedToast ? (
                    <>
                      <Check size={18} /> Added to Cart!
                    </>
                  ) : (
                    <>
                      <ShoppingBag size={18} /> Add {quantity} to Cart
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
