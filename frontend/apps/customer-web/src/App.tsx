import { useState, useEffect, useMemo } from "react";
import { client, getUser, subscribeAuth, type AuthUser, type paths } from "@bagodi/api-client";
import { Header } from "./components/Header.js";
import { CategoryNav } from "./components/CategoryNav.js";
import { ProductCard } from "./components/ProductCard.js";
import { ProductDetailModal } from "./components/ProductDetailModal.js";
import { AuthModal } from "./components/AuthModal.js";
import { EmptyState } from "./components/EmptyState.js";
import { Sparkles } from "lucide-react";
import "./styles.css";

type CategoryItem = paths["/api/v1/catalog/categories"]["get"]["responses"][200]["content"]["application/json"][number];
type ProductSummary = paths["/api/v1/catalog/products"]["get"]["responses"][200]["content"]["application/json"][number];

interface CartLine {
  variantId: string;
  productId: string;
  title: string;
  quantity: number;
  price: number;
}

export default function App() {
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(() => getUser());
  const [authModalOpen, setAuthModalOpen] = useState(false);

  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(null);
  const [loadingCategories, setLoadingCategories] = useState(true);

  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedProductForModal, setSelectedProductForModal] = useState<ProductSummary | null>(null);

  const [cart, setCart] = useState<CartLine[]>([]);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Sync auth state
  useEffect(() => {
    const unsubscribe = subscribeAuth((_, user) => {
      setCurrentUser(user);
    });
    return unsubscribe;
  }, []);

  // Fetch categories
  useEffect(() => {
    let isMounted = true;
    async function loadCategories() {
      setLoadingCategories(true);
      try {
        const { data } = await client.GET("/api/v1/catalog/categories", {});
        if (isMounted && data) {
          setCategories(data);
        }
      } catch (err) {
        console.error("Failed to load categories:", err);
      } finally {
        if (isMounted) setLoadingCategories(false);
      }
    }
    loadCategories();
    return () => {
      isMounted = false;
    };
  }, []);

  // Fetch products
  useEffect(() => {
    let isMounted = true;
    async function loadProducts() {
      setLoadingProducts(true);
      try {
        const queryParams: Record<string, string | number> = { limit: 50 };
        if (selectedCategoryId) {
          queryParams.category_id = selectedCategoryId;
        }

        const { data } = await client.GET("/api/v1/catalog/products", {
          params: { query: queryParams },
        });

        if (isMounted && data) {
          setProducts(data);
        }
      } catch (err) {
        console.error("Failed to load products:", err);
      } finally {
        if (isMounted) setLoadingProducts(false);
      }
    }
    loadProducts();
    return () => {
      isMounted = false;
    };
  }, [selectedCategoryId]);

  // Filter products by search query
  const filteredProducts = useMemo(() => {
    if (!searchQuery.trim()) return products;
    const q = searchQuery.toLowerCase().trim();
    return products.filter((p) => {
      const matchName = p.name.toLowerCase().includes(q);
      const matchDesc = p.description?.toLowerCase().includes(q);
      const matchVariant = p.variants?.some(
        (v) =>
          v.sku.toLowerCase().includes(q) ||
          v.name.toLowerCase().includes(q) ||
          (v.attributes && Object.values(v.attributes).some((val) => String(val).toLowerCase().includes(q)))
      );
      return matchName || matchDesc || matchVariant;
    });
  }, [products, searchQuery]);

  // Cart operations
  const handleAddToCart = (product: ProductSummary, variantId: string, quantity = 1) => {
    const variant = product.variants?.find((v) => v.id === variantId) || product.variants?.[0];
    const unitPrice = variant ? parseFloat(variant.base_price) : 0;

    setCart((prev) => {
      const existing = prev.find((item) => item.variantId === variantId);
      if (existing) {
        return prev.map((item) =>
          item.variantId === variantId ? { ...item, quantity: item.quantity + quantity } : item
        );
      }
      return [
        ...prev,
        {
          variantId,
          productId: product.id,
          title: product.name,
          quantity,
          price: unitPrice,
        },
      ];
    });

    setToastMessage(`Added ${product.name} (${quantity}) to cart`);
    setTimeout(() => setToastMessage(null), 2500);
  };

  const totalCartCount = useMemo(() => {
    return cart.reduce((sum, item) => sum + item.quantity, 0);
  }, [cart]);

  return (
    <div className="app-container">
      {/* Toast Notice */}
      {toastMessage && (
        <div
          style={{
            position: "fixed",
            bottom: "24px",
            right: "24px",
            zIndex: 999,
            background: "var(--color-botanical)",
            color: "#FFFFFF",
            padding: "12px 20px",
            borderRadius: "var(--radius-full)",
            boxShadow: "var(--shadow-lg)",
            fontSize: "0.875rem",
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: "8px",
            animation: "slideUp 180ms ease-out",
          }}
        >
          <Sparkles size={16} />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Main Header */}
      <Header
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        cartCount={totalCartCount}
        currentUser={currentUser}
        onOpenAuth={() => setAuthModalOpen(true)}
        onOpenCart={() => setAuthModalOpen(true)}
      />

      {/* Category Navigation Bar */}
      <CategoryNav
        categories={categories}
        selectedCategoryId={selectedCategoryId}
        onSelectCategory={setSelectedCategoryId}
        loading={loadingCategories}
      />

      {/* Hero Showcase */}
      <section className="hero-banner">
        <div className="hero-card">
          <div className="hero-tag">
            <span>Bidar Express Storefront</span>
          </div>
          <h1 className="hero-title">
            Freshness, groceries & essentials delivered to your doorstep.
          </h1>
          <p className="hero-subtitle">
            Authentic retail experience with live double-entry inventory and express 2-hour doorstep fulfillment in Bidar, Karnataka.
          </p>
        </div>
      </section>

      {/* Main Catalogue Section */}
      <main className="content-section">
        <div className="section-header">
          <h2 className="section-title">
            {selectedCategoryId
              ? categories.find((c) => c.id === selectedCategoryId)?.name || "Category Items"
              : searchQuery
              ? `Results for "${searchQuery}"`
              : "All Available Products"}
          </h2>
          <span className="section-count">
            {loadingProducts ? "Loading..." : `${filteredProducts.length} items`}
          </span>
        </div>

        {loadingProducts ? (
          <div className="product-grid">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="skeleton skeleton-card" />
            ))}
          </div>
        ) : filteredProducts.length === 0 ? (
          <EmptyState
            isSearch={Boolean(searchQuery)}
            isCategoryFilter={Boolean(selectedCategoryId)}
            searchQuery={searchQuery}
            onReset={() => {
              setSearchQuery("");
              setSelectedCategoryId(null);
            }}
          />
        ) : (
          <div className="product-grid">
            {filteredProducts.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                onClick={setSelectedProductForModal}
                onAddToCart={(p, vId) => handleAddToCart(p, vId, 1)}
              />
            ))}
          </div>
        )}
      </main>

      {/* Product Detail Modal */}
      <ProductDetailModal
        product={selectedProductForModal}
        onClose={() => setSelectedProductForModal(null)}
        onAddToCart={handleAddToCart}
      />

      {/* Auth Modal (Phone OTP & Profile) */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        currentUser={currentUser}
        onAuthSuccess={(user) => {
          setCurrentUser(user);
        }}
        onLogout={() => {
          setCurrentUser(null);
          setCart([]);
        }}
      />
    </div>
  );
}
