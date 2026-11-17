import React, { useState } from "react";
import {
  Plus,
  Shirt,
  Tag,
  Layers,
  Search,
  Eye,
  EyeOff,
  X,
  Trash2,
  Edit3,
  Image as ImageIcon,
  ArrowLeft,
  Sparkles,
  Save,
  Check,
  AlertCircle,
  HelpCircle,
  Package,
} from "lucide-react";
import type { Category, Brand } from "../types";
import type { ProductDetail } from "@bagodi/api-client";

interface CatalogViewProps {
  products: ProductDetail[];
  categories: Category[];
  brands: Brand[];
  onCreateProduct: (data: any) => Promise<any>;
  onUpdateProduct: (productId: string, data: any) => Promise<any>;
  onDeleteProduct?: (productId: string) => Promise<void>;
  onAddVariant: (productId: string, data: any) => Promise<void>;
  onDeleteVariant?: (variantId: string) => Promise<void>;
  onAddImage?: (productId: string, data: any) => Promise<void>;
  onCreateCategory: (data: any) => Promise<void>;
  onCreateBrand: (data: any) => Promise<void>;
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

export const CatalogView: React.FC<CatalogViewProps> = ({
  products,
  categories,
  brands,
  onCreateProduct,
  onUpdateProduct,
  onDeleteProduct,
  onAddVariant,
  onDeleteVariant,
  onAddImage,
  onCreateCategory,
  onCreateBrand,
}) => {
  const [activeSubTab, setActiveSubTab] = useState<"products" | "categories" | "brands">("products");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  // View mode state
  const [isNewProductOpen, setIsNewProductOpen] = useState(() => {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get("action") === "new";
  });
  const [editingProduct, setEditingProduct] = useState<ProductDetail | null>(null);
  const [selectedProductForVariants, setSelectedProductForVariants] = useState<ProductDetail | null>(null);
  const [isNewCategoryOpen, setIsNewCategoryOpen] = useState(false);
  const [isNewBrandOpen, setIsNewBrandOpen] = useState(false);

  // New product form states
  const [newProductName, setNewProductName] = useState("");
  const [newProductCategoryId, setNewProductCategoryId] = useState("");
  const [newProductBrandId, setNewProductBrandId] = useState("");
  const [newProductDesc, setNewProductDesc] = useState("");
  const [newProductPublished, setNewProductPublished] = useState(true);
  const [newProductBasePrice, setNewProductBasePrice] = useState("");
  const [newProductMrp, setNewProductMrp] = useState("");

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
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Edit product form
  const [editName, setEditName] = useState("");
  const [editCategoryId, setEditCategoryId] = useState("");
  const [editBrandId, setEditBrandId] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editPublished, setEditPublished] = useState(true);

  // New variant form (for sub-view)
  const [variantSize, setVariantSize] = useState("M");
  const [variantColor, setVariantColor] = useState("");
  const [variantStock, setVariantStock] = useState("");
  const [variantBarcode, setVariantBarcode] = useState("");
  const [variantBasePrice, setVariantBasePrice] = useState("");
  const [variantMrp, setVariantMrp] = useState("");

  // New Image form (for sub-view)
  const [imageUrl, setImageUrl] = useState("");
  const [imageAlt, setImageAlt] = useState("");
  const [isPrimaryImage, setIsPrimaryImage] = useState(true);

  // New category form
  const [newCatName, setNewCatName] = useState("");
  const [newCatSlug, setNewCatSlug] = useState("");
  const [newCatDesc, setNewCatDesc] = useState("");

  // New brand form
  const [newBrandName, setNewBrandName] = useState("");
  const [newBrandSlug, setNewBrandSlug] = useState("");

  // Calculations for studio preview
  const basePriceNum = parseFloat(newProductBasePrice) || 0;
  const mrpNum = parseFloat(newProductMrp) || 0;
  const discountPct =
    mrpNum > basePriceNum && mrpNum > 0
      ? Math.round(((mrpNum - basePriceNum) / mrpNum) * 100)
      : 0;

  const selectedCategoryObj = categories.find((c) => c.id === newProductCategoryId);
  const selectedBrandObj = brands.find((b) => b.id === newProductBrandId);
  const primaryStudioImage = studioImages.find((img) => img.is_primary) || studioImages[0];
  const totalStockUnits = sizeOptions
    .filter((s) => s.enabled)
    .reduce((acc, s) => acc + (s.stock || 0), 0);

