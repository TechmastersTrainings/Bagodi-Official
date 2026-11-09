/**
 * Centralized Type-Safe API Client for Bagodi Platform.
 * Built on openapi-fetch and authoritative OpenAPI schemas.
 * Enforces automatic JWT attachment, concurrency-safe token refresh rotation,
 * and tenant context propagation without overwriting request headers.
 */

import createClient from "openapi-fetch";
import type { paths } from "./schema.js";
import {
  getAccessToken,
  getRefreshToken,
  getTenantId,
  setTokens,
  clearAuth,
} from "./auth.js";

// Determine base API URL (OpenAPI schema paths already include /api/v1)
function resolveBaseUrl(): string {
  if (typeof window !== "undefined") {
    const win = window as unknown as { __BAGODI_API_URL__?: string };
    if (win.__BAGODI_API_URL__) return win.__BAGODI_API_URL__.replace(/\/api\/v1\/?$/, "");
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

  let req: Request;
  if (input instanceof Request) {
    req = input;
    if (token) req.headers.set("Authorization", `Bearer ${token}`);
    if (tenantId && !req.headers.has("X-Tenant-ID")) req.headers.set("X-Tenant-ID", tenantId);
  } else {
    const headers = new Headers(init?.headers);
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    if (tenantId && !headers.has("X-Tenant-ID")) {
      headers.set("X-Tenant-ID", tenantId);
    }
    req = new Request(input, { ...init, headers });
  }

  const response = await fetch(req);

  // Determine if URL is an auth lifecycle endpoint (skip refresh loops)
  const urlStr = req.url;
  const isAuthLifecycle =
    urlStr.includes("/api/v1/auth/token/refresh") ||
    urlStr.includes("/api/v1/auth/otp/") ||
    urlStr.includes("/api/v1/auth/logout");

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
      } catch {
        isRefreshing = false;
        refreshQueue = [];
        clearAuth();
        return response;
      }
    }

    // Await active refresh and replay original request
    return new Promise<Response>((resolve) => {
      refreshQueue.push((refreshedToken: string) => {
        const retryHeaders = new Headers(req.headers);
        retryHeaders.set("Authorization", `Bearer ${refreshedToken}`);
        if (tenantId) retryHeaders.set("X-Tenant-ID", tenantId);
        resolve(fetch(new Request(req, { headers: retryHeaders })));
      });
    });
  }

  return response;
}

/**
 * The authoritative type-safe Bagodi API Client.
 */
export const client = createClient<paths>({
  baseUrl: API_BASE_URL,
  fetch: authenticatedFetch,
});
