/**
 * Authentication and Token Management Layer for Bagodi Platform.
 * Enforces secure RFC 6750 token storage, claims decoding, and lifecycle listeners.
 */

export interface AuthUser {
  id: string;
  phone?: string | null;
  phone_e164?: string | null;
  email?: string | null;
  display_name?: string | null;
  full_name?: string | null;
  role?: string;
  roles?: string[];
  tenant_id?: string | null;
}

const ACCESS_TOKEN_KEY = "bagodi_access_token";
const REFRESH_TOKEN_KEY = "bagodi_refresh_token";
const USER_KEY = "bagodi_user";
const TENANT_KEY = "bagodi_tenant_id";
const SESSION_ID_KEY = "bagodi_session_id";

type AuthListener = (isAuthenticated: boolean, user: AuthUser | null) => void;
const listeners = new Set<AuthListener>();

function notifyListeners(): void {
  const isAuthed = Boolean(getAccessToken());
  const user = getUser();
  listeners.forEach((listener) => {
    try {
      listener(isAuthed, user);
    } catch (err) {
      console.error("Auth listener error:", err);
    }
  });
}

function getStorage(): Storage | null {
  if (typeof window !== "undefined" && window.localStorage) {
    return window.localStorage;
  }
  if (typeof localStorage !== "undefined") {
    return localStorage;
  }
  return null;
}

export function getAccessToken(): string | null {
  const storage = getStorage();
  if (!storage) return null;
  return storage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  const storage = getStorage();
  if (!storage) return null;
  return storage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken?: string): void {
  const storage = getStorage();
  if (!storage) return;
  storage.setItem(ACCESS_TOKEN_KEY, accessToken);
  if (refreshToken) {
    storage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  }
  notifyListeners();
}

export function getUser(): AuthUser | null {
  const storage = getStorage();
  if (!storage) return null;
  const raw = storage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setUser(user: AuthUser | null): void {
  const storage = getStorage();
  if (!storage) return;
  if (user) {
    storage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    storage.removeItem(USER_KEY);
  }
  notifyListeners();
}

export function getTenantId(): string | null {
  const storage = getStorage();
  if (!storage) return null;
  return storage.getItem(TENANT_KEY);
}

export function setTenantId(tenantId: string | null): void {
  const storage = getStorage();
  if (!storage) return;
  if (tenantId) {
    storage.setItem(TENANT_KEY, tenantId);
  } else {
    storage.removeItem(TENANT_KEY);
  }
}

export function getSessionId(): string {
  const storage = getStorage();
  if (!storage) return "guest-session";
  let sid = storage.getItem(SESSION_ID_KEY);
  if (!sid) {
    sid = "sess_" + Math.random().toString(36).substring(2, 12) + "_" + Date.now().toString(36);
    storage.setItem(SESSION_ID_KEY, sid);
  }
  return sid;
}

export function clearSessionId(): void {
  const storage = getStorage();
  if (storage) {
    storage.removeItem(SESSION_ID_KEY);
  }
}

export function clearAuth(): void {
  const storage = getStorage();
  if (!storage) return;
  storage.removeItem(ACCESS_TOKEN_KEY);
  storage.removeItem(REFRESH_TOKEN_KEY);
  storage.removeItem(USER_KEY);
  notifyListeners();
}

export function subscribeAuth(listener: AuthListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length < 2) return null;
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    return JSON.parse(jsonPayload) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== "number") return true;
  // Expired if within 10 seconds of expiry
  return Date.now() >= (payload.exp - 10) * 1000;
}
