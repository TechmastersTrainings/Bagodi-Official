/**
 * Centralized Type-Safe API Client for Bagodi Platform.
 * Supports both OpenAPI fetch client (Merchant & Super Admin) and Class-based REST client (Customer Web).
 * Connects directly to authoritative FastAPI /api/v1 backend without mock fallback.
 */

import createClient from "openapi-fetch";
import type { paths } from "./schema.js";
import {
  getAccessToken,
  getRefreshToken,
  getTenantId,
  getSessionId,
  setTokens,
  clearAuth,
} from "./auth.js";
import {
  ApiError,
  AuthenticationError,
  ForbiddenError,
  NotFoundError,
  ValidationError,
  ServerError,
  NetworkError,
} from "./errors.js";
import type { RequestConfig, ApiClientConfig, ApiClientAuthConfig } from "./types.js";

// Determine base API URL
function resolveBaseUrl(): string {
  if (typeof window !== "undefined") {
    const win = window as unknown as { __BAGODI_API_URL__?: string; __API_BASE_URL__?: string };
    if (win.__BAGODI_API_URL__) return win.__BAGODI_API_URL__.replace(/\/api\/v1\/?$/, "");
    if (win.__API_BASE_URL__) return win.__API_BASE_URL__.replace(/\/api\/v1\/?$/, "");
    const metaEnv = (import.meta as unknown as { env?: { VITE_API_BASE_URL?: string } }).env;
    if (metaEnv?.VITE_API_BASE_URL) return metaEnv.VITE_API_BASE_URL.replace(/\/api\/v1\/?$/, "");
  }
  return "";
}

export const API_BASE_URL = resolveBaseUrl();

// Refresh coordination queue
let isRefreshing = false;
let refreshQueue: Array<(token: string) => void> = [];

function flushRefreshQueue(newToken: string): void {
  refreshQueue.forEach((cb) => cb(newToken));
  refreshQueue = [];
}

async function authenticatedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const token = getAccessToken();
  const tenantId = getTenantId();
  const sessionId = getSessionId();

  const headers = new Headers(input instanceof Request ? input.headers : init?.headers);
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (tenantId && !headers.has("X-Tenant-ID")) {
    headers.set("X-Tenant-ID", tenantId);
  }
  if (sessionId && !headers.has("X-Session-ID")) {
    headers.set("X-Session-ID", sessionId);
  }

  const method = (input instanceof Request ? input.method : init?.method || "GET").toUpperCase();
  if (!headers.has("Content-Type") && method !== "GET" && method !== "HEAD") {
    headers.set("Content-Type", "application/json");
  }

  const targetInput = input instanceof Request ? new Request(input, { headers }) : input;
  const targetInit = input instanceof Request ? undefined : { ...init, headers };

  const response = await fetch(targetInput, targetInit);

  // Determine if URL is an auth lifecycle endpoint (skip refresh loops)
  const urlStr = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
  const isAuthLifecycle =
    urlStr.includes("/auth/login") ||
    urlStr.includes("register") ||
    urlStr.includes("/auth/token/refresh") ||
    urlStr.includes("/auth/otp/") ||
    urlStr.includes("/auth/logout");

  // On 401 Unauthorized, initiate token rotation and replay
  if (response.status === 401 && !isAuthLifecycle) {
    const currentRefreshToken = getRefreshToken();
    if (!currentRefreshToken) {
      clearAuth();
      return response;
    }

    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const refreshUrl = `${API_BASE_URL.replace(/\/$/, "")}/api/v1/auth/token/refresh`;
        const refreshResp = await fetch(refreshUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: currentRefreshToken }),
        });

        if (refreshResp.ok) {
          const data = (await refreshResp.json()) as { access_token: string; refresh_token: string };
          setTokens(data.access_token, data.refresh_token);
          isRefreshing = false;
          flushRefreshQueue(data.access_token);
        } else {
          isRefreshing = false;
          refreshQueue = [];
          clearAuth();
          return response;
        }
      } catch (err) {
        isRefreshing = false;
        refreshQueue = [];
        clearAuth();
        return response;
      }
    }

    // Await active refresh and replay original request
    return new Promise<Response>((resolve) => {
      refreshQueue.push((refreshedToken: string) => {
        if (input instanceof Request) {
          input.headers.set("Authorization", `Bearer ${refreshedToken}`);
          if (tenantId) input.headers.set("X-Tenant-ID", tenantId);
          resolve(fetch(input));
        } else {
          const replayHeaders = new Headers(init?.headers);
          replayHeaders.set("Authorization", `Bearer ${refreshedToken}`);
          if (tenantId) replayHeaders.set("X-Tenant-ID", tenantId);
          resolve(fetch(input, { ...init, headers: replayHeaders }));
        }
      });
    });
  }

  return response;
}