  const filteredProducts = products.filter((p) => {
    const matchesSearch =
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.variants?.some((v) => v.sku.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesCategory =
      selectedCategory === "ALL" || p.category_id === selectedCategory;
    const matchesStatus =
      statusFilter === "ALL" ||
      (statusFilter === "PUBLISHED" ? p.is_published : !p.is_published);
    return matchesSearch && matchesCategory && matchesStatus;
  });

  const handleToggleAllSizes = (enable: boolean) => {
    setSizeOptions((prev) =>
      prev.map((s) => ({
        ...s,
        enabled: enable,
        price: enable ? (s.price || newProductBasePrice) : "",
        mrp: enable ? (s.mrp || newProductMrp) : "",
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
        alt_text: altText || newProductName.trim() || "Garment Photo",
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

  const handleCreateProductSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (!newProductName.trim()) {
      setValidationError("Please enter a garment title.");
      return;
    }
    if (!newProductCategoryId) {
      setValidationError("Please select an apparel category.");
      return;
    }

    const activeSizes = sizeOptions.filter((s) => s.enabled);
    if (activeSizes.length === 0) {
      setValidationError("Please enable at least one clothing size (S, M, L, XL, XXL, or Free Size) with available stock.");
      return;
    }

    const variants = activeSizes.map((s) => ({
      name: `Size ${s.size}`,
      size: s.size,
      initial_stock: s.stock,
      base_price: s.price,
      mrp: s.mrp,
      status: "active",
    }));

    const images = studioImages.map((img, idx) => ({
      url: img.url,
      alt_text: img.alt_text || newProductName.trim(),
      is_primary: img.is_primary,
      sort_order: idx,
    }));

    setIsSubmitting(true);
    try {
      await onCreateProduct({
        name: newProductName.trim(),
        category_id: newProductCategoryId,
        brand_id: newProductBrandId || null,
        description: newProductDesc.trim() || null,
        is_published: newProductPublished,
        status: "active",
        variants,
        images,
      });

      setIsNewProductOpen(false);
      setNewProductName("");
      setNewProductDesc("");
      setStudioImages([]);
      setSizeOptions(DEFAULT_SIZES);
    } catch (err: any) {
      setValidationError(err?.message || "Failed to create apparel item. Please verify required fields and try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStartEditProduct = (p: ProductDetail) => {
    setEditingProduct(p);
    setEditName(p.name);
    setEditCategoryId(p.category_id || "");
    setEditBrandId(p.brand_id || "");
    setEditDesc(p.description || "");
    setEditPublished(p.is_published);
  };

  const handleUpdateProductSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingProduct) return;

    setIsSubmitting(true);
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
      alert(err?.message || "Failed to update product details.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteProductClick = async (productId: string, productName: string) => {
    if (window.confirm(`Are you sure you want to delete "${productName}" from the catalogue? This will also remove all its variants.`)) {
      if (onDeleteProduct) {
        await onDeleteProduct(productId);
      }
    }
  };

  const handleAddVariantSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProductForVariants) return;

    const stockQty = Math.max(0, parseInt(variantStock, 10) || 0);
    await onAddVariant(selectedProductForVariants.id, {
      name: `Size ${variantSize} / ${variantColor}`,
      size: variantSize,
      color: variantColor,
      initial_stock: stockQty,
      base_price: variantBasePrice,
      mrp: variantMrp,
      status: "active",
    });

    setVariantStock("10");
  };

  const handleDeleteVariantClick = async (variantId: string) => {
    if (window.confirm("Are you sure you want to remove this size variant?")) {
      if (onDeleteVariant) {
        await onDeleteVariant(variantId);
        if (selectedProductForVariants) {
          setSelectedProductForVariants({
            ...selectedProductForVariants,
            variants: selectedProductForVariants.variants?.filter((v) => v.id !== variantId),
          });
        }
      }
    }
  };

  const handleAddImageSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProductForVariants || !imageUrl.trim()) return;

    if (onAddImage) {
      await onAddImage(selectedProductForVariants.id, {
        url: imageUrl.trim(),
        alt_text: imageAlt.trim() || selectedProductForVariants.name,
        is_primary: isPrimaryImage,
        sort_order: 1,
      });

      setImageUrl("");
      setImageAlt("");
    }
  };

  const handleCreateCategorySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCatName.trim()) return;

    await onCreateCategory({
      name: newCatName.trim(),
      slug: newCatSlug.trim() || newCatName.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
      description: newCatDesc.trim() || null,
      is_active: true,
    });

    setIsNewCategoryOpen(false);
    setNewCatName("");
    setNewCatSlug("");
    setNewCatDesc("");
  };

