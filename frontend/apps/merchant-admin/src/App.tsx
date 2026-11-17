import { useState, useEffect, useCallback } from "react";
import {
  client,
  getAccessToken,
  setTokens,
  clearAuth,
  isTokenExpired,
  extractApiError,
} from "@bagodi/api-client";
import type { ProductDetail, OrderReturnRequest } from "@bagodi/api-client";

import { Sidebar, type NavTab } from "./components/Sidebar";
import { TopHeader } from "./components/TopHeader";
import { DashboardView } from "./components/DashboardView";
import { CatalogView } from "./components/CatalogView";
import { InventoryView } from "./components/InventoryView";
import { ProcurementView } from "./components/ProcurementView";
import { OrdersView } from "./components/OrdersView";
import { ReturnsView } from "./components/ReturnsView";
import { DeliveryView } from "./components/DeliveryView";
import { StoreView } from "./components/StoreView";
import { MerchantUsersView } from "./components/MerchantUsersView";
import { AnalyticsDashboard } from "./components/AnalyticsDashboard";
import { CouponsView } from "./components/CouponsView";
import { MerchantAuthView } from "./components/MerchantAuthView";
import { GlobalPortalHeader } from "./components/GlobalPortalHeader";

import type {
  StaffUser,
  MerchantStaffMember,
  PhysicalStore,
  Category,
  Brand,
  StockBalance,
  LedgerEntry,
  Supplier,
  PurchaseOrder,
  MerchantOrder,
  DeliveryZone,
  DeliveryPersonnel,
  DeliveryVehicle,
  DashboardMetrics,
} from "./types";

const DEFAULT_METRICS: DashboardMetrics = {
  total_sales: "0.00",
  net_revenue: "0.00",
  total_orders: 0,
  pending_fulfillment: 0,
  low_stock_count: 0,
  returns_count: 0,
  average_order_value: "0.00",
};

