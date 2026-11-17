import React, { useState, useEffect, useCallback } from "react";
import {
  Search,
  ShoppingBag,
  Sparkles,
  User as UserIcon,
  X,
  Plus,
  Minus,
  ArrowRight,
  Star,
  Truck,
  ShieldCheck,
  CreditCard,
  Smartphone,
  Building2,
  Banknote,
  CheckCircle2,
  Package,
  QrCode,
} from "lucide-react";
import { client, setTokens, clearAuth, extractApiError } from "@bagodi/api-client";
import type { ProductDetail } from "@bagodi/api-client";

interface StorefrontViewProps {
  onNavigateToMerchant: () => void;
}

interface CartItem {
  id: string;
  productId: string;
  variantId: string;
  name: string;
  size: string;
  color: string;
  price: number;
  mrp: number;
  imageUrl?: string;
  quantity: number;
  available_qty: number;
}

export const StorefrontView: React.FC<StorefrontViewProps> = ({ onNavigateToMerchant }) => {
  // Navigation View State
  const [activeView, setActiveView] = useState<"catalog" | "pdp" | "checkout" | "order-confirmed" | "my-orders">("catalog");

  // Catalog State
  const [products, setProducts] = useState<ProductDetail[]>([]);
  const [categories, setCategories] = useState<{ id: string; name: string; slug: string }[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  // PDP (Product Details Page) State
  const [activeProduct, setActiveProduct] = useState<ProductDetail | null>(null);
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(null);
  const [selectedQuantity, setSelectedQuantity] = useState<number>(1);
  const [activeImageIdx, setActiveImageIdx] = useState<number>(0);
  const [pincodeInput, setPincodeInput] = useState<string>("585401");
  const [pincodeStatus, setPincodeStatus] = useState<string | null>(null);

  // Customer Auth State
  const [customerUser, setCustomerUser] = useState<{ id: string; email?: string; name?: string } | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authTab, setAuthTab] = useState<"login" | "register">("login");
  const [authIdentifier, setAuthIdentifier] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [regName, setRegName] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPhone, setRegPhone] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  // Cart & Checkout State
  const [cart, setCart] = useState<CartItem[]>([]);
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [checkoutItems, setCheckoutItems] = useState<CartItem[]>([]);
  const [shippingAddress, setShippingAddress] = useState({
    full_name: "Customer",
    phone: "9876500001",
    address_line1: "Main Bazaar, Heritage Circle",
    city: "Bidar",
    state: "Karnataka",
    postal_code: "585401",
  });
  const [paymentMethod, setPaymentMethod] = useState<"upi" | "card" | "netbanking" | "cod">("upi");
  const [upiId, setUpiId] = useState("bagodi.retail@okhdfcbank");
  const [showUpiQr, setShowUpiQr] = useState(false);
  const [cardData, setCardData] = useState({
    number: "4532 •••• •••• 8821",
    name: "Customer",
    expiry: "09/28",
    cvv: "•••",
  });
  const [selectedBank, setSelectedBank] = useState("HDFC Bank");
  const [orderNotes, setOrderNotes] = useState("");
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);

  // Order Confirmed State
  const [confirmedOrder, setConfirmedOrder] = useState<any | null>(null);

  // Customer Order History State
  const [customerOrders, setCustomerOrders] = useState<any[]>([]);
  const [isLoadingOrders, setIsLoadingOrders] = useState(false);

  // Toast
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // Load Catalog from PostgreSQL Database
  const loadCatalog = useCallback(async () => {
    setIsLoading(true);
    try {
      const [catResp, prodResp] = await Promise.all([
        client.GET("/api/v1/catalog/categories"),
        client.GET("/api/v1/catalog/products"),
      ]);

      if (catResp.data && Array.isArray(catResp.data)) {
        setCategories(catResp.data as any);
      }
      if (prodResp.data && Array.isArray(prodResp.data)) {
        setProducts(prodResp.data as any);
      } else {
        setProducts([]);
      }
    } catch (err) {
      console.warn("Catalog fetch notice:", err);
      setProducts([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  // Load Customer Orders
  const loadCustomerOrders = useCallback(async () => {
    if (!customerUser) return;
    setIsLoadingOrders(true);
    try {
      const resp = await client.GET("/api/v1/orders/my-orders");
      if (resp.data && Array.isArray(resp.data)) {
        setCustomerOrders(resp.data);
      } else {
        setCustomerOrders([]);
      }
    } catch (err) {
      console.warn("Orders fetch notice:", err);
      setCustomerOrders([]);
    } finally {
      setIsLoadingOrders(false);
    }
  }, [customerUser]);

  useEffect(() => {
    if (activeView === "my-orders") {
      loadCustomerOrders();
    }
  }, [activeView, loadCustomerOrders]);

  // Auth Handlers
  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    setAuthLoading(true);

    try {
      const resp = await client.POST("/api/v1/auth/login", {
        body: {
          email: authIdentifier.trim(),
          password: authPassword.trim(),
        },
      });

      if (resp.error || !resp.data) {
        const parsed = extractApiError(resp.error);
        setAuthError(parsed.message || "Invalid credentials.");
        return;
      }

      setTokens(resp.data.access_token, resp.data.refresh_token);
      const userObj = {
        id: resp.data.user.id,
        email: resp.data.user.email || undefined,
        name: resp.data.user.display_name || "Customer",
      };
      setCustomerUser(userObj);
      setShippingAddress((prev) => ({
        ...prev,
        full_name: userObj.name,
      }));
      setIsAuthModalOpen(false);
      setAuthIdentifier("");
      setAuthPassword("");
      showToast(`Welcome back, ${userObj.name}!`);
    } catch (err) {
      setAuthError(extractApiError(err).message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    setAuthLoading(true);

    try {
      const resp = await client.POST("/api/v1/auth/register", {
        body: {
          display_name: regName.trim(),
          email: regEmail.trim(),
          phone_e164: regPhone.trim() ? (regPhone.startsWith("+") ? regPhone : `+91${regPhone.replace(/\D/g, "")}`) : null,
          password: regPassword.trim(),
        },
      });

      if (resp.error || !resp.data) {
        const parsed = extractApiError(resp.error);
        setAuthError(parsed.message || "Registration failed.");
        return;
      }

      setTokens(resp.data.access_token, resp.data.refresh_token);
      const userObj = {
        id: resp.data.user.id,
        email: resp.data.user.email || undefined,
        name: resp.data.user.display_name || "Customer",
      };
      setCustomerUser(userObj);
      setShippingAddress((prev) => ({
        ...prev,
        full_name: userObj.name,
        phone: regPhone.trim() || prev.phone,
      }));
      setIsAuthModalOpen(false);
      setRegName("");
      setRegEmail("");
      setRegPhone("");
      setRegPassword("");
      showToast("Account created successfully!");
    } catch (err) {
      setAuthError(extractApiError(err).message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleCustomerLogout = () => {
    clearAuth();
    setCustomerUser(null);
    if (activeView === "my-orders") {
      setActiveView("catalog");
    }
    showToast("Signed out of customer account.");
  };

  // Open Dedicated Full-Page Product Details View
  const handleOpenPDP = (product: ProductDetail) => {
    setActiveProduct(product);
    // Select first in-stock variant if available
    const firstInStock = product.variants?.find((v) => (v.available_qty ?? 0) > 0) || product.variants?.[0];
    setSelectedVariantId(firstInStock?.id || null);
    setSelectedQuantity(1);
    setActiveImageIdx(0);
    setPincodeStatus(null);
    setActiveView("pdp");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Add to Bag
  const handleAddToCart = (product: ProductDetail, variantId?: string, qty: number = 1) => {
    const v = product.variants?.find((item) => (variantId ? item.id === variantId : true)) || product.variants?.[0];
    if (!v) {
      showToast("Please select a garment size first.");
      return;
    }

    const available = v.available_qty ?? 0;
    if (available <= 0) {
      showToast(`Size ${v.size || "Standard"} is currently out of stock.`);
      return;
    }

    const existing = cart.find((item) => item.productId === product.id && item.variantId === v.id);
    const existingQty = existing ? existing.quantity : 0;
    if (existingQty + qty > available) {
      showToast(`Only ${available} unit(s) available for size ${v.size || "Standard"}.`);
      return;
    }

    const price = parseFloat(v.base_price) || 0;
    const mrp = parseFloat(v.mrp) || 0;
    const primaryImg = product.images?.find((img) => img.is_primary)?.url || product.images?.[0]?.url;

    setCart((prev) => {
      if (existing) {
        return prev.map((item) =>
          item.variantId === v.id ? { ...item, quantity: item.quantity + qty } : item
        );
      }
      return [
        ...prev,
        {
          id: `cart_${Date.now()}_${v.id}`,
          productId: product.id,
          variantId: v.id,
          name: product.name,
          size: v.size || "Free Size",
          color: v.color || "Standard",
          price,
          mrp,
          imageUrl: primaryImg,
          quantity: qty,
          available_qty: available,
        },
      ];
    });

    showToast(`Added ${qty}x "${product.name} (Size: ${v.size || "Free"})" to Shopping Bag`);
  };

  // Buy Now: Immediately opens dedicated Checkout page with this product
  const handleBuyNow = (product: ProductDetail, variantId?: string, qty: number = 1) => {
    const v = product.variants?.find((item) => (variantId ? item.id === variantId : true)) || product.variants?.[0];
    if (!v) {
      showToast("Please select a valid garment size.");
      return;
    }

    const available = v.available_qty ?? 0;
    if (available <= 0) {
      showToast(`Size ${v.size || "Standard"} is currently out of stock.`);
      return;
    }

    const price = parseFloat(v.base_price) || 0;
    const mrp = parseFloat(v.mrp) || 0;
    const primaryImg = product.images?.find((img) => img.is_primary)?.url || product.images?.[0]?.url;

    const singleItem: CartItem = {
      id: `buynow_${Date.now()}_${v.id}`,
      productId: product.id,
      variantId: v.id,
      name: product.name,
      size: v.size || "Free Size",
      color: v.color || "Standard",
      price,
      mrp,
      imageUrl: primaryImg,
      quantity: qty,
      available_qty: available,
    };

    setCheckoutItems([singleItem]);
    setCheckoutError(null);
    setActiveView("checkout");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Proceed to Checkout from Cart
  const handleProceedFromCart = () => {
    if (cart.length === 0) {
      showToast("Your shopping bag is empty.");
      return;
    }
    setCheckoutItems([...cart]);
    setIsCartOpen(false);
    setCheckoutError(null);
    setActiveView("checkout");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Submit Order via Direct Checkout
  const handlePlaceOrder = async () => {
    if (!customerUser) {
      setIsAuthModalOpen(true);
      return;
    }

    if (checkoutItems.length === 0) {
      setCheckoutError("No garments selected for checkout.");
      return;
    }

    if (!shippingAddress.full_name.trim() || !shippingAddress.phone.trim() || !shippingAddress.address_line1.trim()) {
      setCheckoutError("Please fill in complete delivery address details.");
      return;
    }

    setIsSubmittingOrder(true);
    setCheckoutError(null);

    try {
      const items = checkoutItems.map((i) => ({
        variant_id: i.variantId,
        quantity: i.quantity,
      }));

      const resp = await client.POST("/api/v1/orders/direct-checkout", {
        body: {
          items,
          customer_name: shippingAddress.full_name.trim(),
          customer_email: customerUser.email || undefined,
          customer_phone: shippingAddress.phone.trim(),
          payment_method: paymentMethod,
          shipping_address: {
            full_name: shippingAddress.full_name.trim(),
            phone: shippingAddress.phone.trim(),
            address_line1: shippingAddress.address_line1.trim(),
            city: shippingAddress.city.trim() || "Bidar",
            state: shippingAddress.state.trim() || "Karnataka",
            postal_code: shippingAddress.postal_code.trim() || "585401",
          },
          notes: orderNotes.trim() ? `${orderNotes.trim()} [Method: ${paymentMethod.toUpperCase()}]` : `Direct Checkout (${paymentMethod.toUpperCase()})`,
        },
      });

      if (resp.error || !resp.data) {
        const parsed = extractApiError(resp.error);
        setCheckoutError(parsed.message || "Checkout failed. An item may have sold out.");
        return;
      }

      const orderData = resp.data as any;
      setConfirmedOrder(orderData);

      // If checkout was from cart, clear cart
      setCart((prev) => prev.filter((c) => !checkoutItems.some((ci) => ci.variantId === c.variantId)));
      setCheckoutItems([]);

      // Reload catalog to sync real stock deductions
      await loadCatalog();

      // Navigate to dedicated confirmation view
      setActiveView("order-confirmed");
      window.scrollTo({ top: 0, behavior: "smooth" });
      showToast(`Order #${orderData.order_number} confirmed! Inventory updated.`);
    } catch (err) {
      setCheckoutError(extractApiError(err).message);
    } finally {
      setIsSubmittingOrder(false);
    }
  };

  // Pincode check
  const handleCheckPincode = (e: React.FormEvent) => {
    e.preventDefault();
    if (pincodeInput.trim().length !== 6) {
      setPincodeStatus("Please enter a valid 6-digit Indian PIN code.");
      return;
    }
    if (pincodeInput.startsWith("585")) {
      setPincodeStatus("✓ Bidar Express: Delivery in 1-2 business days (Direct from Atelier)");
    } else {
      setPincodeStatus("✓ PAN-India Standard: Delivery in 3-5 business days via BlueDart");
    }
  };

  // Filtered Products
  const filteredProducts = products.filter((p) => {
    const matchesCategory = selectedCategoryId === "ALL" || p.category_id === selectedCategoryId;
    const matchesSearch =
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.description?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  // Financial Calculations
  const cartTotal = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const cartItemsCount = cart.reduce((sum, item) => sum + item.quantity, 0);

  const checkoutSubtotal = checkoutItems.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const isFreeDelivery = checkoutSubtotal >= 999;
  const checkoutDeliveryFee = checkoutSubtotal > 0 && !isFreeDelivery ? 49 : 0;
  const checkoutTotal = checkoutSubtotal + checkoutDeliveryFee;

  // Active PDP variant calculation
  const currentVariant = activeProduct?.variants?.find((v) => (selectedVariantId ? v.id === selectedVariantId : true)) || activeProduct?.variants?.[0];
  const currentPrice = currentVariant ? parseFloat(currentVariant.base_price) : 0;
  const currentMrp = currentVariant ? parseFloat(currentVariant.mrp) : 0;
  const currentDiscount = currentMrp > currentPrice && currentMrp > 0 ? Math.round(((currentMrp - currentPrice) / currentMrp) * 100) : 0;
  const currentStock = currentVariant?.available_qty ?? 0;
  const isCurrentOutOfStock = currentStock <= 0;

  // Image list for PDP
  const productImages = activeProduct?.images && activeProduct.images.length > 0
    ? activeProduct.images
    : [{ id: "def_img", url: "", is_primary: true, display_order: 0 }];

  return (
    <div className="storefront-container">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="storefront-toast">
          <Sparkles size={16} />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Main Storefront Header */}
      <header className="storefront-header">
        <div className="storefront-header-content">
          <div
            className="storefront-brand"
            style={{ cursor: "pointer" }}
            onClick={() => {
              setActiveView("catalog");
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          >
            <h1 className="brand-title">Bagodi</h1>
            <span className="brand-tagline">Haute Couture & Heritage Silks • Bidar Atelier</span>
          </div>

          <div className="storefront-header-actions">
            {/* Search Box */}
            <div className="storefront-search">
              <Search size={16} />
              <input
                type="text"
                placeholder="Search sarees, kurtas, sherwanis..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  if (activeView !== "catalog") {
                    setActiveView("catalog");
                  }
                }}
              />
            </div>

            {/* Collections Shortcut */}
            <button
              type="button"
              className={`btn btn-secondary btn-sm ${activeView === "catalog" ? "active" : ""}`}
              onClick={() => {
                setActiveView("catalog");
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
            >
              Collections
            </button>

            {/* Customer Account & Order History */}
            {customerUser ? (
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <button
                  type="button"
                  className={`btn btn-secondary btn-sm ${activeView === "my-orders" ? "active" : ""}`}
                  onClick={() => {
                    setActiveView("my-orders");
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                  title="View your placed orders"
                >
                  <Package size={15} />
                  <span>My Orders</span>
                </button>

                <div className="customer-badge">
                  <UserIcon size={16} />
                  <span>{customerUser.name}</span>
                  <button type="button" className="btn-link" onClick={handleCustomerLogout}>
                    Sign Out
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setIsAuthModalOpen(true)}
              >
                <UserIcon size={16} />
                <span>Customer Sign In</span>
              </button>
            )}

            {/* Cart Button */}
            <button
              type="button"
              className="btn btn-primary btn-sm storefront-cart-btn"
              onClick={() => setIsCartOpen(true)}
            >
              <ShoppingBag size={16} />
              <span>Bag ({cartItemsCount})</span>
            </button>
          </div>
        </div>
      </header>

      {/* =====================================================================
          VIEW 1: CATALOGUE GRID (Default)
          ===================================================================== */}
      {activeView === "catalog" && (
        <>
          {/* Hero Showcase Banner */}
          <section className="storefront-hero">
            <div className="hero-content">
              <span className="hero-eyebrow">BIDAR FLAGSHIP ATELIER • ZERO COMPROMISE CRAFTSMANSHIP</span>
              <h2 className="hero-heading">Handcrafted Luxury Fashion & Bespoke Tailoring</h2>
              <p className="hero-lead">
                Discover authentic Banarasi silks, handwoven Bidri-inspired zari dupattas, tailored wedding sherwanis, and contemporary festive wear direct from master artisans.
              </p>

              <div className="hero-trust-bar">
                <span>✓ Certified Pure Handloom</span>
                <span>✓ Real Database Synchronization</span>
                <span>✓ Live Size-Wise Inventory</span>
              </div>
            </div>
          </section>

          {/* Category Navigation */}
          <nav className="storefront-category-nav">
            <button
              type="button"
              className={`category-pill ${selectedCategoryId === "ALL" ? "active" : ""}`}
              onClick={() => setSelectedCategoryId("ALL")}
            >
              All Collections
            </button>
            {categories.map((c) => (
              <button
                key={c.id}
                type="button"
                className={`category-pill ${selectedCategoryId === c.id ? "active" : ""}`}
                onClick={() => setSelectedCategoryId(c.id)}
              >
                {c.name}
              </button>
            ))}
          </nav>

          {/* Products Grid */}
          <main className="storefront-main">
            {isLoading ? (
              <div className="storefront-loading">
                <Sparkles size={24} className="animate-spin" />
                <p>Loading live boutique catalog from PostgreSQL...</p>
              </div>
            ) : filteredProducts.length === 0 ? (
              <div className="storefront-empty-state">
                <div className="empty-icon-circle">
                  <ShoppingBag size={32} />
                </div>
                <h3>No Apparel Products Found in Catalogue</h3>
                <p>
                  Your Bagodi Bidar store catalog is live and connected directly to the PostgreSQL database.
                  Zero mock/dummy data policy is active. Products created and published by merchants will appear here immediately.
                </p>
                <button type="button" className="btn btn-primary" onClick={onNavigateToMerchant}>
                  Open Merchant Portal to Add Products
                </button>
              </div>
            ) : (
              <div className="storefront-product-grid">
                {filteredProducts.map((p) => {
                  const primaryImg = p.images?.find((img) => img.is_primary)?.url || p.images?.[0]?.url;
                  const firstVariant = p.variants?.[0];
                  const price = firstVariant ? parseFloat(firstVariant.base_price) : 0;
                  const mrp = firstVariant ? parseFloat(firstVariant.mrp) : 0;
                  const discountPercent = mrp > price && mrp > 0 ? Math.round(((mrp - price) / mrp) * 100) : 0;
                  const catName = categories.find((c) => c.id === p.category_id)?.name || "Apparel";
                  const isAllOutOfStock = (p.variants || []).length > 0 && (p.variants || []).every((v) => (v.available_qty ?? 0) <= 0);

                  return (
                    <article key={p.id} className="fashion-card">
                      <div className="fashion-card-media" onClick={() => handleOpenPDP(p)}>
                        {primaryImg ? (
                          <img src={primaryImg} alt={p.name} loading="lazy" />
                        ) : (
                          <div className="fashion-placeholder-img">
                            <ShoppingBag size={36} color="var(--brand-terracotta)" />
                            <span>Bagodi Atelier</span>
                          </div>
                        )}
                        {isAllOutOfStock ? (
                          <span className="card-badge-discount" style={{ background: "var(--status-danger)", color: "#fff" }}>
                            OUT OF STOCK
                          </span>
                        ) : discountPercent > 0 ? (
                          <span className="card-badge-discount">-{discountPercent}% OFF</span>
                        ) : null}
                      </div>

                      <div className="fashion-card-details">
                        <span className="fashion-card-category">{catName}</span>
                        <h3 className="fashion-card-title" onClick={() => handleOpenPDP(p)}>
                          {p.name}
                        </h3>

                        {/* Available Sizes with Stock Indicators */}
                        <div className="fashion-card-sizes">
                          {p.variants?.map((v) => {
                            const isOutOfStock = (v.available_qty ?? 0) <= 0;
                            return (
                              <span
                                key={v.id}
                                className={`size-badge ${isOutOfStock ? "out-of-stock" : ""}`}
                                style={{
                                  textDecoration: isOutOfStock ? "line-through" : "none",
                                  opacity: isOutOfStock ? 0.6 : 1,
                                  border: isOutOfStock ? "1px dashed var(--status-danger)" : undefined,
                                }}
                                title={`${v.size || "Free"} — ${v.available_qty ?? 0} in stock`}
                              >
                                {v.size || "Free"}
                              </span>
                            );
                          })}
                        </div>

                        <div className="fashion-card-pricing">
                          <span className="selling-price">
                            {price > 0 ? `₹${price.toLocaleString("en-IN")}` : "Price On Request"}
                          </span>
                          {mrp > price && (
                            <span className="mrp-price">₹{mrp.toLocaleString("en-IN")}</span>
                          )}
                        </div>

                        <div className="fashion-card-actions" style={{ display: "flex", gap: "0.5rem" }}>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            style={{ flex: 1 }}
                            onClick={() => handleOpenPDP(p)}
                          >
                            View Details
                          </button>
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            style={{ flex: 1 }}
                            disabled={isAllOutOfStock}
                            onClick={() => handleAddToCart(p)}
                          >
                            {isAllOutOfStock ? "Out of Stock" : "Add to Bag"}
                          </button>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </main>
        </>
      )}

      {/* =====================================================================
          VIEW 2: DEDICATED FULL-PAGE PRODUCT DETAILS PAGE (PDP)
          ===================================================================== */}
      {activeView === "pdp" && activeProduct && (
        <div className="pdp-page">
          {/* Breadcrumbs */}
          <nav className="pdp-breadcrumb">
            <button type="button" onClick={() => setActiveView("catalog")}>
              Collections
            </button>
            <span className="pdp-breadcrumb-sep">/</span>
            <span>{categories.find((c) => c.id === activeProduct.category_id)?.name || "Fashion"}</span>
            <span className="pdp-breadcrumb-sep">/</span>
            <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>{activeProduct.name}</span>
          </nav>

          <div className="pdp-grid">
            {/* Left Column: Multi-Image Gallery */}
            <div className="pdp-gallery-col">
              {productImages.length > 1 && (
                <div className="pdp-thumb-strip">
                  {productImages.map((img, idx) => (
                    <button
                      key={img.id || idx}
                      type="button"
                      className={`pdp-thumb-btn ${activeImageIdx === idx ? "active" : ""}`}
                      onClick={() => setActiveImageIdx(idx)}
                    >
                      {img.url ? (
                        <img src={img.url} alt={`${activeProduct.name} thumbnail ${idx + 1}`} />
                      ) : (
                        <div className="fashion-placeholder-img" style={{ fontSize: "0.65rem" }}>
                          <ShoppingBag size={18} />
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}

              <div className="pdp-main-image-wrap">
                {productImages[activeImageIdx]?.url ? (
                  <img src={productImages[activeImageIdx].url} alt={activeProduct.name} />
                ) : (
                  <div className="fashion-placeholder-img large">
                    <ShoppingBag size={56} color="var(--brand-terracotta)" />
                    <span style={{ fontSize: "1.2rem", fontWeight: 700 }}>Bagodi Flagship Atelier</span>
                    <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Bidar, Karnataka</span>
                  </div>
                )}
                <span className="pdp-badge-origin">100% Authentic Handloom</span>
              </div>
            </div>

            {/* Middle Column: Garment Intel & Specifications */}
            <div className="pdp-info-col">
              <span className="pdp-brand-tag">
                {categories.find((c) => c.id === activeProduct.category_id)?.name || "HERITAGE COUTURE"} • BIDAR ATELIER
              </span>

              <h1 className="pdp-title">{activeProduct.name}</h1>

              <div className="pdp-rating-row">
                <div className="pdp-stars">
                  <Star size={14} fill="currentColor" />
                  <span>4.9</span>
                </div>
                <span className="pdp-review-count">48 Verified Boutique Reviews</span>
                <span style={{ color: "var(--status-success)", fontWeight: 600 }}>• In High Demand</span>
              </div>

              <div className="pdp-divider" />

              {/* Price Block */}
              <div className="pdp-price-box">
                <span className="pdp-selling-price">₹{currentPrice.toLocaleString("en-IN")}</span>
                {currentMrp > currentPrice && (
                  <span className="pdp-mrp-price">₹{currentMrp.toLocaleString("en-IN")}</span>
                )}
                {currentDiscount > 0 && (
                  <span className="pdp-discount-pill">{currentDiscount}% OFF</span>
                )}
              </div>
              <p className="pdp-tax-notice">Inclusive of all taxes & free shipping for orders over ₹999</p>

              {/* Description & Craft Story */}
              <div className="pdp-description">
                <p>
                  {activeProduct.description ||
                    "Master handcrafted couture garment created exclusively in the Bagodi Bidar atelier. Woven with pure natural silk fibers and accented with exquisite traditional craftsmanship."}
                </p>
              </div>

              {/* Specifications Table */}
              <div className="pdp-specs-card">
                <h4 className="pdp-specs-title">Garment Specifications</h4>
                <table className="pdp-specs-table">
                  <tbody>
                    <tr>
                      <td>Fabric & Weave</td>
                      <td>Pure Handloom Silk / Chanderi Jacquard</td>
                    </tr>
                    <tr>
                      <td>Artisan Cluster</td>
                      <td>Bidar Heritage Weavers, Karnataka</td>
                    </tr>
                    <tr>
                      <td>Fit & Cut</td>
                      <td>Contemporary Tailored Fit</td>
                    </tr>
                    <tr>
                      <td>Wash & Care</td>
                      <td>Dry Clean Recommended for Silk Preservation</td>
                    </tr>
                    <tr>
                      <td>Authenticity</td>
                      <td>Silk Mark & Handloom Board Certified</td>
                    </tr>
                    <tr>
                      <td>SKU Code</td>
                      <td style={{ fontFamily: "monospace" }}>{currentVariant?.sku || "AUTO-GENERATED-BGD"}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Merchant / Seller Information */}
              <div className="pdp-merchant-info-card">
                <span className="pdp-merchant-label">Sold & Crafted By</span>
                <span className="pdp-merchant-name">Bagodi Flagship Atelier & Boutique</span>
                <p style={{ fontSize: "0.825rem", color: "var(--text-secondary)", margin: "0.2rem 0" }}>
                  Main Heritage Road, Bidar, Karnataka - 585401
                </p>
                <div className="pdp-merchant-badges">
                  <span>✓ Verified Heritage Merchant</span>
                  <span>✓ 100% Direct Artisan Wages</span>
                  <span>✓ Tax Invoice & GST Compliant</span>
                </div>
              </div>
            </div>

            {/* Right Column: Buy Box & Shopping Actions */}
            <div className="pdp-buybox-col">
              <div className="pdp-buybox-price-header">
                <span className="pdp-buybox-price">₹{currentPrice.toLocaleString("en-IN")}</span>
                {isCurrentOutOfStock ? (
                  <span className="pdp-buybox-stock-status out-of-stock">Out of Stock</span>
                ) : currentStock <= 5 ? (
                  <span className="pdp-buybox-stock-status low-stock">Only {currentStock} Left!</span>
                ) : (
                  <span className="pdp-buybox-stock-status in-stock">✓ In Stock ({currentStock})</span>
                )}
              </div>

              {/* Size Selector */}
              <div className="pdp-size-selection-block">
                <div className="pdp-size-header">
                  <span>Select Clothing Size:</span>
                  <span style={{ color: "var(--brand-terracotta)", fontWeight: 700 }}>
                    {currentVariant?.size || "Select a size"}
                  </span>
                </div>

                <div className="pdp-sizes-grid">
                  {activeProduct.variants?.map((v) => {
                    const isOut = (v.available_qty ?? 0) <= 0;
                    const isSelected = (selectedVariantId || activeProduct.variants?.[0]?.id) === v.id;
                    return (
                      <button
                        key={v.id}
                        type="button"
                        className={`pdp-size-chip ${isSelected ? "selected" : ""} ${isOut ? "out-of-stock" : ""}`}
                        disabled={isOut}
                        onClick={() => {
                          setSelectedVariantId(v.id);
                          setSelectedQuantity(1);
                        }}
                      >
                        <span className="pdp-size-chip-name">{v.size || "Free"}</span>
                        <span className="pdp-size-chip-qty" style={{ color: isOut ? "var(--status-danger)" : (v.available_qty ?? 0) <= 5 ? "var(--brand-terracotta)" : "var(--status-success)" }}>
                          {isOut ? "Out of Stock" : `${v.available_qty ?? 0} in stock`}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Quantity Selector */}
              <div className="pdp-qty-row">
                <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>Quantity:</span>
                <div className="pdp-qty-control">
                  <button
                    type="button"
                    className="pdp-qty-btn"
                    disabled={selectedQuantity <= 1}
                    onClick={() => setSelectedQuantity((q) => Math.max(1, q - 1))}
                  >
                    <Minus size={14} />
                  </button>
                  <span className="pdp-qty-value">{selectedQuantity}</span>
                  <button
                    type="button"
                    className="pdp-qty-btn"
                    disabled={selectedQuantity >= currentStock}
                    onClick={() => setSelectedQuantity((q) => Math.min(currentStock, q + 1))}
                  >
                    <Plus size={14} />
                  </button>
                </div>
              </div>

              {/* Two Clear Shopping Actions */}
              <div className="pdp-actions-row">
                <button
                  type="button"
                  className="btn-add-to-cart"
                  disabled={isCurrentOutOfStock}
                  onClick={() => handleAddToCart(activeProduct, selectedVariantId || undefined, selectedQuantity)}
                >
                  <ShoppingBag size={18} />
                  <span>{isCurrentOutOfStock ? "Out of Stock" : "Add to Cart"}</span>
                </button>

                <button
                  type="button"
                  className="btn-buy-now"
                  disabled={isCurrentOutOfStock}
                  onClick={() => handleBuyNow(activeProduct, selectedVariantId || undefined, selectedQuantity)}
                >
                  <ArrowRight size={18} />
                  <span>{isCurrentOutOfStock ? "Size Unavailable" : "Buy Now"}</span>
                </button>
              </div>

              {/* Pincode Estimator */}
              <div className="pdp-pincode-box">
                <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                  Check Delivery Time to Your Area:
                </span>
                <form onSubmit={handleCheckPincode} className="pdp-pincode-input-row">
                  <input
                    type="text"
                    maxLength={6}
                    className="pdp-pincode-input"
                    value={pincodeInput}
                    onChange={(e) => setPincodeInput(e.target.value.replace(/\D/g, ""))}
                    placeholder="Enter 6-digit PIN"
                  />
                  <button type="submit" className="btn btn-secondary btn-sm">
                    Check
                  </button>
                </form>
                {pincodeStatus && (
                  <span style={{ fontSize: "0.75rem", color: pincodeStatus.startsWith("✓") ? "var(--status-success)" : "var(--status-danger)", fontWeight: 600 }}>
                    {pincodeStatus}
                  </span>
                )}
              </div>

              {/* Trust & Guarantee Highlights */}
              <div className="pdp-trust-list">
                <div className="pdp-trust-item">
                  <Truck size={15} color="var(--botanical-sage)" />
                  <span>Free Express Delivery above ₹999</span>
                </div>
                <div className="pdp-trust-item">
                  <ShieldCheck size={15} color="var(--botanical-sage)" />
                  <span>7 Days Boutique Exchange & Alteration</span>
                </div>
                <div className="pdp-trust-item">
                  <CreditCard size={15} color="var(--botanical-sage)" />
                  <span>100% Secure UPI / Card / COD Payments</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          VIEW 3: DEDICATED FULL-PAGE CART & CHECKOUT VIEW
          ===================================================================== */}
      {activeView === "checkout" && (
        <div className="checkout-page">
          {/* Breadcrumb Navigation */}
          <nav className="pdp-breadcrumb">
            <button type="button" onClick={() => setActiveView("catalog")}>
              Collections
            </button>
            <span className="pdp-breadcrumb-sep">/</span>
            <button type="button" onClick={() => setIsCartOpen(true)}>
              Shopping Bag
            </button>
            <span className="pdp-breadcrumb-sep">/</span>
            <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>Secure Checkout</span>
          </nav>

          {checkoutError && (
            <div className="auth-error-banner" style={{ marginBottom: "1.5rem" }}>
              {checkoutError}
            </div>
          )}

          <div className="checkout-grid">
            {/* Left Steps Column */}
            <div className="checkout-steps-col">
              {/* Step 1: Delivery Address */}
              <div className="checkout-step-card">
                <h3 className="checkout-step-title">
                  <span className="step-num">1</span>
                  <span>Delivery Address</span>
                </h3>

                <div className="checkout-form-grid">
                  <div className="form-group">
                    <label className="form-label">Full Name *</label>
                    <input
                      type="text"
                      className="form-input"
                      value={shippingAddress.full_name}
                      onChange={(e) => setShippingAddress({ ...shippingAddress, full_name: e.target.value })}
                      placeholder="e.g. Ramesh Patil"
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Mobile Contact Number *</label>
                    <input
                      type="tel"
                      className="form-input"
                      value={shippingAddress.phone}
                      onChange={(e) => setShippingAddress({ ...shippingAddress, phone: e.target.value })}
                      placeholder="98765 00001"
                      required
                    />
                  </div>

                  <div className="form-group" style={{ gridColumn: "span 2" }}>
                    <label className="form-label">Street / House / Boutique Address *</label>
                    <input
                      type="text"
                      className="form-input"
                      value={shippingAddress.address_line1}
                      onChange={(e) => setShippingAddress({ ...shippingAddress, address_line1: e.target.value })}
                      placeholder="e.g. House #14, Main Heritage Bazaar, near Bidar Fort"
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">City *</label>
                    <input
                      type="text"
                      className="form-input"
                      value={shippingAddress.city}
                      onChange={(e) => setShippingAddress({ ...shippingAddress, city: e.target.value })}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">State / Province *</label>
                    <input
                      type="text"
                      className="form-input"
                      value={shippingAddress.state}
                      onChange={(e) => setShippingAddress({ ...shippingAddress, state: e.target.value })}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Postal PIN Code *</label>
                    <input
                      type="text"
                      maxLength={6}
                      className="form-input"
                      value={shippingAddress.postal_code}
                      onChange={(e) => setShippingAddress({ ...shippingAddress, postal_code: e.target.value.replace(/\D/g, "") })}
                      required
                    />
                  </div>
                </div>
              </div>

              {/* Step 2: Review Ordered Garments */}
              <div className="checkout-step-card">
                <h3 className="checkout-step-title">
                  <span className="step-num">2</span>
                  <span>Review Items in Order ({checkoutItems.reduce((acc, i) => acc + i.quantity, 0)})</span>
                </h3>

                <div className="cart-items-list">
                  {checkoutItems.map((item) => (
                    <div key={item.id} className="cart-item-row">
                      <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                        {item.imageUrl ? (
                          <img
                            src={item.imageUrl}
                            alt={item.name}
                            style={{ width: "56px", height: "64px", objectFit: "cover", borderRadius: "var(--radius-xs)" }}
                          />
                        ) : (
                          <div style={{ width: "56px", height: "64px", background: "var(--bg-subtle)", display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "var(--radius-xs)" }}>
                            <ShoppingBag size={20} color="var(--brand-terracotta)" />
                          </div>
                        )}
                        <div className="cart-item-info">
                          <span className="cart-item-name">{item.name}</span>
                          <span className="cart-item-meta">
                            Size: <strong style={{ color: "var(--brand-terracotta)" }}>{item.size}</strong> • {item.color}
                          </span>
                          <span className="cart-item-price">
                            ₹{item.price.toLocaleString("en-IN")} × {item.quantity} = ₹{(item.price * item.quantity).toLocaleString("en-IN")}
                          </span>
                        </div>
                      </div>

                      <div className="cart-item-qty">
                        <button
                          type="button"
                          onClick={() => {
                            if (item.quantity <= 1) {
                              setCheckoutItems((prev) => prev.filter((i) => i.id !== item.id));
                            } else {
                              setCheckoutItems((prev) =>
                                prev.map((i) => (i.id === item.id ? { ...i, quantity: i.quantity - 1 } : i))
                              );
                            }
                          }}
                        >
                          <Minus size={12} />
                        </button>
                        <span>{item.quantity}</span>
                        <button
                          type="button"
                          disabled={item.quantity >= item.available_qty}
                          onClick={() =>
                            setCheckoutItems((prev) =>
                              prev.map((i) => (i.id === item.id ? { ...i, quantity: i.quantity + 1 } : i))
                            )
                          }
                        >
                          <Plus size={12} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Step 3: Payment Method Integration (Requirement 11) */}
              <div className="checkout-step-card">
                <h3 className="checkout-step-title">
                  <span className="step-num">3</span>
                  <span>Select Payment Method</span>
                </h3>

                <div className="payment-methods-grid">
                  <button
                    type="button"
                    className={`payment-tab-btn ${paymentMethod === "upi" ? "active" : ""}`}
                    onClick={() => setPaymentMethod("upi")}
                  >
                    <Smartphone size={20} color="var(--brand-terracotta)" />
                    <span className="payment-tab-title">UPI</span>
                    <span className="payment-tab-sub">GPay, PhonePe</span>
                  </button>

                  <button
                    type="button"
                    className={`payment-tab-btn ${paymentMethod === "card" ? "active" : ""}`}
                    onClick={() => setPaymentMethod("card")}
                  >
                    <CreditCard size={20} color="var(--brand-terracotta)" />
                    <span className="payment-tab-title">Cards</span>
                    <span className="payment-tab-sub">Credit / Debit</span>
                  </button>

                  <button
                    type="button"
                    className={`payment-tab-btn ${paymentMethod === "netbanking" ? "active" : ""}`}
                    onClick={() => setPaymentMethod("netbanking")}
                  >
                    <Building2 size={20} color="var(--brand-terracotta)" />
                    <span className="payment-tab-title">Net Banking</span>
                    <span className="payment-tab-sub">All Indian Banks</span>
                  </button>

                  <button
                    type="button"
                    className={`payment-tab-btn ${paymentMethod === "cod" ? "active" : ""}`}
                    onClick={() => setPaymentMethod("cod")}
                  >
                    <Banknote size={20} color="var(--brand-terracotta)" />
                    <span className="payment-tab-title">COD</span>
                    <span className="payment-tab-sub">Cash on Delivery</span>
                  </button>
                </div>

                {/* Payment Detail Box */}
                <div className="payment-body-box">
                  {paymentMethod === "upi" && (
                    <div>
                      <div className="form-group" style={{ marginBottom: "1rem" }}>
                        <label className="form-label">Virtual Payment Address (UPI ID)</label>
                        <input
                          type="text"
                          className="form-input"
                          value={upiId}
                          onChange={(e) => setUpiId(e.target.value)}
                          placeholder="e.g. yourname@okhdfcbank"
                        />
                      </div>

                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => setShowUpiQr(!showUpiQr)}
                        >
                          <QrCode size={16} />
                          <span>{showUpiQr ? "Hide QR Code" : "Scan UPI QR Code Instead"}</span>
                        </button>
                        <span style={{ fontSize: "0.8rem", color: "var(--botanical-sage)", fontWeight: 600 }}>
                          ✓ Instant zero-fee verification
                        </span>
                      </div>

                      {showUpiQr && (
                        <div style={{ marginTop: "1rem", display: "flex", alignItems: "center", gap: "1rem", background: "#FFFFFF", padding: "1rem", borderRadius: "var(--radius-sm)" }}>
                          <div style={{ width: "90px", height: "90px", border: "1px solid var(--border-medium)", display: "flex", alignItems: "center", justifyContent: "center", background: "#fff" }}>
                            <QrCode size={64} color="var(--brand-terracotta)" />
                          </div>
                          <div>
                            <strong style={{ fontSize: "0.9rem" }}>Scan with Any UPI App</strong>
                            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", margin: "0.2rem 0" }}>
                              Open GPay, PhonePe, Paytm or BHIM to pay ₹{checkoutTotal.toLocaleString("en-IN")}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {paymentMethod === "card" && (
                    <div className="checkout-form-grid">
                      <div className="form-group" style={{ gridColumn: "span 2" }}>
                        <label className="form-label">Card Number</label>
                        <input
                          type="text"
                          className="form-input"
                          value={cardData.number}
                          onChange={(e) => setCardData({ ...cardData, number: e.target.value })}
                          placeholder="4532 0000 0000 8821"
                        />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Name on Card</label>
                        <input
                          type="text"
                          className="form-input"
                          value={cardData.name}
                          onChange={(e) => setCardData({ ...cardData, name: e.target.value })}
                          placeholder="Cardholder Name"
                        />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Expiry / CVV</label>
                        <div style={{ display: "flex", gap: "0.5rem" }}>
                          <input
                            type="text"
                            className="form-input"
                            value={cardData.expiry}
                            onChange={(e) => setCardData({ ...cardData, expiry: e.target.value })}
                            placeholder="MM/YY"
                          />
                          <input
                            type="password"
                            maxLength={4}
                            className="form-input"
                            value={cardData.cvv}
                            onChange={(e) => setCardData({ ...cardData, cvv: e.target.value })}
                            placeholder="CVV"
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  {paymentMethod === "netbanking" && (
                    <div className="form-group">
                      <label className="form-label">Choose Bank</label>
                      <select
                        className="form-input"
                        value={selectedBank}
                        onChange={(e) => setSelectedBank(e.target.value)}
                      >
                        <option value="HDFC Bank">HDFC Bank</option>
                        <option value="State Bank of India">State Bank of India (SBI)</option>
                        <option value="ICICI Bank">ICICI Bank</option>
                        <option value="Axis Bank">Axis Bank</option>
                        <option value="Kotak Mahindra Bank">Kotak Mahindra Bank</option>
                        <option value="Karnataka Bank">Karnataka Bank</option>
                      </select>
                    </div>
                  )}

                  {paymentMethod === "cod" && (
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", color: "var(--text-secondary)", fontSize: "0.875rem" }}>
                      <Banknote size={24} color="var(--brand-terracotta)" />
                      <span>
                        Pay with cash or UPI directly to our delivery executive when your parcel arrives in Bidar or your destination city.
                      </span>
                    </div>
                  )}
                </div>

                {/* Order Notes */}
                <div className="form-group" style={{ marginTop: "1.25rem" }}>
                  <label className="form-label">Special Delivery Instructions / Tailoring Notes (Optional)</label>
                  <input
                    type="text"
                    className="form-input"
                    value={orderNotes}
                    onChange={(e) => setOrderNotes(e.target.value)}
                    placeholder="e.g. Ring doorbell, deliver during morning hours"
                  />
                </div>
              </div>
            </div>

            {/* Right Summary Sidebar */}
            <div className="checkout-summary-col">
              <div className="checkout-summary-card">
                <h3 className="checkout-summary-title">Order Summary</h3>

                <div className="checkout-item-preview-list">
                  {checkoutItems.map((item) => (
                    <div key={item.id} className="checkout-item-preview-row">
                      {item.imageUrl ? (
                        <img src={item.imageUrl} alt={item.name} className="checkout-item-preview-img" />
                      ) : (
                        <div className="checkout-item-preview-img" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <ShoppingBag size={16} color="var(--brand-terracotta)" />
                        </div>
                      )}
                      <div className="checkout-item-preview-info">
                        <div className="checkout-item-preview-title">{item.name}</div>
                        <div className="checkout-item-preview-size">
                          Size {item.size} • Qty {item.quantity}
                        </div>
                      </div>
                      <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>
                        ₹{(item.price * item.quantity).toLocaleString("en-IN")}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="checkout-bill-row">
                  <span>Garments Subtotal:</span>
                  <span>₹{checkoutSubtotal.toLocaleString("en-IN")}</span>
                </div>

                <div className="checkout-bill-row">
                  <span>Shipping & Handling:</span>
                  <span>{isFreeDelivery ? <strong style={{ color: "var(--status-success)" }}>FREE</strong> : "₹49"}</span>
                </div>

                <div className="checkout-bill-row">
                  <span>Handloom Artisan Cess:</span>
                  <span style={{ color: "var(--status-success)" }}>₹0 (Covered by Bagodi)</span>
                </div>

                <div className="checkout-bill-total">
                  <span>Final Payable Amount:</span>
                  <span className="checkout-total-amt">₹{checkoutTotal.toLocaleString("en-IN")}</span>
                </div>

                <div style={{ marginTop: "1.5rem" }}>
                  <button
                    type="button"
                    className="btn btn-primary btn-full"
                    style={{ padding: "0.85rem", fontSize: "1rem", fontWeight: 700 }}
                    disabled={isSubmittingOrder || checkoutItems.length === 0}
                    onClick={handlePlaceOrder}
                  >
                    {isSubmittingOrder ? (
                      <span>Verifying & Placing Order...</span>
                    ) : (
                      <span>
                        {customerUser
                          ? `Confirm & Place Order (₹${checkoutTotal.toLocaleString("en-IN")})`
                          : "Sign In & Confirm Order"}
                      </span>
                    )}
                  </button>
                </div>

                <div style={{ marginTop: "1.25rem", textAlign: "center", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  <span>🔒 256-Bit Encrypted Database Transaction • Guaranteed Artisan Quality</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          VIEW 4: DEDICATED FULL-PAGE ORDER CONFIRMATION PAGE (Requirement 12)
          ===================================================================== */}
      {activeView === "order-confirmed" && confirmedOrder && (
        <div className="order-confirm-page">
          <div className="order-confirm-card">
            <div className="order-confirm-header">
              <div className="order-confirm-icon">
                <CheckCircle2 size={44} />
              </div>
              <h2 className="order-confirm-title">Order Confirmed!</h2>
              <p className="order-confirm-sub">
                Thank you for choosing Bagodi. Your handcrafted luxury apparel is now confirmed and recorded in the database.
              </p>
            </div>

            {/* Order Reference Banner */}
            <div className="order-confirm-number-banner">
              <div>
                <span className="order-id-label">Official Order Reference</span>
                <div className="order-id-val">{confirmedOrder.order_number}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <span className="order-id-label">Estimated Delivery</span>
                <div style={{ fontWeight: 700, color: "var(--botanical-sage)" }}>
                  Within 2-3 Business Days (Express Dispatch from Bidar)
                </div>
              </div>
            </div>

            {/* Real-time Order Tracking Stepper */}
            <div className="order-tracking-stepper">
              <div className="stepper-step completed">
                <div className="stepper-dot">✓</div>
                <span className="stepper-label">Order Confirmed</span>
              </div>
              <div className="stepper-step active">
                <div className="stepper-dot">2</div>
                <span className="stepper-label">Quality Check & Packing</span>
              </div>
              <div className="stepper-step">
                <div className="stepper-dot">3</div>
                <span className="stepper-label">Dispatched from Bidar</span>
              </div>
              <div className="stepper-step">
                <div className="stepper-dot">4</div>
                <span className="stepper-label">Out for Delivery</span>
              </div>
              <div className="stepper-step">
                <div className="stepper-dot">5</div>
                <span className="stepper-label">Delivered</span>
              </div>
            </div>

            {/* Ordered Garments List */}
            <div style={{ marginBottom: "2rem" }}>
              <h4 style={{ fontFamily: "var(--font-serif)", fontSize: "1.15rem", marginBottom: "1rem" }}>
                Garments in this Order
              </h4>
              <div className="cart-items-list">
                {confirmedOrder.items?.map((item: any) => (
                  <div key={item.id} className="cart-item-row">
                    <div className="cart-item-info">
                      <span className="cart-item-name">{item.product_name}</span>
                      <span className="cart-item-meta">
                        SKU: <strong style={{ fontFamily: "monospace" }}>{item.sku}</strong> • Quantity: {item.quantity}
                      </span>
                    </div>
                    <span className="cart-item-price">
                      ₹{parseFloat(item.total_price || item.unit_price).toLocaleString("en-IN")}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Shipping Address & Payment Method Summary */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", background: "var(--bg-subtle)", padding: "1.25rem", borderRadius: "var(--radius-md)", marginBottom: "2rem" }}>
              <div>
                <strong style={{ fontSize: "0.85rem", textTransform: "uppercase", color: "var(--text-muted)" }}>
                  Shipping Address
                </strong>
                <p style={{ fontSize: "0.9rem", marginTop: "0.4rem", color: "var(--text-primary)" }}>
                  {confirmedOrder.shipping_address?.full_name || confirmedOrder.customer_name}<br />
                  {confirmedOrder.shipping_address?.address_line1}<br />
                  {confirmedOrder.shipping_address?.city}, {confirmedOrder.shipping_address?.state} - {confirmedOrder.shipping_address?.postal_code}<br />
                  Phone: {confirmedOrder.shipping_address?.phone || confirmedOrder.customer_phone}
                </p>
              </div>

              <div>
                <strong style={{ fontSize: "0.85rem", textTransform: "uppercase", color: "var(--text-muted)" }}>
                  Payment Details
                </strong>
                <p style={{ fontSize: "0.9rem", marginTop: "0.4rem", color: "var(--text-primary)" }}>
                  Method: <strong style={{ textTransform: "uppercase", color: "var(--brand-terracotta)" }}>{confirmedOrder.payment_method}</strong><br />
                  Payment Status: <span style={{ color: "var(--status-success)", fontWeight: 700 }}>{confirmedOrder.payment_status?.toUpperCase()}</span><br />
                  Total Paid / Payable: <strong>₹{parseFloat(confirmedOrder.total_amount).toLocaleString("en-IN")}</strong>
                </p>
              </div>
            </div>

            {/* Actions */}
            <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setActiveView("catalog");
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              >
                Continue Shopping
              </button>

              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  setActiveView("my-orders");
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              >
                <Package size={16} />
                <span>View in Order History</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          VIEW 5: CUSTOMER ORDER HISTORY (My Orders - Requirement 13)
          ===================================================================== */}
      {activeView === "my-orders" && (
        <div className="my-orders-page">
          <nav className="pdp-breadcrumb">
            <button type="button" onClick={() => setActiveView("catalog")}>
              Collections
            </button>
            <span className="pdp-breadcrumb-sep">/</span>
            <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>My Order History</span>
          </nav>

          <div className="my-orders-header">
            <div>
              <h2 style={{ fontFamily: "var(--font-serif)", fontSize: "1.75rem" }}>My Garment Orders</h2>
              <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                Real-time tracking of orders placed with Bagodi Bidar Atelier.
              </p>
            </div>

            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={loadCustomerOrders}
              disabled={isLoadingOrders}
            >
              <Sparkles size={14} />
              <span>Refresh Orders</span>
            </button>
          </div>

          {isLoadingOrders ? (
            <div className="storefront-loading">
              <Sparkles size={24} className="animate-spin" />
              <p>Loading your orders from PostgreSQL database...</p>
            </div>
          ) : customerOrders.length === 0 ? (
            <div className="storefront-empty-state">
              <div className="empty-icon-circle">
                <Package size={32} />
              </div>
              <h3>No Past Orders Found</h3>
              <p>
                You haven't placed any orders yet. Discover our latest handwoven silks and sherwanis in the boutique.
              </p>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setActiveView("catalog")}
              >
                Browse Catalog
              </button>
            </div>
          ) : (
            <div className="orders-list-wrap">
              {customerOrders.map((ord) => {
                const isConfirmed = ord.status === "CONFIRMED";
                const isProcessing = ord.status === "PROCESSING";
                const isDispatched = ord.status === "DISPATCHED";
                const isDelivered = ord.status === "DELIVERED";

                return (
                  <div key={ord.id} className="order-history-card">
                    <div className="order-card-header">
                      <div>
                        <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", display: "block" }}>
                          ORDER NUMBER
                        </span>
                        <strong style={{ fontFamily: "monospace", fontSize: "0.95rem" }}>{ord.order_number}</strong>
                      </div>

                      <div>
                        <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", display: "block" }}>
                          DATE PLACED
                        </span>
                        <span>{new Date(ord.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</span>
                      </div>

                      <div>
                        <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", display: "block" }}>
                          TOTAL AMOUNT
                        </span>
                        <strong style={{ color: "var(--brand-terracotta)" }}>
                          ₹{parseFloat(ord.total_amount).toLocaleString("en-IN")}
                        </strong>
                      </div>

                      <div>
                        <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", display: "block" }}>
                          STATUS
                        </span>
                        <span
                          className="status-pill"
                          style={{
                            background: isDelivered ? "var(--status-success-bg)" : "var(--brand-terracotta-light)",
                            color: isDelivered ? "var(--status-success)" : "var(--brand-terracotta)",
                            fontWeight: 700,
                            padding: "0.2rem 0.6rem",
                            borderRadius: "var(--radius-xs)",
                            fontSize: "0.78rem",
                          }}
                        >
                          {ord.status}
                        </span>
                      </div>
                    </div>

                    <div className="order-card-body">
                      {/* Tracking Stepper */}
                      <div className="order-tracking-stepper" style={{ margin: "1rem 0 1.5rem" }}>
                        <div className={`stepper-step ${isConfirmed || isProcessing || isDispatched || isDelivered ? "completed" : ""}`}>
                          <div className="stepper-dot">✓</div>
                          <span className="stepper-label">Confirmed</span>
                        </div>
                        <div className={`stepper-step ${isProcessing || isDispatched || isDelivered ? "completed" : isConfirmed ? "active" : ""}`}>
                          <div className="stepper-dot">2</div>
                          <span className="stepper-label">Packing</span>
                        </div>
                        <div className={`stepper-step ${isDispatched || isDelivered ? "completed" : isProcessing ? "active" : ""}`}>
                          <div className="stepper-dot">3</div>
                          <span className="stepper-label">Dispatched</span>
                        </div>
                        <div className={`stepper-step ${isDelivered ? "completed" : isDispatched ? "active" : ""}`}>
                          <div className="stepper-dot">4</div>
                          <span className="stepper-label">Delivered</span>
                        </div>
                      </div>

                      {/* Items */}
                      <div className="cart-items-list">
                        {ord.items?.map((item: any) => (
                          <div key={item.id} className="cart-item-row" style={{ padding: "0.6rem 0" }}>
                            <div>
                              <strong>{item.product_name}</strong>
                              <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", display: "block" }}>
                                SKU: {item.sku} • Qty: {item.quantity}
                              </span>
                            </div>
                            <span style={{ fontWeight: 700 }}>
                              ₹{parseFloat(item.total_price || item.unit_price).toLocaleString("en-IN")}
                            </span>
                          </div>
                        ))}
                      </div>

                      <div style={{ marginTop: "1rem", paddingTop: "0.75rem", borderTop: "1px solid var(--border-light)", fontSize: "0.8rem", color: "var(--text-muted)", display: "flex", justifyContent: "space-between" }}>
                        <span>Payment: <strong style={{ textTransform: "uppercase" }}>{ord.payment_method}</strong> ({ord.payment_status})</span>
                        <span>Deliver to: {ord.shipping_address?.city}, {ord.shipping_address?.postal_code}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* =====================================================================
          CUSTOMER AUTH MODAL
          ===================================================================== */}
      {isAuthModalOpen && (
        <div className="modal-overlay" onClick={() => setIsAuthModalOpen(false)}>
          <div className="modal-card modal-auth-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Customer Retail Access</h3>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setIsAuthModalOpen(false)}
              >
                <X size={16} />
              </button>
            </div>

            <div className="modal-body">
              {authError && (
                <div className="auth-error-banner">
                  {authError}
                </div>
              )}

              {/* Tab Selector */}
              <div className="auth-tab-row">
                <button
                  type="button"
                  className={`auth-tab-btn ${authTab === "login" ? "active" : ""}`}
                  onClick={() => {
                    setAuthTab("login");
                    setAuthError(null);
                  }}
                >
                  Sign In
                </button>
                <button
                  type="button"
                  className={`auth-tab-btn ${authTab === "register" ? "active" : ""}`}
                  onClick={() => {
                    setAuthTab("register");
                    setAuthError(null);
                  }}
                >
                  Create Account
                </button>
              </div>

              {authTab === "login" ? (
                <form onSubmit={handleLoginSubmit}>
                  <div className="form-group" style={{ marginBottom: "1rem" }}>
                    <label className="form-label">Email Address or Phone</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="customer@bagodi.in"
                      value={authIdentifier}
                      onChange={(e) => setAuthIdentifier(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group" style={{ marginBottom: "1.25rem" }}>
                    <label className="form-label">Account Password</label>
                    <input
                      type="password"
                      className="form-input"
                      placeholder="••••••••"
                      value={authPassword}
                      onChange={(e) => setAuthPassword(e.target.value)}
                      required
                    />
                  </div>

                  <button
                    type="submit"
                    className="btn btn-primary btn-full"
                    disabled={authLoading}
                  >
                    <span>{authLoading ? "Authenticating..." : "Sign In to Account"}</span>
                    <ArrowRight size={16} />
                  </button>
                </form>
              ) : (
                <form onSubmit={handleRegisterSubmit}>
                  <div className="form-group" style={{ marginBottom: "0.75rem" }}>
                    <label className="form-label">Full Name *</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Ramesh Patil"
                      value={regName}
                      onChange={(e) => setRegName(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group" style={{ marginBottom: "0.75rem" }}>
                    <label className="form-label">Email Address *</label>
                    <input
                      type="email"
                      className="form-input"
                      placeholder="ramesh@gmail.com"
                      value={regEmail}
                      onChange={(e) => setRegEmail(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group" style={{ marginBottom: "0.75rem" }}>
                    <label className="form-label">Mobile Number</label>
                    <input
                      type="tel"
                      className="form-input"
                      placeholder="98765 00001"
                      value={regPhone}
                      onChange={(e) => setRegPhone(e.target.value)}
                    />
                  </div>

                  <div className="form-group" style={{ marginBottom: "1.25rem" }}>
                    <label className="form-label">Create Password *</label>
                    <input
                      type="password"
                      className="form-input"
                      placeholder="Minimum 6 characters"
                      value={regPassword}
                      onChange={(e) => setRegPassword(e.target.value)}
                      required
                      minLength={6}
                    />
                  </div>

                  <button
                    type="submit"
                    className="btn btn-primary btn-full"
                    disabled={authLoading}
                  >
                    <span>{authLoading ? "Creating Account..." : "Complete Registration"}</span>
                    <ArrowRight size={16} />
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          CART DRAWER
          ===================================================================== */}
      {isCartOpen && (
        <div className="cart-drawer-overlay" onClick={() => setIsCartOpen(false)}>
          <aside className="cart-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="cart-drawer-header">
              <h3>Shopping Bag ({cartItemsCount})</h3>
              <button type="button" className="btn-close" onClick={() => setIsCartOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <div className="cart-drawer-body">
              {cart.length === 0 ? (
                <div className="cart-empty">
                  <ShoppingBag size={40} color="var(--text-muted)" />
                  <p>Your shopping bag is currently empty.</p>
                </div>
              ) : (
                <div className="cart-items-list">
                  {cart.map((item) => (
                    <div key={item.id} className="cart-item-row">
                      <div className="cart-item-info">
                        <span className="cart-item-name">{item.name}</span>
                        <span className="cart-item-meta">
                          Size: {item.size} • Color: {item.color}
                        </span>
                        <span className="cart-item-price">
                          ₹{item.price.toLocaleString("en-IN")}
                        </span>
                      </div>

                      <div className="cart-item-qty">
                        <button
                          type="button"
                          onClick={() => {
                            if (item.quantity <= 1) {
                              setCart((prev) => prev.filter((i) => i.id !== item.id));
                            } else {
                              setCart((prev) =>
                                prev.map((i) => (i.id === item.id ? { ...i, quantity: i.quantity - 1 } : i))
                              );
                            }
                          }}
                        >
                          <Minus size={12} />
                        </button>
                        <span>{item.quantity}</span>
                        <button
                          type="button"
                          disabled={item.quantity >= item.available_qty}
                          onClick={() =>
                            setCart((prev) =>
                              prev.map((i) => (i.id === item.id ? { ...i, quantity: i.quantity + 1 } : i))
                            )
                          }
                        >
                          <Plus size={12} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {cart.length > 0 && (
              <div className="cart-drawer-footer">
                <div className="cart-total-row">
                  <span>Subtotal Amount:</span>
                  <span className="total-amount">₹{cartTotal.toLocaleString("en-IN")}</span>
                </div>

                <button
                  type="button"
                  className="btn btn-primary btn-full"
                  onClick={handleProceedFromCart}
                >
                  <span>Proceed to Secure Checkout</span>
                  <ArrowRight size={16} />
                </button>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
};
