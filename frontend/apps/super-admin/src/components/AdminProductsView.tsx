import React, { useState } from "react";
import {
  Shirt,
  Plus,
  Search,
  Tag,
  Trash2,
  Edit3,
  Eye,
  EyeOff,
  Image as ImageIcon,
  Layers,
  ArrowLeft,
  Sparkles,
  Save,
  Package,
  AlertCircle,
} from "lucide-react";
import type { AdminProduct } from "../types";

interface Category {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  is_active: boolean;
}

interface Brand {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  is_active: boolean;
}

interface AdminProductsViewProps {
  products: AdminProduct[];
  categories: Category[];
  brands: Brand[];
  onCreateProduct: (data: any) => Promise<void>;
  onUpdateProduct: (productId: string, data: any) => Promise<void>;
  onDeleteProduct: (productId: string) => Promise<void>;
}

interface SizeOption {
  size: "S" | "M" | "L" | "XL" | "XXL" | "Free Size";
  enabled: boolean;
  stock: number;
  price: string;
  mrp: string;
}

interface StudioImage {
  url: string;
  alt_text: string;
  is_primary: boolean;
}

export const AdminProductsView: React.FC<AdminProductsViewProps> = ({
  products,
  categories,
  brands,
  onCreateProduct,
  onUpdateProduct,
  onDeleteProduct,
}) => {
  const [activeTab, setActiveTab] = useState<"products" | "categories" | "brands">("products");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("ALL");
  const [selectedBrand, setSelectedBrand] = useState("ALL");

  // Full-Page Studio View States
  const [isStudioOpen, setIsStudioOpen] = useState(() => {
    return new URLSearchParams(window.location.search).get("studio") === "true";
  });
  const [editingProduct, setEditingProduct] = useState<AdminProduct | null>(null);

  // Form State (Clean Initial Defaults - Zero Dummy Values)
  const [name, setName] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [brandId, setBrandId] = useState("");
  const [description, setDescription] = useState("");
  const [basePrice, setBasePrice] = useState("");
  const [mrp, setMrp] = useState("");
  const [isPublished, setIsPublished] = useState(true);

  // Size Options
  const DEFAULT_SIZES: SizeOption[] = [
    { size: "S", enabled: false, stock: 0, price: "", mrp: "" },
    { size: "M", enabled: false, stock: 0, price: "", mrp: "" },
    { size: "L", enabled: false, stock: 0, price: "", mrp: "" },
    { size: "XL", enabled: false, stock: 0, price: "", mrp: "" },
    { size: "XXL", enabled: false, stock: 0, price: "", mrp: "" },
    { size: "Free Size", enabled: false, stock: 0, price: "", mrp: "" },
  ];
  const [sizeOptions, setSizeOptions] = useState<SizeOption[]>(DEFAULT_SIZES);

  // Studio Photography
  const [studioImages, setStudioImages] = useState<StudioImage[]>([]);
  const [newImageUrl, setNewImageUrl] = useState("");
  const [newImageAlt, setNewImageAlt] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Edit form states
  const [editName, setEditName] = useState("");
  const [editCategoryId, setEditCategoryId] = useState("");
  const [editBrandId, setEditBrandId] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editPublished, setEditPublished] = useState(true);

  // Calculations for studio preview
  const basePriceNum = parseFloat(basePrice) || 0;
  const mrpNum = parseFloat(mrp) || 0;
  const discountPct =
    mrpNum > basePriceNum && mrpNum > 0
      ? Math.round(((mrpNum - basePriceNum) / mrpNum) * 100)
      : 0;

  const selectedCategoryObj = categories.find((c) => c.id === categoryId);
  const selectedBrandObj = brands.find((b) => b.id === brandId);
  const primaryStudioImage = studioImages.find((img) => img.is_primary) || studioImages[0];
  const totalStockUnits = sizeOptions
    .filter((s) => s.enabled)
    .reduce((acc, s) => acc + (s.stock || 0), 0);

  const filteredProducts = products.filter((p) => {
    const matchesSearch =
      !searchQuery ||
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.slug.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCat = selectedCategory === "ALL" || p.category_id === selectedCategory;
    const matchesBrand = selectedBrand === "ALL" || p.brand_id === selectedBrand;
    return matchesSearch && matchesCat && matchesBrand;
  });

  const handleToggleAllSizes = (enable: boolean) => {
    setSizeOptions((prev) =>
      prev.map((s) => ({
        ...s,
        enabled: enable,
        price: enable ? (s.price || basePrice) : "",
        mrp: enable ? (s.mrp || mrp) : "",
      }))
    );
  };

  const handleAddStudioImage = (url: string, altText?: string) => {
    if (!url.trim()) return;
    const isPrimary = studioImages.length === 0;
    setStudioImages((prev) => [
      ...prev,
      {
        url: url.trim(),
        alt_text: altText || name.trim() || "Garment Photo",
        is_primary: isPrimary,
      },
    ]);
    setNewImageUrl("");
    setNewImageAlt("");
  };

  const handleSetPrimaryImage = (index: number) => {
    setStudioImages((prev) =>
      prev.map((img, idx) => ({
        ...img,
        is_primary: idx === index,
      }))
    );
  };

  const handleRemoveStudioImage = (index: number) => {
    setStudioImages((prev) => {
      const filtered = prev.filter((_, idx) => idx !== index);
      if (filtered.length > 0 && !filtered.some((img) => img.is_primary)) {
        filtered[0].is_primary = true;
      }
      return filtered;
    });
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!name.trim()) {
      setErrorMsg("Please enter a garment title.");
      return;
    }
    if (!categoryId) {
      setErrorMsg("Please select an apparel category.");
      return;
    }

    const activeSizes = sizeOptions.filter((s) => s.enabled);
    if (activeSizes.length === 0) {
      setErrorMsg("Please enable at least one clothing size (S, M, L, XL, XXL, or Free Size) with available stock.");
      return;
    }

    setSubmitting(true);
    try {
      const payload: any = {
        name: name.trim(),
        category_id: categoryId,
        brand_id: brandId || null,
        description: description.trim() || null,
        status: "active",
        is_published: isPublished,
        variants: activeSizes.map((s) => ({
          name: `${name.trim()} - Size ${s.size}`,
          size: s.size,
          base_price: parseFloat(s.price || basePrice) || 0,
          mrp: parseFloat(s.mrp || mrp) || 0,
          initial_stock: s.stock || 0,
          status: "active",
        })),
        images: studioImages.map((img, idx) => ({
          url: img.url,
          alt_text: img.alt_text || name.trim(),
          is_primary: img.is_primary,
          sort_order: idx,
        })),
      };

      await onCreateProduct(payload);
      setIsStudioOpen(false);
      setName("");
      setDescription("");
      setBasePrice("");
      setMrp("");
      setStudioImages([]);
      setSizeOptions(DEFAULT_SIZES);
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to create garment.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleStartEdit = (p: AdminProduct) => {
    setEditingProduct(p);
    setEditName(p.name);
    setEditCategoryId(p.category_id || "");
    setEditBrandId(p.brand_id || "");
    setEditDesc(p.description || "");
    setEditPublished(p.is_published);
  };

  const handleUpdateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingProduct) return;
    setSubmitting(true);
    try {
      await onUpdateProduct(editingProduct.id, {
        name: editName.trim(),
        category_id: editCategoryId || null,
        brand_id: editBrandId || null,
        description: editDesc.trim() || null,
        is_published: editPublished,
      });
      setEditingProduct(null);
    } catch (err: any) {
      alert(err?.message || "Failed to update product.");
    } finally {
      setSubmitting(false);
    }
  };

  // =========================================================================
  // VIEW 1: FULL-PAGE PRODUCT CREATION STUDIO
  // =========================================================================
  if (isStudioOpen) {
    return (
      <div className="product-studio-page">
        <div className="studio-header">
          <div>
            <button
              type="button"
              className="studio-back-btn"
              onClick={() => setIsStudioOpen(false)}
            >
              <ArrowLeft size={16} />
              <span>Back to Fashion Catalogue</span>
            </button>
            <div className="studio-title-area">
              <h2>New Apparel Garment Studio</h2>
              <p>
                Publish handcrafted luxury couture, heritage silks, and modern silhouettes with individual size inventory and live storefront card preview.
              </p>
            </div>
          </div>

          <div className="studio-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setIsStudioOpen(false)}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleCreateSubmit}
              disabled={submitting}
            >
              <Save size={16} />
              <span>{submitting ? "Publishing Garment..." : "Publish Apparel to Storefront"}</span>
            </button>
          </div>
        </div>

        {errorMsg && (
          <div className="studio-alert-error">
            <AlertCircle size={18} />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleCreateSubmit}>
          <div className="studio-layout">
            {/* Left Column: Garment Specifications & Assets */}
            <div className="studio-main-col">
              {/* Card 1: Identity & Valuation */}
              <div className="studio-card">
                <div className="studio-card-header">
                  <div>
                    <div className="studio-card-title">
                      <Shirt size={16} />
                      <span>1. Garment Identity &amp; Valuation</span>
                    </div>
                    <div className="studio-card-subtitle">
                      Product title, category classification, brand pedigree, and pricing structure
                    </div>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Garment Title *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Raymond Tailored Italian Wool Formal Blazer"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                  />
                </div>

                <div className="form-row" style={{ marginTop: "1rem" }}>
                  <div className="form-group">
                    <label className="form-label">Apparel Category *</label>
                    <select
                      className="form-select"
                      value={categoryId}
                      onChange={(e) => setCategoryId(e.target.value)}
                      required
                    >
                      <option value="">Select Category...</option>
                      {categories.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Label / Brand Pedigree</label>
                    <select
                      className="form-select"
                      value={brandId}
                      onChange={(e) => setBrandId(e.target.value)}
                    >
                      <option value="">Select Brand (Optional)...</option>
                      {brands.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="form-row" style={{ marginTop: "1rem" }}>
                  <div className="form-group">
                    <label className="form-label">Garment Base Selling Price (₹) *</label>
                    <input
                      type="number"
                      step="0.01"
                      className="form-input"
                      placeholder="e.g. 4999.00"
                      value={basePrice}
                      onChange={(e) => {
                        const val = e.target.value;
                        setBasePrice(val);
                        setSizeOptions((prev) => prev.map((s) => ({ ...s, price: val })));
                      }}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                      <label className="form-label">Garment MRP (₹) *</label>
                      {discountPct > 0 && (
                        <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--flame)" }}>
                          {discountPct}% Storefront Discount
                        </span>
                      )}
                    </div>
                    <input
                      type="number"
                      step="0.01"
                      className="form-input"
                      placeholder="e.g. 6499.00"
                      value={mrp}
                      onChange={(e) => {
                        const val = e.target.value;
                        setMrp(val);
                        setSizeOptions((prev) => prev.map((s) => ({ ...s, mrp: val })));
                      }}
                      required
                    />
                  </div>
                </div>

                <div
                  style={{
                    marginTop: "1rem",
                    padding: "0.65rem 0.9rem",
                    background: "rgba(255, 255, 255, 0.04)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "var(--radius-sm)",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    fontSize: "0.8rem",
                    color: "#FFFFFF",
                  }}
                >
                  <Sparkles size={15} color="#FFFFFF" />
                  <span>
                    <strong>Automatic SKU &amp; Slug Architecture:</strong> SKUs and clean URLs are generated automatically by the platform backend.
                  </span>
                </div>
              </div>

              {/* Card 2: Sizing & Individual Stock Matrix */}
              <div className="studio-card">
                <div className="studio-card-header">
                  <div>
                    <div className="studio-card-title">
                      <Layers size={16} />
                      <span>2. Clothing Sizing Matrix &amp; Individual Stock</span>
                    </div>
                    <div className="studio-card-subtitle">
                      Control inventory per size (S, M, L, XL, XXL, Free Size). Dedicated atomic stock deduction on purchases.
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: "0.8rem",
                      fontWeight: 700,
                      color: "#059669",
                      background: "#ECFDF5",
                      padding: "4px 12px",
                      borderRadius: "var(--radius-full)",
                      border: "1px solid #A7F3D0",
                    }}
                  >
                    Total Available Units: {totalStockUnits}
                  </span>
                </div>

                {/* Sizing Controls */}
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap", marginBottom: "1rem" }}>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600 }}>Quick Selection:</span>
                  <button
                    type="button"
                    className="studio-preset-btn"
                    onClick={() => handleToggleAllSizes(true)}
                  >
                    Select All Sizes
                  </button>
                  <button
                    type="button"
                    className="studio-preset-btn"
                    onClick={() => handleToggleAllSizes(false)}
                  >
                    Clear All Sizes
                  </button>
                </div>

                {/* Sizing Table */}
                <div style={{ border: "1px solid var(--border-medium)", borderRadius: "var(--radius-sm)", overflow: "hidden", background: "var(--bg-surface)" }}>
                  <table className="data-table" style={{ margin: 0, fontSize: "0.85rem" }}>
                    <thead>
                      <tr>
                        <th style={{ width: 60, textAlign: "center" }}>Active</th>
                        <th style={{ width: 100 }}>Size</th>
                        <th>Available Stock</th>
                        <th>Selling Price (₹)</th>
                        <th>MRP (₹)</th>
                        <th>Inventory Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sizeOptions.map((opt, idx) => (
                        <tr key={opt.size} style={{ opacity: opt.enabled ? 1 : 0.45 }}>
                          <td style={{ textAlign: "center" }}>
                            <input
                              type="checkbox"
                              checked={opt.enabled}
                              onChange={(e) => {
                                const updated = [...sizeOptions];
                                updated[idx] = { ...updated[idx], enabled: e.target.checked };
                                setSizeOptions(updated);
                              }}
                            />
                          </td>
                          <td style={{ fontWeight: 700, color: "var(--flame)" }}>{opt.size}</td>
                          <td>
                            <input
                              type="number"
                              min="0"
                              disabled={!opt.enabled}
                              className="form-input"
                              style={{ width: 95, padding: "4px 8px" }}
                              value={opt.stock}
                              onChange={(e) => {
                                const updated = [...sizeOptions];
                                updated[idx] = {
                                  ...updated[idx],
                                  stock: Math.max(0, parseInt(e.target.value) || 0),
                                };
                                setSizeOptions(updated);
                              }}
                            />
                          </td>
                          <td>
                            <input
                              type="number"
                              step="0.01"
                              disabled={!opt.enabled}
                              className="form-input"
                              style={{ width: 115, padding: "4px 8px" }}
                              value={opt.price}
                              onChange={(e) => {
                                const updated = [...sizeOptions];
                                updated[idx] = { ...updated[idx], price: e.target.value };
                                setSizeOptions(updated);
                              }}
                            />
                          </td>
                          <td>
                            <input
                              type="number"
                              step="0.01"
                              disabled={!opt.enabled}
                              className="form-input"
                              style={{ width: 115, padding: "4px 8px" }}
                              value={opt.mrp}
                              onChange={(e) => {
                                const updated = [...sizeOptions];
                                updated[idx] = { ...updated[idx], mrp: e.target.value };
                                setSizeOptions(updated);
                              }}
                            />
                          </td>
                          <td>
                            {opt.enabled && opt.stock > 0 ? (
                              <span className="status-pill success" style={{ fontSize: "0.72rem" }}>
                                In Stock ({opt.stock})
                              </span>
                            ) : opt.enabled ? (
                              <span className="status-pill danger" style={{ fontSize: "0.72rem" }}>
                                Out of Stock (0)
                              </span>
                            ) : (
                              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Disabled</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Card 3: High-Res Photography & Lookbook */}
              <div className="studio-card">
                <div className="studio-card-header">
                  <div>
                    <div className="studio-card-title">
                      <ImageIcon size={16} />
                      <span>3. Garment Photography &amp; Lookbook</span>
                    </div>
                    <div className="studio-card-subtitle">
                      Curate high-resolution imagery for the customer storefront product detail gallery
                    </div>
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "var(--flame)", fontWeight: 600 }}>
                    {studioImages.length} Photo{studioImages.length === 1 ? "" : "s"} Attached
                  </span>
                </div>

                {/* Custom Photo URL Input */}
                <div className="form-row">
                  <div className="form-group" style={{ flex: 3 }}>
                    <label className="form-label">Custom Image URL (Unsplash or CDN link)</label>
                    <input
                      type="url"
                      className="form-input"
                      placeholder="https://images.unsplash.com/photo-..."
                      value={newImageUrl}
                      onChange={(e) => setNewImageUrl(e.target.value)}
                    />
                  </div>
                  <div className="form-group" style={{ flex: 2 }}>
                    <label className="form-label">Alt / View Description</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. Front look in studio lighting"
                      value={newImageAlt}
                      onChange={(e) => setNewImageAlt(e.target.value)}
                    />
                  </div>
                  <div style={{ alignSelf: "flex-end" }}>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleAddStudioImage(newImageUrl, newImageAlt)}
                      disabled={!newImageUrl.trim()}
                    >
                      <Plus size={16} />
                      <span>Add Photo</span>
                    </button>
                  </div>
                </div>

                {/* Photo Gallery Grid */}
                {studioImages.length > 0 ? (
                  <div className="studio-photo-grid">
                    {studioImages.map((img, idx) => (
                      <div
                        key={idx}
                        className={`studio-photo-card ${img.is_primary ? "is-cover" : ""}`}
                      >
                        <img src={img.url} alt={img.alt_text} className="studio-photo-thumb" />
                        {img.is_primary && (
                          <span className="studio-photo-badge">Cover Photo</span>
                        )}
                        <div className="studio-photo-actions">
                          {!img.is_primary && (
                            <button
                              type="button"
                              className="studio-photo-btn"
                              onClick={() => handleSetPrimaryImage(idx)}
                              title="Make this the storefront cover photo"
                            >
                              Set Cover
                            </button>
                          )}
                          <button
                            type="button"
                            className="studio-photo-btn delete"
                            onClick={() => handleRemoveStudioImage(idx)}
                            title="Remove photo"
                            style={{ marginLeft: "auto" }}
                          >
                            <Trash2 size={11} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div
                    style={{
                      padding: "1.5rem",
                      background: "rgba(255, 255, 255, 0.03)",
                      border: "1px dashed rgba(255, 255, 255, 0.18)",
                      borderRadius: "var(--radius-sm)",
                      textAlign: "center",
                      color: "var(--text-secondary)",
                      marginTop: "1rem",
                      fontSize: "0.85rem",
                    }}
                  >
                    No photos attached yet. Enter an image URL above to attach high-resolution photography.
                  </div>
                )}
              </div>

              {/* Card 4: Craftsmanship & Description */}
              <div className="studio-card">
                <div className="studio-card-header">
                  <div>
                    <div className="studio-card-title">
                      <Sparkles size={16} />
                      <span>4. Craftsmanship, Weave &amp; Artisan Origin</span>
                    </div>
                    <div className="studio-card-subtitle">
                      Describe the textile heritage, zardozi embroidery, handloom details, and care guidelines
                    </div>
                  </div>
                </div>

                <div className="form-group">
                  <textarea
                    className="form-textarea"
                    rows={4}
                    placeholder="Describe the pure mulberry silk warp, intricate silver zari border, heritage handloom weaving technique, occasion styling, and dry-clean recommendations..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </div>
              </div>
            </div>

            {/* Right Column: Storefront Governance & Real-time Live Preview */}
            <div className="studio-side-col">
              {/* Card: Publishing Governance */}
              <div className="studio-card">
                <div className="studio-card-header">
                  <div className="studio-card-title">
                    <Package size={16} />
                    <span>Storefront Publishing</span>
                  </div>
                  <span
                    className={`status-pill ${isPublished ? "success" : "neutral"}`}
                    style={{ fontSize: "0.72rem" }}
                  >
                    {isPublished ? "PUBLISHED" : "DRAFT"}
                  </span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "1.25rem" }}>
                  <input
                    type="checkbox"
                    id="adminStudioPublishedCheck"
                    checked={isPublished}
                    onChange={(e) => setIsPublished(e.target.checked)}
                    style={{ width: 18, height: 18, cursor: "pointer" }}
                  />
                  <label htmlFor="adminStudioPublishedCheck" style={{ fontSize: "0.85rem", cursor: "pointer", color: "var(--text-primary)", fontWeight: 500 }}>
                    Publish to Customer Storefront immediately
                  </label>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ width: "100%", justifyContent: "center", padding: "0.75rem" }}
                    onClick={handleCreateSubmit}
                    disabled={submitting}
                  >
                    <Save size={16} />
                    <span>{submitting ? "Publishing Garment..." : "Publish Apparel to Storefront"}</span>
                  </button>

                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ width: "100%", justifyContent: "center" }}
                    onClick={() => setIsStudioOpen(false)}
                    disabled={submitting}
                  >
                    Cancel &amp; Discard
                  </button>
                </div>
              </div>

              {/* Card: Live Storefront Card Preview */}
              <div className="studio-card">
                <div className="studio-card-header">
                  <div>
                    <div className="studio-card-title">
                      <Sparkles size={16} />
                      <span>Live Storefront Card</span>
                    </div>
                    <div className="studio-card-subtitle">Live simulation of customer experience</div>
                  </div>
                  <span className="status-pill success" style={{ fontSize: "0.72rem" }}>
                    Live
                  </span>
                </div>

                <div className="studio-preview-card">
                  {primaryStudioImage ? (
                    <div style={{ position: "relative" }}>
                      <img
                        src={primaryStudioImage.url}
                        alt={primaryStudioImage.alt_text}
                        className="studio-preview-image"
                      />
                      {discountPct > 0 && (
                        <span
                          style={{
                            position: "absolute",
                            top: 10,
                            left: 10,
                            background: "#FEF2F2",
                            border: "1px solid #FECACA",
                            color: "#DC2626",
                            fontSize: "0.72rem",
                            fontWeight: 700,
                            padding: "3px 8px",
                            borderRadius: "4px",
                            letterSpacing: "0.04em",
                          }}
                        >
                          {discountPct}% OFF
                        </span>
                      )}
                    </div>
                  ) : (
                    <div className="studio-preview-placeholder">
                      <div className="studio-preview-monogram">
                        {name.trim() ? name.trim().charAt(0).toUpperCase() : "B"}
                      </div>
                      <span style={{ fontSize: "0.8rem", color: "var(--flame)", fontWeight: 500 }}>
                        Attach a photo above to preview
                      </span>
                    </div>
                  )}

                  <div className="studio-preview-body">
                    <div
                      style={{
                        fontSize: "0.72rem",
                        fontWeight: 700,
                        color: "var(--flame)",
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        marginBottom: 4,
                      }}
                    >
                      {selectedCategoryObj?.name || "Apparel Category"}
                    </div>

                    <div
                      style={{
                        fontFamily: "var(--font-serif)",
                        fontSize: "1.05rem",
                        fontWeight: 700,
                        color: "#FFFFFF",
                        lineHeight: 1.3,
                        marginBottom: 4,
                      }}
                    >
                      {name.trim() || "Untitled Garment"}
                    </div>

                    <div
                      style={{
                        fontSize: "0.78rem",
                        color: "var(--text-muted)",
                        marginBottom: 8,
                        fontWeight: 500,
                      }}
                    >
                      {selectedBrandObj?.name || "Bagodi Atelier"}
                    </div>

                    {/* Size Pills */}
                    <div className="studio-size-preview-row">
                      {sizeOptions
                        .filter((s) => s.enabled)
                        .map((s) => (
                          <span key={s.size} className="studio-size-chip-tag">
                            {s.size} ({s.stock})
                          </span>
                        ))}
                    </div>

                    {/* Price row */}
                    <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 8 }}>
                      <span style={{ fontSize: "1.15rem", fontWeight: 700, color: "#FFFFFF" }}>
                        ₹{parseFloat(basePrice || "0").toLocaleString("en-IN")}
                      </span>
                      {mrpNum > basePriceNum && (
                        <span
                          style={{
                            fontSize: "0.85rem",
                            color: "var(--text-muted)",
                            textDecoration: "line-through",
                          }}
                        >
                          ₹{mrpNum.toLocaleString("en-IN")}
                        </span>
                      )}
                    </div>

                    <button
                      type="button"
                      disabled
                      className="btn btn-primary"
                      style={{
                        width: "100%",
                        marginTop: 12,
                        justifyContent: "center",
                        opacity: 0.9,
                        cursor: "default",
                        fontSize: "0.82rem",
                      }}
                    >
                      Add to Bag
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </form>
      </div>
    );
  }

  // =========================================================================
  // VIEW 2: FULL-PAGE PRODUCT EDIT STUDIO
  // =========================================================================
  if (editingProduct) {
    return (
      <div className="product-studio-page">
        <div className="studio-header">
          <div>
            <button
              type="button"
              className="studio-back-btn"
              onClick={() => setEditingProduct(null)}
            >
              <ArrowLeft size={16} />
              <span>Back to Fashion Catalogue</span>
            </button>
            <div className="studio-title-area">
              <h2>Edit Apparel Garment</h2>
              <p>
                Modify titles, categorization, artisan origin descriptions, and storefront visibility for "{editingProduct.name}".
              </p>
            </div>
          </div>

          <div className="studio-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setEditingProduct(null)}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleUpdateSubmit}
              disabled={submitting}
            >
              <Save size={16} />
              <span>{submitting ? "Saving Changes..." : "Save Garment Updates"}</span>
            </button>
          </div>
        </div>

        <form onSubmit={handleUpdateSubmit}>
          <div className="studio-layout">
            <div className="studio-main-col">
              <div className="studio-card">
                <div className="studio-card-header">
                  <div className="studio-card-title">
                    <Shirt size={16} />
                    <span>Garment Metadata &amp; Classification</span>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Garment Title *</label>
                  <input
                    type="text"
                    className="form-input"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    required
                  />
                </div>

                <div className="form-row" style={{ marginTop: "1rem" }}>
                  <div className="form-group">
                    <label className="form-label">Category</label>
                    <select
                      className="form-select"
                      value={editCategoryId}
                      onChange={(e) => setEditCategoryId(e.target.value)}
                    >
                      <option value="">Select Category...</option>
                      {categories.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Brand Label</label>
                    <select
                      className="form-select"
                      value={editBrandId}
                      onChange={(e) => setEditBrandId(e.target.value)}
                    >
                      <option value="">Select Brand (Optional)...</option>
                      {brands.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="form-group" style={{ marginTop: "1rem" }}>
                  <label className="form-label">Apparel Description &amp; Craftsmanship</label>
                  <textarea
                    className="form-textarea"
                    rows={4}
                    value={editDesc}
                    onChange={(e) => setEditDesc(e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div className="studio-side-col">
              <div className="studio-card">
                <div className="studio-card-header">
                  <div className="studio-card-title">
                    <Package size={16} />
                    <span>Storefront Visibility</span>
                  </div>
                  <span
                    className={`status-pill ${editPublished ? "success" : "neutral"}`}
                    style={{ fontSize: "0.72rem" }}
                  >
                    {editPublished ? "PUBLISHED" : "DRAFT"}
                  </span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "1.25rem" }}>
                  <input
                    type="checkbox"
                    id="superAdminEditPublishedCheck"
                    checked={editPublished}
                    onChange={(e) => setEditPublished(e.target.checked)}
                    style={{ width: 18, height: 18, cursor: "pointer" }}
                  />
                  <label htmlFor="superAdminEditPublishedCheck" style={{ fontSize: "0.85rem", cursor: "pointer", color: "var(--text-primary)", fontWeight: 500 }}>
                    Visible on Storefront (Published)
                  </label>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    style={{ width: "100%", justifyContent: "center" }}
                    disabled={submitting}
                  >
                    <Save size={16} />
                    <span>{submitting ? "Saving Changes..." : "Save Garment Updates"}</span>
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ width: "100%", justifyContent: "center" }}
                    onClick={() => setEditingProduct(null)}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          </div>
        </form>
      </div>
    );
  }

  // =========================================================================
  // VIEW 3: DEFAULT CATALOGUE TABLE (PRODUCTS / CATEGORIES / BRANDS)
  // =========================================================================
  return (
    <div className="tab-pane">
      {/* Sub Tabs */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            className={`btn btn-sm ${activeTab === "products" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setActiveTab("products")}
          >
            <Shirt size={15} />
            <span>Apparel Catalogue ({products.length})</span>
          </button>
          <button
            className={`btn btn-sm ${activeTab === "categories" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setActiveTab("categories")}
          >
            <Layers size={15} />
            <span>Standard Categories ({categories.length})</span>
          </button>
          <button
            className={`btn btn-sm ${activeTab === "brands" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setActiveTab("brands")}
          >
            <Tag size={15} />
            <span>Bagodi Brands ({brands.length})</span>
          </button>
        </div>

        {activeTab === "products" && (
          <button
            className="btn btn-primary"
            onClick={() => {
              setErrorMsg(null);
              setIsStudioOpen(true);
            }}
          >
            <Plus size={16} />
            <span>Add Apparel Item</span>
          </button>
        )}
      </div>

      {activeTab === "products" && (
        <>
          {/* Controls */}
          <div className="table-controls">
            <div style={{ display: "flex", gap: "0.75rem", flex: 1, alignItems: "center", flexWrap: "wrap" }}>
              <div className="search-box" style={{ maxWidth: 320 }}>
                <Search size={16} color="var(--text-secondary)" />
                <input
                  type="text"
                  placeholder="Search catalogue by name or SKU..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <select
                className="form-select"
                style={{ width: 180 }}
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
              >
                <option value="ALL">All Categories</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>

              <select
                className="form-select"
                style={{ width: 180 }}
                value={selectedBrand}
                onChange={(e) => setSelectedBrand(e.target.value)}
              >
                <option value="ALL">All Brands</option>
                {brands.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Products Table */}
          <div className="table-wrapper" style={{ marginTop: "1rem" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Garment Item</th>
                  <th>Category</th>
                  <th>Brand Label</th>
                  <th>Sizes &amp; Stock</th>
                  <th>Price Range (₹)</th>
                  <th>Store Visibility</th>
                  <th style={{ textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                      <Shirt size={32} style={{ margin: "0 auto 0.75rem", display: "block", opacity: 0.4 }} />
                      <div style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "0.25rem" }}>
                        No apparel products in database
                      </div>
                      <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
                        Start creating authentic clothing items using the full-page garment studio.
                      </div>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => {
                          setErrorMsg(null);
                          setIsStudioOpen(true);
                        }}
                      >
                        <Plus size={15} />
                        <span>Add First Garment</span>
                      </button>
                    </td>
                  </tr>
                ) : (
                  filteredProducts.map((p) => {
                    const cat = categories.find((c) => c.id === p.category_id);
                    const br = brands.find((b) => b.id === p.brand_id);
                    const primaryImg = p.images?.find((img) => img.is_primary)?.url || p.images?.[0]?.url;
                    const prices = p.variants?.map((v) => Number(v.base_price)) || [];
                    const minPrice = prices.length > 0 ? Math.min(...prices) : 0;
                    const maxPrice = prices.length > 0 ? Math.max(...prices) : 0;

                    return (
                      <tr key={p.id}>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                            {primaryImg ? (
                              <img
                                src={primaryImg}
                                alt={p.name}
                                style={{
                                  width: 44,
                                  height: 56,
                                  objectFit: "cover",
                                  borderRadius: "var(--radius-xs)",
                                  border: "1px solid var(--border-medium)",
                                  flexShrink: 0,
                                }}
                              />
                            ) : (
                              <div
                                style={{
                                  width: 44,
                                  height: 56,
                                  background: "var(--bg-muted)",
                                  borderRadius: "var(--radius-xs)",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  color: "var(--flame)",
                                  flexShrink: 0,
                                }}
                              >
                                <Shirt size={20} />
                              </div>
                            )}
                            <div>
                              <div style={{ fontWeight: 600 }}>{p.name}</div>
                              <div style={{ fontSize: "0.75rem", color: "var(--flame)", fontFamily: "var(--font-mono)" }}>
                                /{p.slug}
                              </div>
                            </div>
                          </div>
                        </td>

                        <td>
                          <div style={{ fontWeight: 500 }}>{cat?.name || "—"}</div>
                        </td>

                        <td>
                          <div style={{ fontWeight: 500, color: "var(--text-muted)" }}>{br?.name || "Bagodi Atelier"}</div>
                        </td>

                        <td>
                          <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", marginBottom: "4px" }}>
                            {p.variants?.slice(0, 5).map((v) => (
                              <span
                                key={v.id}
                                style={{
                                  fontSize: "0.7rem",
                                  padding: "1px 5px",
                                  borderRadius: 3,
                                  background: (v.available_qty ?? 0) > 0 ? "rgba(255, 255, 255, 0.08)" : "rgba(239, 68, 68, 0.2)",
                                  color: (v.available_qty ?? 0) > 0 ? "#FFFFFF" : "var(--status-error)",
                                  border: "1px solid rgba(255, 255, 255, 0.15)",
                                  fontFamily: "var(--font-mono)",
                                }}
                              >
                                {v.size || "M"}: {v.available_qty ?? 0}
                              </span>
                            ))}
                          </div>
                        </td>

                        <td style={{ fontWeight: 600, color: "var(--flame)" }}>
                          {minPrice === maxPrice
                            ? `₹${minPrice.toLocaleString("en-IN")}`
                            : `₹${minPrice.toLocaleString("en-IN")} - ₹${maxPrice.toLocaleString("en-IN")}`}
                        </td>

                        <td>
                          <span className={`status-pill ${p.is_published ? "success" : "neutral"}`}>
                            {p.is_published ? "PUBLISHED" : "DRAFT"}
                          </span>
                        </td>

                        <td style={{ textAlign: "right" }}>
                          <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleStartEdit(p)}
                              title="Edit Garment Details"
                            >
                              <Edit3 size={14} />
                            </button>
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() =>
                                onUpdateProduct(p.id, {
                                  is_published: !p.is_published,
                                })
                              }
                              title={p.is_published ? "Unpublish from Store" : "Publish to Store"}
                            >
                              {p.is_published ? <EyeOff size={14} /> : <Eye size={14} />}
                            </button>
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => {
                                if (window.confirm(`Delete "${p.name}"? This removes all variants and inventory.`)) {
                                  onDeleteProduct(p.id);
                                }
                              }}
                              title="Delete Product"
                              style={{ color: "var(--status-error)" }}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Categories Tab */}
      {activeTab === "categories" && (
        <div className="table-wrapper" style={{ marginTop: "1rem" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Category Title</th>
                <th>Standard Slug</th>
                <th>Description</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {categories.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 600, color: "var(--flame)" }}>{c.name}</td>
                  <td>
                    <code style={{ color: "var(--flame)" }}>/{c.slug}</code>
                  </td>
                  <td style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>{c.description || "—"}</td>
                  <td>
                    <span className="status-pill success">Active</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Brands Tab */}
      {activeTab === "brands" && (
        <div className="table-wrapper" style={{ marginTop: "1rem" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Brand Name</th>
                <th>Brand Slug</th>
                <th>Heritage &amp; Description</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {brands.map((b) => (
                <tr key={b.id}>
                  <td style={{ fontWeight: 600, color: "var(--flame)" }}>{b.name}</td>
                  <td>
                    <code style={{ color: "var(--flame)" }}>/{b.slug}</code>
                  </td>
                  <td style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>{b.description || "—"}</td>
                  <td>
                    <span className="status-pill success">Official Brand</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