/**
 * OpenAPI-fetch client used by Merchant Admin and Super Admin
 */
export const client = createClient<paths>({
  baseUrl: API_BASE_URL,
  fetch: authenticatedFetch,
});

/**
 * Class-based REST client used by Customer Web and Authentication package
 */
export class ApiClient {
  private baseUrl: string;
  private defaultTimeoutMs: number;
  private tokenGetter: (() => Promise<string | null> | string | null) | null = null;
  private tokenRefresher: (() => Promise<string | null> | string | null) | null = null;
  private onTokenRefreshedCb: ((token: string) => void) | null = null;
  private onUnauthorizedCb: (() => void) | null = null;
  private refreshPromise: Promise<string | null> | null = null;

  constructor(config: ApiClientConfig = {}) {
    this.baseUrl = config.baseUrl || (typeof window !== "undefined" && (window as any).__API_BASE_URL__) || "/api/v1";
    this.defaultTimeoutMs = config.defaultTimeoutMs || 30000;
  }

  public updateConfig(authConfig: ApiClientAuthConfig): void {
    if (authConfig.getAccessToken) this.tokenGetter = authConfig.getAccessToken;
    if (authConfig.getRefreshToken) this.tokenRefresher = authConfig.getRefreshToken;
    if (authConfig.onTokenRefreshed) this.onTokenRefreshedCb = authConfig.onTokenRefreshed;
    if (authConfig.onUnauthorized) this.onUnauthorizedCb = authConfig.onUnauthorized;
  }

  public setTokenGetter(getter: () => Promise<string | null> | string | null): void {
    this.tokenGetter = getter;
  }

  public setTokenRefresher(refresher: () => Promise<string | null> | string | null): void {
    this.tokenRefresher = refresher;
  }

  private buildUrl(path: string, params?: Record<string, string | number | boolean | undefined | null>): string {
    const cleanPath = path.startsWith("/") ? path : `/${path}`;
    const base = this.baseUrl.replace(/\/$/, "");
    const fullPath = cleanPath.startsWith(base) ? cleanPath : `${base}${cleanPath}`;
    const url = new URL(fullPath, typeof window !== "undefined" ? window.location.origin : "http://localhost");

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }

    return url.pathname + url.search;
  }

  public async request<T = unknown>(path: string, config: RequestConfig = {}): Promise<T> {
    const { params, skipAuth = false, timeoutMs = this.defaultTimeoutMs, headers: customHeaders, ...fetchInit } = config;

    const url = this.buildUrl(path, params);
    const headers = new Headers(customHeaders);

    if (!headers.has("Content-Type") && !(fetchInit.body instanceof FormData) && fetchInit.method !== "GET" && fetchInit.method !== "HEAD") {
      headers.set("Content-Type", "application/json");
    }
    headers.set("Accept", "application/json");

    if (!skipAuth) {
      let token: string | null = null;
      if (this.tokenGetter) {
        try {
          token = await this.tokenGetter();
        } catch {}
      }
      if (!token) {
        token = getAccessToken();
      }
      if (token && !headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${token}`);
      }
    }

    const tenantId = getTenantId();
    if (tenantId && !headers.has("X-Tenant-ID")) {
      headers.set("X-Tenant-ID", tenantId);
    }
    const sessionId = getSessionId();
    if (sessionId && !headers.has("X-Session-ID")) {
      headers.set("X-Session-ID", sessionId);
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url, {
        ...fetchInit,
        headers,
        signal: fetchInit.signal || controller.signal,
      });
      clearTimeout(timer);

      // Handle 401 Unauthorized with token refresh mutex
      if (response.status === 401 && !skipAuth) {
        let refreshToken: string | null = null;
        if (this.tokenRefresher) {
          try {
            refreshToken = await this.tokenRefresher();
          } catch {}
        }
        if (!refreshToken) {
          refreshToken = getRefreshToken();
        }

        if (refreshToken) {
          if (!this.refreshPromise) {
            this.refreshPromise = (async () => {
              try {
                const refreshRes = await fetch(this.buildUrl("/auth/token/refresh"), {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ refresh_token: refreshToken }),
                });
                if (refreshRes.ok) {
                  const data = await refreshRes.json();
                  const newAccess = data.access_token || data.accessToken;
                  const newRefresh = data.refresh_token || data.refreshToken;
                  if (newAccess && newRefresh) {
                    setTokens(newAccess, newRefresh);
                  }
                  if (newAccess && this.onTokenRefreshedCb) {
                    this.onTokenRefreshedCb(newAccess);
                  }
                  return newAccess;
                }
                return null;
              } catch {
                return null;
              } finally {
                this.refreshPromise = null;
              }
            })();
          }

          const newTok = await this.refreshPromise;
          if (newTok) {
            headers.set("Authorization", `Bearer ${newTok}`);
            const retryRes = await fetch(url, { ...fetchInit, headers });
            if (retryRes.ok) {
              const ct = retryRes.headers.get("content-type");
              return ct && ct.includes("application/json") ? ((await retryRes.json()) as T) : ((await retryRes.text()) as unknown as T);
            }
          }
        }

        if (this.onUnauthorizedCb) {
          this.onUnauthorizedCb();
        }
        throw new AuthenticationError("Authentication session expired or invalid");
      }

      if (!response.ok) {
        let errData: any = null;
        try {
          errData = await response.json();
        } catch {
          errData = await response.text();
        }
        const errorMsg = typeof errData === "object" && errData !== null
          ? (errData.message || (Array.isArray(errData.detail) ? errData.detail.map((d: any) => d.msg).join(", ") : errData.detail) || `HTTP error ${response.status}`)
          : String(errData || `HTTP error ${response.status}`);

        if (response.status === 401) throw new AuthenticationError(errorMsg, errData);
        if (response.status === 403) throw new ForbiddenError(errorMsg, errData);
        if (response.status === 404) throw new NotFoundError(errorMsg, errData);
        if (response.status === 422) throw new ValidationError(errorMsg, undefined, errData);
        if (response.status >= 500) throw new ServerError(errorMsg, errData);
        throw new ApiError(errorMsg, response.status, errData);
      }

      if (response.status === 204) {
        return undefined as unknown as T;
      }

      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        return (await response.json()) as T;
      }
      return (await response.text()) as unknown as T;
    } catch (err: any) {
      clearTimeout(timer);
      if (err instanceof ApiError) throw err;
      if (err.name === "AbortError") throw new NetworkError("Request timed out");
      throw new NetworkError(err.message || "Network request failed");
    }
  }

  public get<T = unknown>(path: string, config?: RequestConfig): Promise<T> {
    return this.request<T>(path, { ...config, method: "GET" });
  }

  public post<T = unknown>(path: string, body?: unknown, config?: RequestConfig): Promise<T> {
    return this.request<T>(path, {
      ...config,
      method: "POST",
      body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  public put<T = unknown>(path: string, body?: unknown, config?: RequestConfig): Promise<T> {
    return this.request<T>(path, {
      ...config,
      method: "PUT",
      body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  public patch<T = unknown>(path: string, body?: unknown, config?: RequestConfig): Promise<T> {
    return this.request<T>(path, {
      ...config,
      method: "PATCH",
      body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  public delete<T = unknown>(path: string, config?: RequestConfig): Promise<T> {
    return this.request<T>(path, { ...config, method: "DELETE" });
  }
}

export const defaultApiClient = new ApiClient();