  const handleCreateBrandSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBrandName.trim()) return;

    await onCreateBrand({
      name: newBrandName.trim(),
      slug: newBrandSlug.trim() || newBrandName.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
      is_active: true,
    });

    setIsNewBrandOpen(false);
    setNewBrandName("");
    setNewBrandSlug("");
  };

  // =========================================================================
  // VIEW 1: FULL-PAGE PRODUCT CREATION STUDIO
  // =========================================================================
  if (isNewProductOpen) {
    return (
      <div className="product-studio-page">
        {/* Studio Header */}
        <div className="studio-header">
          <div>
            <button
              type="button"
              className="studio-back-btn"
              onClick={() => setIsNewProductOpen(false)}
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
              onClick={() => setIsNewProductOpen(false)}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleCreateProductSubmit}
              disabled={isSubmitting}
            >
              <Save size={16} />
              <span>{isSubmitting ? "Publishing Garment..." : "Publish Apparel to Storefront"}</span>
            </button>
          </div>
        </div>

        {validationError && (
          <div className="studio-alert-error">
            <AlertCircle size={18} />
            <span>{validationError}</span>
          </div>
        )}

        <form onSubmit={handleCreateProductSubmit}>
          <div className="studio-layout">
            {/* Left Column: Garment Specifications & Assets */}
            <div className="studio-main-col">
              {/* Card 1: Identity & Pricing */}
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
                    placeholder="e.g. Bidar Handcrafted Chanderi Silk Saree with Metallic Zari"
                    value={newProductName}
                    onChange={(e) => setNewProductName(e.target.value)}
                    required
                  />
                </div>

                <div className="form-row" style={{ marginTop: "1rem" }}>
                  <div className="form-group">
                    <label className="form-label">Apparel Category *</label>
                    <select
                      className="form-select"
                      value={newProductCategoryId}
                      onChange={(e) => setNewProductCategoryId(e.target.value)}
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
                      value={newProductBrandId}
                      onChange={(e) => setNewProductBrandId(e.target.value)}
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
                      value={newProductBasePrice}
                      onChange={(e) => {
                        const val = e.target.value;
                        setNewProductBasePrice(val);
                        setSizeOptions((prev) => prev.map((s) => ({ ...s, price: val })));
                      }}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                      <label className="form-label">Garment MRP (₹) *</label>
                      {discountPct > 0 && (
                        <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--palette-plum)" }}>
                          {discountPct}% Storefront Discount
                        </span>
                      )}
                    </div>
                    <input
                      type="number"
                      step="0.01"
                      className="form-input"
                      value={newProductMrp}
                      onChange={(e) => {
                        const val = e.target.value;
                        setNewProductMrp(val);
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
                          <td style={{ fontWeight: 700, color: "var(--palette-blush)" }}>{opt.size}</td>
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
                  <span style={{ fontSize: "0.75rem", color: "var(--palette-blush)", fontWeight: 600 }}>
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
                      placeholder="e.g. Front look in natural light"
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
                    No photos attached yet. Click one of the instant presets above or enter a custom image URL.
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
                    value={newProductDesc}
                    onChange={(e) => setNewProductDesc(e.target.value)}
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
                    className={`status-pill ${newProductPublished ? "success" : "neutral"}`}
                    style={{ fontSize: "0.72rem" }}
                  >
                    {newProductPublished ? "PUBLISHED" : "DRAFT"}
                  </span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "1.25rem" }}>
                  <input
                    type="checkbox"
                    id="studioPublishedCheck"
                    checked={newProductPublished}
                    onChange={(e) => setNewProductPublished(e.target.checked)}
                    style={{ width: 18, height: 18, cursor: "pointer" }}
                  />
                  <label htmlFor="studioPublishedCheck" style={{ fontSize: "0.85rem", cursor: "pointer", color: "var(--text-primary)", fontWeight: 500 }}>
                    Publish to Customer Storefront immediately
                  </label>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ width: "100%", justifyContent: "center", padding: "0.75rem" }}
                    onClick={handleCreateProductSubmit}
                    disabled={isSubmitting}
                  >
                    <Save size={16} />
                    <span>{isSubmitting ? "Publishing Garment..." : "Publish Apparel to Storefront"}</span>
                  </button>

                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ width: "100%", justifyContent: "center" }}
                    onClick={() => setIsNewProductOpen(false)}
                    disabled={isSubmitting}
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
                            background: "var(--palette-plum)",
                            color: "#FFFFFF",
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
                        {newProductName.trim() ? newProductName.trim().charAt(0).toUpperCase() : "B"}
                      </div>
                      <span style={{ fontSize: "0.8rem", color: "var(--palette-blush)", fontWeight: 500 }}>
                        Attach or select a photo above
                      </span>
                    </div>
                  )}

                  <div className="studio-preview-body">
                    <div
                      style={{
                        fontSize: "0.72rem",
                        fontWeight: 700,
                        color: "var(--palette-blush)",
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
                      {newProductName.trim() || "Untitled Garment"}
                    </div>

                    <div
                      style={{
                        fontSize: "0.78rem",
                        color: "var(--palette-rosewood)",
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
                        ₹{parseFloat(newProductBasePrice || "0").toLocaleString("en-IN")}
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
    const editCategoryObj = categories.find((c) => c.id === editCategoryId);
    const editBrandObj = brands.find((b) => b.id === editBrandId);

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
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleUpdateProductSubmit}
              disabled={isSubmitting}
            >
              <Save size={16} />
              <span>{isSubmitting ? "Saving Changes..." : "Save Garment Updates"}</span>
            </button>
          </div>
        </div>

        <form onSubmit={handleUpdateProductSubmit}>
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
                    <label className="form-label">Label / Brand</label>
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
                    id="editPublishedCheck"
                    checked={editPublished}
                    onChange={(e) => setEditPublished(e.target.checked)}
                    style={{ width: 18, height: 18, cursor: "pointer" }}
                  />
                  <label htmlFor="editPublishedCheck" style={{ fontSize: "0.85rem", cursor: "pointer", color: "var(--text-primary)", fontWeight: 500 }}>
                    Visible on Storefront (Published)
                  </label>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    style={{ width: "100%", justifyContent: "center" }}
                    disabled={isSubmitting}
                  >
                    <Save size={16} />
                    <span>{isSubmitting ? "Saving Changes..." : "Save Garment Updates"}</span>
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
  // VIEW 3: FULL-PAGE SIZE VARIANTS & LOOKBOOK MANAGER
  // =========================================================================
  if (selectedProductForVariants) {
    return (
      <div className="product-studio-page">
        <div className="studio-header">
          <div>
            <button
              type="button"
              className="studio-back-btn"
              onClick={() => setSelectedProductForVariants(null)}
            >
              <ArrowLeft size={16} />
              <span>Back to Fashion Catalogue</span>
            </button>
            <div className="studio-title-area">
              <h2>Sizes, Stock &amp; Lookbook: {selectedProductForVariants.name}</h2>
              <p>
                Configure individual variant SKUs, manage available quantities, and attach high-res apparel photography.
              </p>
            </div>
          </div>

          <div className="studio-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setSelectedProductForVariants(null)}
            >
              <Check size={16} />
              <span>Done Managing Garment</span>
            </button>
          </div>
        </div>

        <div className="studio-layout">
          {/* Main Column: Active Variants Table & Add Variant Form */}
          <div className="studio-main-col">
            <div className="studio-card">
              <div className="studio-card-header">
                <div>
                  <div className="studio-card-title">
                    <Shirt size={16} />
                    <span>Active Size Variants ({selectedProductForVariants.variants?.length || 0})</span>
                  </div>
                  <div className="studio-card-subtitle">
                    Live inventory units per size SKU
                  </div>
                </div>
              </div>

              {(!selectedProductForVariants.variants || selectedProductForVariants.variants.length === 0) ? (
                <div
                  style={{
                    padding: "1.5rem",
                    background: "rgba(74, 74, 74, 0.2)",
                    borderRadius: "var(--radius-sm)",
                    textAlign: "center",
                    color: "var(--text-secondary)",
                    fontSize: "0.85rem",
                  }}
                >
                  No size variants registered for this garment yet. Add sizes below.
                </div>
              ) : (
                <div style={{ border: "1px solid var(--border-medium)", borderRadius: "var(--radius-sm)", overflow: "hidden" }}>
                  <table className="data-table" style={{ margin: 0, fontSize: "0.85rem" }}>
                    <thead>
                      <tr>
                        <th>Size</th>
                        <th>Color</th>
                        <th>SKU Code</th>
                        <th>Barcode</th>
                        <th>Available Stock</th>
                        <th>Price (MRP)</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedProductForVariants.variants.map((v) => (
                        <tr key={v.id}>
                          <td style={{ fontWeight: 700, color: "var(--palette-blush)" }}>{v.size || "—"}</td>
                          <td>{v.color || "—"}</td>
                          <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "var(--palette-blush)" }}>{v.sku}</td>
                          <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "var(--text-muted)" }}>{v.barcode || "—"}</td>
                          <td>
                            {(v.available_qty ?? 0) > 0 ? (
                              <span className="status-pill success" style={{ fontSize: "0.75rem" }}>
                                {v.available_qty} units
                              </span>
                            ) : (
                              <span className="status-pill danger" style={{ fontSize: "0.75rem" }}>
                                0 (Out of Stock)
                              </span>
                            )}
                          </td>
                          <td style={{ fontWeight: 600 }}>
                            ₹{parseFloat(v.base_price).toLocaleString("en-IN")}{" "}
                            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textDecoration: "line-through" }}>
                              ₹{parseFloat(v.mrp).toLocaleString("en-IN")}
                            </span>
                          </td>
                          <td>
                            {onDeleteVariant && (
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleDeleteVariantClick(v.id)}
                                title="Remove Variant"
                                style={{ color: "var(--status-danger)", padding: "4px 8px" }}
                              >
                                <Trash2 size={13} />
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Add Variant Sub-Form */}
              <div style={{ marginTop: "1.75rem", borderTop: "1px solid var(--border-medium)", paddingTop: "1.25rem" }}>
                <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--palette-blush)", marginBottom: "0.75rem" }}>
                  Add Garment Size &amp; Stock
                </div>

                <form onSubmit={handleAddVariantSubmit}>
                  <div className="form-row">
                    <div className="form-group">
                      <label className="form-label">Size *</label>
                      <select
                        className="form-select"
                        value={variantSize}
                        onChange={(e) => setVariantSize(e.target.value)}
                        required
                      >
                        <option value="XS">XS (36 in)</option>
                        <option value="S">S (38 in)</option>
                        <option value="M">M (40 in)</option>
                        <option value="L">L (42 in)</option>
                        <option value="XL">XL (44 in)</option>
                        <option value="XXL">XXL (46 in)</option>
                        <option value="Free Size">Free Size</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label className="form-label">Color Shade *</label>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="e.g. Royal Indigo, Maroon Zari"
                        value={variantColor}
                        onChange={(e) => setVariantColor(e.target.value)}
                        required
                      />
                    </div>
                  </div>

                  <div className="form-row" style={{ marginTop: "0.75rem" }}>
                    <div className="form-group">
                      <label className="form-label">Initial Stock Quantity *</label>
                      <input
                        type="number"
                        min="0"
                        className="form-input"
                        placeholder="e.g. 15"
                        value={variantStock}
                        onChange={(e) => setVariantStock(e.target.value)}
                        required
                      />
                    </div>

                    <div className="form-group">
                      <label className="form-label">Barcode / EAN (Optional)</label>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="Auto-generated if empty"
                        value={variantBarcode}
                        onChange={(e) => setVariantBarcode(e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="form-row" style={{ marginTop: "0.75rem" }}>
                    <div className="form-group">
                      <label className="form-label">Base Selling Price (₹) *</label>
                      <input
                        type="number"
                        step="0.01"
                        className="form-input"
                        value={variantBasePrice}
                        onChange={(e) => setVariantBasePrice(e.target.value)}
                        required
                      />
                    </div>

                    <div className="form-group">
                      <label className="form-label">MRP (₹) *</label>
                      <input
                        type="number"
                        step="0.01"
                        className="form-input"
                        value={variantMrp}
                        onChange={(e) => setVariantMrp(e.target.value)}
                        required
                      />
                    </div>
                  </div>

                  <div style={{ marginTop: "1rem", display: "flex", justifyContent: "flex-end" }}>
                    <button type="submit" className="btn btn-primary btn-sm">
                      <Plus size={15} />
                      <span>Add This Size Variant</span>
                    </button>
                  </div>
                </form>
              </div>
            </div>

            {/* Lookbook Photography Section */}
            {onAddImage && (
              <div className="studio-card">
                <div className="studio-card-header">
                  <div className="studio-card-title">
                    <ImageIcon size={16} />
                    <span>Storefront Photography &amp; Gallery</span>
                  </div>
                </div>

                {selectedProductForVariants.images && selectedProductForVariants.images.length > 0 && (
                  <div className="studio-photo-grid" style={{ marginBottom: "1.25rem" }}>
                    {selectedProductForVariants.images.map((img) => (
                      <div key={img.id} className={`studio-photo-card ${img.is_primary ? "is-cover" : ""}`}>
                        <img src={img.url} alt={img.alt_text || "Product photo"} className="studio-photo-thumb" />
                        {img.is_primary && (
                          <span className="studio-photo-badge">Cover</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                <form onSubmit={handleAddImageSubmit}>
                  <div className="form-row">
                    <div className="form-group" style={{ flex: 2 }}>
                      <label className="form-label">Image URL</label>
                      <input
                        type="url"
                        className="form-input"
                        placeholder="https://images.unsplash.com/photo-..."
                        value={imageUrl}
                        onChange={(e) => setImageUrl(e.target.value)}
                        required
                      />
                    </div>
                    <div className="form-group" style={{ flex: 1 }}>
                      <label className="form-label">Alt Text</label>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="Front look"
                        value={imageAlt}
                        onChange={(e) => setImageAlt(e.target.value)}
                      />
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "0.75rem" }}>
                    <label style={{ fontSize: "0.8125rem", display: "inline-flex", alignItems: "center", gap: "6px", cursor: "pointer", color: "var(--text-secondary)" }}>
                      <input
                        type="checkbox"
                        checked={isPrimaryImage}
                        onChange={(e) => setIsPrimaryImage(e.target.checked)}
                      />
                      <span>Set as primary storefront cover photo</span>
                    </label>
                    <button type="submit" className="btn btn-secondary btn-sm">
                      <Plus size={14} />
                      <span>Attach Photo</span>
                    </button>
                  </div>
                </form>
              </div>
            )}
          </div>

          {/* Side Column: Summary */}
          <div className="studio-side-col">
            <div className="studio-card">
              <div className="studio-card-header">
                <div className="studio-card-title">
                  <Package size={16} />
                  <span>Garment Status</span>
                </div>
                <span className={`status-pill ${selectedProductForVariants.is_published ? "success" : "neutral"}`}>
                  {selectedProductForVariants.is_published ? "PUBLISHED" : "DRAFT"}
                </span>
              </div>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                {selectedProductForVariants.description || "No description specified."}
              </p>
              <div style={{ marginTop: "1rem", paddingTop: "0.75rem", borderTop: "1px solid var(--border-light)" }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ width: "100%", justifyContent: "center" }}
                  onClick={() => setSelectedProductForVariants(null)}
                >
                  Return to Catalogue
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // VIEW 4: DEFAULT CATALOGUE TABLE (PRODUCTS / CATEGORIES / BRANDS)
  // =========================================================================
  return (
    <div>
      {/* Sub Tabs */}
      <div className="filter-tabs">
        <button
          className={`filter-tab ${activeSubTab === "products" ? "active" : ""}`}
          onClick={() => setActiveSubTab("products")}
        >
          <Shirt size={16} style={{ display: "inline", verticalAlign: "text-bottom", marginRight: 6 }} />
          Apparel Products ({products.length})
        </button>
        <button
          className={`filter-tab ${activeSubTab === "categories" ? "active" : ""}`}
          onClick={() => setActiveSubTab("categories")}
        >
          <Layers size={16} style={{ display: "inline", verticalAlign: "text-bottom", marginRight: 6 }} />
          Categories ({categories.length})
        </button>
        <button
          className={`filter-tab ${activeSubTab === "brands" ? "active" : ""}`}
          onClick={() => setActiveSubTab("brands")}
        >
          <Tag size={16} style={{ display: "inline", verticalAlign: "text-bottom", marginRight: 6 }} />
          Labels &amp; Brands ({brands.length})
        </button>
      </div>

      {/* PRODUCTS TAB */}
      {activeSubTab === "products" && (
        <div className="table-container">
          <div className="table-toolbar">
            <div className="table-toolbar-left">
              <div className="search-box" style={{ width: 240 }}>
                <Search size={16} color="var(--text-secondary)" />
                <input
                  type="text"
                  placeholder="Search products or SKUs..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <select
                className="form-select"
                style={{ width: 170, padding: "0.4rem 0.6rem" }}
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
                style={{ width: 150, padding: "0.4rem 0.6rem" }}
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="ALL">All Status</option>
                <option value="PUBLISHED">Published</option>
                <option value="DRAFT">Draft / Hidden</option>
              </select>
            </div>

            <div className="table-toolbar-right">
              <button
                className="btn btn-primary btn-sm"
                onClick={() => {
                  setValidationError(null);
                  setIsNewProductOpen(true);
                }}
              >
                <Plus size={16} />
                <span>Add Apparel Item</span>
              </button>
            </div>
          </div>

          {filteredProducts.length === 0 ? (
            <div className="table-empty">
              <div className="table-empty-icon">
                <Shirt size={48} />
              </div>
              <div className="table-empty-title">No apparel items found</div>
              <div className="table-empty-desc">
                {searchQuery || selectedCategory !== "ALL" || statusFilter !== "ALL"
                  ? "Try clearing your search query or category filters."
                  : "Start creating luxury clothing and heritage weaves using the full-page creation studio."}
              </div>
              <button
                className="btn btn-primary"
                onClick={() => {
                  setValidationError(null);
                  setIsNewProductOpen(true);
                }}
              >
                <Plus size={16} />
                <span>Add First Apparel Item</span>
              </button>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Product Details</th>
                  <th>Category &amp; Brand</th>
                  <th>Sizes &amp; Available Stock</th>
                  <th>Price Range (₹)</th>
                  <th>Store Visibility</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.map((p) => {
                  const cat = categories.find((c) => c.id === p.category_id);
                  const brand = brands.find((b) => b.id === p.brand_id);
                  const primaryImage = p.images?.find((img) => img.is_primary) || p.images?.[0];

                  const prices = p.variants?.map((v) => parseFloat(v.base_price)) || [];
                  const minPrice = prices.length ? Math.min(...prices) : 0;
                  const maxPrice = prices.length ? Math.max(...prices) : 0;
                  const priceStr =
                    minPrice === maxPrice
                      ? `₹${minPrice.toLocaleString("en-IN")}`
                      : `₹${minPrice.toLocaleString("en-IN")} - ₹${maxPrice.toLocaleString("en-IN")}`;

                  const totalStock = p.variants?.reduce(
                    (acc, v) => acc + (v.available_qty ?? 0),
                    0
                  ) ?? 0;

                  return (
                    <tr key={p.id}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.85rem" }}>
                          {primaryImage ? (
                            <img
                              src={primaryImage.url}
                              alt={p.name}
                              style={{
                                width: 44,
                                height: 56,
                                objectFit: "cover",
                                borderRadius: "var(--radius-xs)",
                                border: "1px solid var(--border-light)",
                                flexShrink: 0,
                              }}
                            />
                          ) : (
                            <div
                              style={{
                                width: 44,
                                height: 56,
                                background: "var(--bg-subtle)",
                                borderRadius: "var(--radius-xs)",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                color: "var(--palette-blush)",
                                flexShrink: 0,
                                border: "1px solid var(--border-light)",
                              }}
                            >
                              <Shirt size={20} />
                            </div>
                          )}
                          <div>
                            <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{p.name}</div>
                            <div style={{ fontSize: "0.75rem", color: "var(--palette-blush)", fontFamily: "var(--font-mono)" }}>
                              /{p.slug}
                            </div>
                          </div>
                        </div>
                      </td>

                      <td>
                        <div style={{ fontWeight: 500 }}>{cat?.name || "—"}</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--palette-rosewood)" }}>
                          {brand?.name || "Bagodi Atelier"}
                        </div>
                      </td>

                      <td>
                        <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap", marginBottom: "0.25rem" }}>
                          {p.variants?.slice(0, 5).map((v) => (
                            <span
                              key={v.id}
                              style={{
                                fontSize: "0.7rem",
                                padding: "1px 5px",
                                borderRadius: 3,
                                background: (v.available_qty ?? 0) > 0 ? "rgba(255, 255, 255, 0.08)" : "rgba(239, 68, 68, 0.2)",
                                color: (v.available_qty ?? 0) > 0 ? "#FFFFFF" : "var(--status-danger)",
                                border: "1px solid rgba(255, 255, 255, 0.15)",
                                fontFamily: "var(--font-mono)",
                              }}
                            >
                              {v.size || "M"}: {v.available_qty ?? 0}
                            </span>
                          ))}
                          {(p.variants?.length || 0) > 5 && (
                            <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                              +{p.variants!.length - 5}
                            </span>
                          )}
                        </div>
                        <span
                          className={`status-pill ${totalStock > 0 ? "success" : "danger"}`}
                          style={{ fontSize: "0.7rem", padding: "1px 6px" }}
                        >
                          {totalStock > 0 ? `${totalStock} units total` : "Out of Stock"}
                        </span>
                      </td>

                      <td style={{ fontWeight: 600, color: "var(--palette-blush)" }}>
                        {priceStr}
                      </td>

                      <td>
                        <span
                          className={`status-pill ${p.is_published ? "success" : "neutral"}`}
                        >
                          {p.is_published ? "PUBLISHED" : "DRAFT"}
                        </span>
                      </td>

                      <td>
                        <div style={{ display: "flex", gap: "0.35rem" }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => setSelectedProductForVariants(p)}
                            title="Manage Variants, Sizes & Photos"
                          >
                            <Shirt size={14} />
                            <span>Sizes ({p.variants?.length || 0})</span>
                          </button>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleStartEditProduct(p)}
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
                            title={p.is_published ? "Unpublish Product" : "Publish to Online Store"}
                          >
                            {p.is_published ? <EyeOff size={14} /> : <Eye size={14} />}
                          </button>
                          {onDeleteProduct && (
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleDeleteProductClick(p.id, p.name)}
                              title="Delete Product"
                              style={{ color: "var(--status-danger)" }}
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* CATEGORIES TAB */}
      {activeSubTab === "categories" && (
        <div className="table-container">
          <div className="table-toolbar">
            <span style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--palette-blush)" }}>Retail Fashion Categories</span>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setIsNewCategoryOpen(true)}
            >
              <Plus size={16} />
              <span>New Category</span>
            </button>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>Category Name</th>
                <th>Slug</th>
                <th>Description</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {categories.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 600, color: "var(--palette-blush)" }}>{c.name}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.82rem" }}>/{c.slug}</td>
                  <td style={{ color: "var(--text-secondary)", fontSize: "0.8125rem" }}>
                    {c.description || "—"}
                  </td>
                  <td>
                    <span className="status-pill success">Active</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* BRANDS TAB */}
      {activeSubTab === "brands" && (
        <div className="table-container">
          <div className="table-toolbar">
            <span style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--palette-blush)" }}>Fashion Labels &amp; Brands</span>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setIsNewBrandOpen(true)}
            >
              <Plus size={16} />
              <span>New Label</span>
            </button>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>Label / Brand</th>
                <th>Slug</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {brands.map((b) => (
                <tr key={b.id}>
                  <td style={{ fontWeight: 600, color: "var(--palette-blush)" }}>{b.name}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.82rem" }}>/{b.slug}</td>
                  <td>
                    <span className="status-pill success">Active</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* CREATE CATEGORY MODAL */}
      {isNewCategoryOpen && (
        <div className="modal-overlay" onClick={() => setIsNewCategoryOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Register Apparel Category</h3>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setIsNewCategoryOpen(false)}
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleCreateCategorySubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Category Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Chanderi Silk Sarees"
                    value={newCatName}
                    onChange={(e) => setNewCatName(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group" style={{ marginTop: "1rem" }}>
                  <label className="form-label">Description</label>
                  <textarea
                    className="form-textarea"
                    rows={2}
                    placeholder="Traditional handloom weaves crafted with metallic zari..."
                    value={newCatDesc}
                    onChange={(e) => setNewCatDesc(e.target.value)}
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsNewCategoryOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Category
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CREATE BRAND MODAL */}
      {isNewBrandOpen && (
        <div className="modal-overlay" onClick={() => setIsNewBrandOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Register Apparel Label / Brand</h3>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setIsNewBrandOpen(false)}
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleCreateBrandSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Brand / Label Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Bagodi Heritage"
                    value={newBrandName}
                    onChange={(e) => setNewBrandName(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsNewBrandOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Brand Label
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