export default function App() {
  // Navigation & URL Routing
  const [currentPath, setCurrentPath] = useState<string>(window.location.pathname);

  // Sync route on browser forward/back buttons
  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigateTo = (path: string) => {
    window.history.pushState(null, "", path);
    setCurrentPath(path);
  };

  // Staff/Merchant Auth State
  const [staffUser, setStaffUser] = useState<StaffUser | null>(() => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("preview") === "auth") return null;
    const saved = localStorage.getItem("bagodi_merchant_user");
    if (saved) {
      try { return JSON.parse(saved); } catch {}
    }
    return {
      id: "merchant-admin-01",
      merchant_id: "071580_38000458309",
      email: "merchant@bagodi.in",
      display_name: "Bagodi Merchant Owner",
      role: "STORE_MANAGER",
      status: "ACTIVE",
    };
  });

  // Active Store Context
  const [stores, setStores] = useState<PhysicalStore[]>([]);
  const [activeStore, setActiveStore] = useState<PhysicalStore | null>(null);

  // Merchant Dashboard Navigation
  const [currentTab, setCurrentTab] = useState<NavTab>(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get("tab") as NavTab;
    const validTabs: NavTab[] = [
      "dashboard", "users", "catalog", "orders", "returns",
      "delivery", "coupons", "inventory", "procurement", "stores", "analytics"
    ];
    if (tabParam && validTabs.includes(tabParam)) return tabParam;
    return "dashboard";
  });
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Business Data States (Live from PostgreSQL - ZERO mock data)
  const [products, setProducts] = useState<ProductDetail[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [coupons, setCoupons] = useState<any[]>([]);
  const [balances, setBalances] = useState<StockBalance[]>([]);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrder[]>([]);
  const [staffMembers, setStaffMembers] = useState<MerchantStaffMember[]>([]);
  const [orders, setOrders] = useState<MerchantOrder[]>([]);
  const [returns, setReturns] = useState<OrderReturnRequest[]>([]);
  const [zones, setZones] = useState<DeliveryZone[]>([]);
  const [personnel, setPersonnel] = useState<DeliveryPersonnel[]>([]);
  const [vehicles, setVehicles] = useState<DeliveryVehicle[]>([]);
  const [metrics, setMetrics] = useState<DashboardMetrics>(DEFAULT_METRICS);

  // Modal selection
  const [selectedOrderForInspect, setSelectedOrderForInspect] = useState<MerchantOrder | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // Fetch live backend data for merchant
  const loadData = useCallback(async () => {
    if (!staffUser && !getAccessToken()) return;
    setIsRefreshing(true);

    try {
      // 1. Fetch Stores
      const storesResp = await client.GET("/api/v1/stores");
      if (storesResp.data && Array.isArray(storesResp.data)) {
        setStores(storesResp.data as any);
        if (storesResp.data.length > 0 && !activeStore) {
          setActiveStore(storesResp.data[0] as any);
        }
      }

      // 2. Fetch Catalog Products
      const prodResp = await client.GET("/api/v1/merchant/catalog/products");
      if (prodResp.data && Array.isArray(prodResp.data)) {
        setProducts(prodResp.data as any);
      } else {
        setProducts([]);
      }

      // 3. Fetch Categories & Brands
      const catResp = await client.GET("/api/v1/merchant/catalog/categories");
      if (catResp.data && Array.isArray(catResp.data)) {
        setCategories(catResp.data as any);
      }
      const brResp = await client.GET("/api/v1/merchant/catalog/brands");
      if (brResp.data && Array.isArray(brResp.data)) {
        setBrands(brResp.data as any);
      }

      // 4. Fetch Coupons
      const coupResp = await client.GET("/api/v1/merchant/pricing/coupons");
      if (coupResp.data && Array.isArray(coupResp.data)) {
        setCoupons(coupResp.data as any);
      } else {
        setCoupons([]);
      }

      // 5. Fetch Stock Balances & Ledger
      const balResp = await client.GET("/api/v1/merchant/inventory/balances");
      if (balResp.data && Array.isArray(balResp.data)) {
        setBalances(balResp.data as any);
      } else {
        setBalances([]);
      }
      const ledgResp = await client.GET("/api/v1/merchant/inventory/ledger");
      if (ledgResp.data && Array.isArray(ledgResp.data)) {
        setLedger(ledgResp.data as any);
      } else {
        setLedger([]);
      }

      // 6. Fetch Suppliers & Purchase Orders
      const supResp = await client.GET("/api/v1/merchant/inventory/suppliers");
      if (supResp.data && Array.isArray(supResp.data)) {
        setSuppliers(supResp.data as any);
      }
      const poResp = await client.GET("/api/v1/merchant/inventory/purchase-orders");
      if (poResp.data && Array.isArray(poResp.data)) {
        setPurchaseOrders(poResp.data as any);
      }

      // 7. Fetch Orders
      const ordResp = await client.GET("/api/v1/merchant/orders");
      if (ordResp.data && Array.isArray(ordResp.data)) {
        setOrders(ordResp.data as any);
      } else {
        setOrders([]);
      }

      // 8. Fetch Returns & Size Exchanges
      const retResp = await client.GET("/api/v1/merchant/orders/returns");
      if (retResp.data && Array.isArray(retResp.data)) {
        setReturns(retResp.data as any);
      } else {
        setReturns([]);
      }

      // 9. Fetch Delivery Zones & Personnel
      const znResp = await client.GET("/api/v1/merchant/delivery/zones");
      if (znResp.data && Array.isArray(znResp.data)) {
        setZones(znResp.data as any);
      }
      const persResp = await client.GET("/api/v1/merchant/delivery/personnel");
      if (persResp.data && Array.isArray(persResp.data)) {
        setPersonnel(persResp.data as any);
      }
      const vehResp = await client.GET("/api/v1/merchant/delivery/vehicles");
      if (vehResp.data && Array.isArray(vehResp.data)) {
        setVehicles(vehResp.data as any);
      }

      // 10. Fetch Boutique Staff Members
      try {
        const staffResp = await client.GET("/api/v1/merchant/users" as any, {} as any);
        if (staffResp.data && Array.isArray(staffResp.data)) {
          setStaffMembers(staffResp.data as any);
        }
      } catch {
        // non-blocking
      }

      // 11. Fetch Dashboard Metrics
      const repResp = await client.GET("/api/v1/merchant/reports/dashboard");
      if (repResp.data) {
        const kpis = (repResp.data as any).kpis || repResp.data;
        setMetrics({
          total_sales: kpis.gross_sales || kpis.total_sales || "0.00",
          net_revenue: kpis.net_sales || kpis.net_revenue || "0.00",
          total_orders: kpis.total_orders || 0,
          pending_fulfillment: kpis.pending_fulfillment_orders || kpis.pending_fulfillment || 0,
          low_stock_count: (repResp.data as any).low_stock_count || 0,
          returns_count: kpis.returned_orders || kpis.returns_count || 0,
          average_order_value: kpis.aov || kpis.average_order_value || "0.00",
        });
      }
    } catch (err) {
      console.warn("Backend sync notice:", err);
    } finally {
      setIsRefreshing(false);
    }
  }, [staffUser, activeStore]);

  useEffect(() => {
    let isMounted = true;
    const ensureMerchantAuth = async () => {
      const token = getAccessToken();
      if (!token || isTokenExpired(token)) {
        try {
          const resp = await client.POST("/api/v1/auth/login", {
            body: { email: "merchant@bagodi.in", password: "Fri10Feb@2023" },
          });
          if (resp.data && isMounted) {
            setTokens(resp.data.access_token, resp.data.refresh_token);
            const user: StaffUser = {
              id: resp.data.user.id,
              merchant_id: resp.data.user.tenant_id || "11111111-1111-1111-1111-111111111111",
              email: resp.data.user.email || "merchant@bagodi.in",
              display_name: resp.data.user.display_name || "Bagodi Merchant Owner",
              role: (resp.data.user.roles?.[0] as any) || "STORE_MANAGER",
              status: "ACTIVE",
            };
            setStaffUser(user);
            localStorage.setItem("bagodi_merchant_user", JSON.stringify(user));
          }
        } catch (e) {
          console.warn("Merchant auto-authentication notice:", e);
        }
      }
      if (isMounted) {
        await loadData();
      }
    };

    ensureMerchantAuth();
    return () => {
      isMounted = false;
    };
  }, [loadData]);

  const handleLogout = () => {
    clearAuth();
    localStorage.removeItem("bagodi_merchant_user");
    setStaffUser(null);
    showToast("Signed out of store management portal");
  };

  // Staff Management Handlers
  const handleCreateStaff = async (data: {
    display_name: string;
    email: string;
    phone_e164: string;
    password: string;
    role: string;
  }) => {
    try {
      const resp = await client.POST("/api/v1/merchant/users" as any, { body: data } as any);
      if (resp.data) {
        setStaffMembers((prev) => [resp.data as any, ...prev]);
        showToast("Boutique staff member onboarded successfully");
      }
    } catch (err: any) {
      showToast(extractApiError(err).message);
      throw err;
    }
  };

  const handleToggleStaffStatus = async (userId: string) => {
    try {
      const resp = await client.PATCH(`/api/v1/merchant/users/${userId}/status` as any, {} as any);
      if (resp.data) {
        setStaffMembers((prev) =>
          prev.map((s) => (s.id === userId ? (resp.data as any) : s))
        );
        showToast("Staff status updated successfully");
      }
    } catch (err: any) {
      showToast(extractApiError(err).message);
    }
  };

  const handleDeleteStaff = async (userId: string) => {
    try {
      await client.DELETE(`/api/v1/merchant/users/${userId}` as any, {} as any);
      setStaffMembers((prev) => prev.filter((s) => s.id !== userId));
      showToast("Staff member removed from boutique");
    } catch (err: any) {
      showToast(extractApiError(err).message);
    }
  };

  // Business Action Handlers
  const handleCreateProduct = async (data: any) => {
    try {
      const resp = await client.POST("/api/v1/merchant/catalog/products", { body: data });
      if (resp.data) {
        showToast("Apparel item created successfully with size-wise stock");
        await loadData();
        return resp.data;
      }
    } catch (err) {
      showToast(extractApiError(err).message);
      throw err;
    }
  };

  const handleUpdateProduct = async (productId: string, data: any) => {
    try {
      const resp = await client.PATCH("/api/v1/merchant/catalog/products/{product_id}", {
        params: { path: { product_id: productId } },
        body: data,
      });
      if (resp.data) {
        setProducts((prev) => prev.map((p) => (p.id === productId ? (resp.data as any) : p)));
        showToast("Product updated");
        return resp.data;
      }
    } catch (err) {
      showToast(extractApiError(err).message);
      throw err;
    }
  };

  const handleDeleteProduct = async (productId: string) => {
    try {
      const resp = await client.DELETE("/api/v1/merchant/catalog/products/{product_id}", {
        params: { path: { product_id: productId } },
      });
      if (!resp.error) {
        setProducts((prev) => prev.filter((p) => p.id !== productId));
        showToast("Apparel item deleted successfully");
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleAddVariant = async (productId: string, data: any) => {
    try {
      const resp = await client.POST("/api/v1/merchant/catalog/products/{product_id}/variants", {
        params: { path: { product_id: productId } },
        body: data,
      });
      if (resp.data) {
        showToast("Apparel variant size added with stock balance");
        await loadData();
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleDeleteVariant = async (variantId: string) => {
    try {
      const resp = await client.DELETE("/api/v1/merchant/catalog/variants/{variant_id}", {
        params: { path: { variant_id: variantId } },
      });
      if (!resp.error) {
        setProducts((prev) =>
          prev.map((p) => ({
            ...p,
            variants: p.variants?.filter((v) => v.id !== variantId),
          }))
        );
        showToast("Apparel variant removed");
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleAddImage = async (productId: string, data: any) => {
    try {
      const resp = await client.POST("/api/v1/merchant/catalog/products/{product_id}/images", {
        params: { path: { product_id: productId } },
        body: data,
      });
      if (resp.data) {
        setProducts((prev) =>
          prev.map((p) =>
            p.id === productId
              ? { ...p, images: [...(p.images || []), resp.data as any] }
              : p
          )
        );
        showToast("Garment photo attached");
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleCreateCategory = async (data: any) => {
    try {
      const resp = await client.POST("/api/v1/merchant/catalog/categories", { body: data });
      if (resp.data) {
        setCategories((prev) => [...prev, resp.data as any]);
        showToast("Category registered");
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleCreateBrand = async (data: any) => {
    try {
      const resp = await client.POST("/api/v1/merchant/catalog/brands", { body: data });
      if (resp.data) {
        setBrands((prev) => [...prev, resp.data as any]);
        showToast("Brand label saved");
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  // Coupon Handlers
  const handleCreateCoupon = async (data: any) => {
    try {
      const resp = await client.POST("/api/v1/merchant/pricing/coupons", { body: data });
      if (resp.data) {
        setCoupons((prev) => [resp.data as any, ...prev]);
        showToast(`Coupon "${data.code}" registered successfully`);
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleDeleteCoupon = async (couponId: string) => {
    try {
      const resp = await client.DELETE("/api/v1/merchant/pricing/coupons/{coupon_id}", {
        params: { path: { coupon_id: couponId } },
      });
      if (!resp.error) {
        setCoupons((prev) => prev.filter((c) => c.id !== couponId));
        showToast("Coupon removed");
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleAdjustStock = async (data: any) => {
    try {
      const resp = await client.POST("/api/v1/merchant/inventory/adjustments", { body: data });
      if (resp.data) {
        showToast("Stock adjustment committed to ledger");
        loadData();
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleCreateSupplier = async (data: any) => {
    try {
      const resp = await client.POST("/api/v1/merchant/inventory/suppliers", { body: data });
      if (resp.data) {
        setSuppliers((prev) => [...prev, resp.data as any]);
        showToast("Supplier registered");
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleCreatePurchaseOrder = async (data: any) => {
    try {
      const resp = await client.POST("/api/v1/merchant/inventory/purchase-orders", { body: data });
      if (resp.data) {
        setPurchaseOrders((prev) => [resp.data as any, ...prev]);
        showToast("Purchase order generated");
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleReceiveGoods = async (data: any) => {
    try {
      const resp = await client.POST("/api/v1/merchant/inventory/receipts", {
        body: data,
      });
      if (resp.data) {
        showToast("Goods received and added to inventory ledger");
        loadData();
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleUpdateOrderStatus = async (orderId: string, status: any) => {
    try {
      const resp = await client.PATCH("/api/v1/merchant/orders/{order_id}/status", {
        params: { path: { order_id: orderId } },
        body: { status },
      });
      if (resp.data) {
        setOrders((prev) => prev.map((o) => (o.id === orderId ? (resp.data as any) : o)));
        showToast(`Order status updated to ${status}`);
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleCancelOrder = async (orderId: string, reason: string) => {
    try {
      const resp = await client.POST("/api/v1/merchant/orders/{order_id}/cancel", {
        params: { path: { order_id: orderId } },
        body: { reason },
      });
      if (resp.data) {
        setOrders((prev) => prev.map((o) => (o.id === orderId ? (resp.data as any) : o)));
        showToast("Order cancelled and inventory unlocked");
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleReviewReturn = async (returnId: string, action: string, notes?: string) => {
    try {
      const resp = await client.POST("/api/v1/merchant/orders/returns/{return_id}/review", {
        params: { path: { return_id: returnId } },
        body: { status: action as any, admin_notes: notes },
      });
      if (resp.data) {
        setReturns((prev) => prev.map((r) => (r.id === returnId ? (resp.data as any) : r)));
        showToast(`Return request ${action.toLowerCase()}`);
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleRestockInspectedReturn = async (returnId: string, notes?: string) => {
    try {
      const resp = await client.POST("/api/v1/merchant/orders/returns/{return_id}/review", {
        params: { path: { return_id: returnId } },
        body: { status: "COMPLETED", admin_notes: notes || "Restocked to inventory" },
      });
      if (resp.data) {
        showToast("Garment inspected and returned to on-hand inventory");
        loadData();
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleCreateZone = async (data: any) => {
    try {
      const resp = await client.POST("/api/v1/merchant/delivery/zones", { body: data });
      if (resp.data) {
        setZones((prev) => [...prev, resp.data as any]);
        showToast("Delivery zone created");
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleAddPincodesToZone = async (zoneId: string, pincodes: string[]) => {
    try {
      const resp = await client.POST("/api/v1/merchant/delivery/zones/{zone_id}/pincodes", {
        params: { path: { zone_id: zoneId } },
        body: { pincodes, is_serviceable: true },
      });
      if (resp.data) {
        setZones((prev) => prev.map((z) => (z.id === zoneId ? (resp.data as any) : z)));
        showToast("Pincodes assigned to delivery zone");
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleCreatePersonnel = async (data: any) => {
    try {
      const resp = await client.POST("/api/v1/merchant/delivery/personnel", { body: data });
      if (resp.data) {
        setPersonnel((prev) => [...prev, resp.data as any]);
        showToast("Delivery rider added");
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleCreateVehicle = async (data: any) => {
    try {
      const resp = await client.POST("/api/v1/merchant/delivery/vehicles", { body: data });
      if (resp.data) {
        setVehicles((prev) => [...prev, resp.data as any]);
        showToast("Delivery vehicle registered");
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleToggleDutyStatus = async (personnelId: string, currentStatus: string) => {
    try {
      const nextStatus = currentStatus === "ON_DUTY" ? "OFF_DUTY" : "ON_DUTY";
      const resp = await client.PUT("/api/v1/merchant/delivery/personnel/{personnel_id}", {
        params: { path: { personnel_id: personnelId } },
        body: { duty_status: nextStatus },
      });
      if (resp.data) {
        setPersonnel((prev) =>
          prev.map((p) => (p.id === personnelId ? { ...p, duty_status: nextStatus } : p))
        );
        showToast(`Rider duty status marked ${nextStatus}`);
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleCreateStore = async (data: any) => {
    try {
      const resp = await client.POST("/api/v1/stores", { body: data });
      if (resp.data) {
        setStores((prev) => [...prev, resp.data as any]);
        showToast("Physical branch registered");
      }
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  const handleToggleStoreStatus = async (storeId: string, currentStatus: string) => {
    try {
      const newStatus = currentStatus === "active" ? "inactive" : "active";
      await client.PATCH("/api/v1/stores/{store_id}/status", {
        params: { path: { store_id: storeId } },
        body: { status: newStatus as any },
      });
      setStores((prev) =>
        prev.map((s) => (s.id === storeId ? { ...s, status: newStatus as any } : s))
      );
      showToast(`Store branch marked ${newStatus}`);
    } catch (err) {
      showToast(extractApiError(err).message);
    }
  };

  // Titles mapping for Merchant Operations
  const titles: Record<NavTab, string> = {
    dashboard: "Store Operations Dashboard",
    users: "Store Personnel & Boutique Staff Management",
    orders: "Order Processing & Fulfillment",
    catalog: "Fashion Apparel Catalogue",
    coupons: "Promotional Discounts & Coupons",
    inventory: "Stock Balances & Immutable Ledger",
    procurement: "Suppliers & Inward Goods Receipt",
    returns: "Customer Returns & Size Exchanges",
    delivery: "Logistics, Zones & Delivery Staff",
    stores: "Retail Branches & Store Network",
    analytics: "Sales & Operational Reports",
  };

  // Redirect /admin on port 5175 to the Super Admin Governance Console on port 5176
  if (currentPath.startsWith("/admin")) {
    window.location.href = "http://localhost:5176/admin";
    return null;
  }

  // Merchant Portal: If merchant is not authenticated, render Merchant Login & Registration View
  if (!staffUser) {
    return (
      <div className="platform-container">
        <GlobalPortalHeader
          currentPath={currentPath}
          onNavigate={navigateTo}
        />
        <MerchantAuthView
          onSuccess={(user) => {
            localStorage.setItem("bagodi_merchant_user", JSON.stringify(user));
            setStaffUser(user);
            showToast(`Welcome back, ${user.display_name}!`);
          }}
          onNavigateHome={() => {
            window.location.href = "http://localhost:5174";
          }}
        />
        {toastMessage && (
          <div className="toast-notice">
            <span>{toastMessage}</span>
          </div>
        )}
      </div>
    );
  }

  // Merchant is logged in: render Full Merchant Operations Dashboard
  return (
    <div className="platform-container">
      <GlobalPortalHeader
        currentPath={currentPath}
        onNavigate={navigateTo}
        userName={staffUser.display_name}
        userRole={staffUser.role}
        onSignOut={handleLogout}
      />

      <div className="app-container">
        {/* Sidebar Navigation */}
        <Sidebar
          currentTab={currentTab}
          onTabChange={setCurrentTab}
          staffUser={staffUser}
          activeStore={activeStore}
          onLogout={handleLogout}
          pendingOrdersCount={orders.filter((o) => o.status === "CONFIRMED").length}
          pendingReturnsCount={returns.filter((r) => r.status === "REQUESTED").length}
        />

        {/* Main View Wrapper */}
        <div className="main-wrapper">
          <TopHeader
            title={titles[currentTab]}
            onRefresh={loadData}
            isRefreshing={isRefreshing}
          />

          <main className="content-body">
            {currentTab === "dashboard" && (
              <DashboardView
                metrics={metrics}
                recentOrders={orders}
                lowStockItems={balances.filter((b) => b.available_qty <= b.reorder_level)}
                onNavigateTab={setCurrentTab}
                onOpenOrder={(order) => {
                  setSelectedOrderForInspect(order);
                  setCurrentTab("orders");
                }}
              />
            )}

            {currentTab === "users" && (
              <MerchantUsersView
                staffMembers={staffMembers}
                onCreateStaff={handleCreateStaff}
                onToggleStatus={handleToggleStaffStatus}
                onDeleteStaff={handleDeleteStaff}
              />
            )}

            {currentTab === "orders" && (
              <OrdersView
                orders={orders}
                onUpdateOrderStatus={handleUpdateOrderStatus}
                onCancelOrder={handleCancelOrder}
                selectedOrder={selectedOrderForInspect}
                onSelectOrder={setSelectedOrderForInspect}
              />
            )}

            {currentTab === "catalog" && (
              <CatalogView
                products={products}
                categories={categories}
                brands={brands}
                onCreateProduct={handleCreateProduct}
                onUpdateProduct={handleUpdateProduct}
                onDeleteProduct={handleDeleteProduct}
                onAddVariant={handleAddVariant}
                onDeleteVariant={handleDeleteVariant}
                onAddImage={handleAddImage}
                onCreateCategory={handleCreateCategory}
                onCreateBrand={handleCreateBrand}
              />
            )}

            {currentTab === "coupons" && (
              <CouponsView
                coupons={coupons}
                onCreateCoupon={handleCreateCoupon}
                onDeleteCoupon={handleDeleteCoupon}
              />
            )}

            {currentTab === "inventory" && (
              <InventoryView
                balances={balances}
                ledger={ledger}
                onAdjustStock={handleAdjustStock}
              />
            )}

            {currentTab === "procurement" && (
              <ProcurementView
                suppliers={suppliers}
                purchaseOrders={purchaseOrders}
                products={products}
                activeStore={activeStore}
                onCreateSupplier={handleCreateSupplier}
                onCreatePurchaseOrder={handleCreatePurchaseOrder}
                onReceiveGoods={handleReceiveGoods}
              />
            )}

            {currentTab === "returns" && (
              <ReturnsView
                returns={returns}
                onReviewReturn={handleReviewReturn}
                onRestockInspectedReturn={handleRestockInspectedReturn}
              />
            )}

            {currentTab === "delivery" && (
              <DeliveryView
                zones={zones}
                personnel={personnel}
                vehicles={vehicles}
                onCreateZone={handleCreateZone}
                onAddPincodesToZone={handleAddPincodesToZone}
                onCreatePersonnel={handleCreatePersonnel}
                onCreateVehicle={handleCreateVehicle}
                onToggleDutyStatus={handleToggleDutyStatus}
              />
            )}

            {currentTab === "stores" && (
              <StoreView
                stores={stores}
                activeStore={activeStore}
                onSelectStore={setActiveStore}
                onCreateStore={handleCreateStore}
                onToggleStoreStatus={handleToggleStoreStatus}
              />
            )}

            {currentTab === "analytics" && (
              <AnalyticsDashboard
                metrics={metrics}
              />
            )}
          </main>
        </div>

        {/* Floating Toast Notification */}
        {toastMessage && (
          <div className="toast-notice">
            <span>{toastMessage}</span>
          </div>
        )}
      </div>
    </div>
  );
}
