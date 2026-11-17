import {
  setTokens,
  getAccessToken,
  getRefreshToken,
  clearAuth,
  decodeJwtPayload,
  isTokenExpired,
} from "./auth.js";
import { extractApiError, formatErrorMessage } from "./errors.js";

function assert(condition: boolean, msg: string) {
  if (!condition) {
    throw new Error("Assertion failed: " + msg);
  }
}

// Mock localStorage in Node
const store: Record<string, string> = {};
(globalThis as unknown as { localStorage: Storage }).localStorage = {
  getItem: (key: string) => store[key] || null,
  setItem: (key: string, value: string) => {
    store[key] = value;
  },
  removeItem: (key: string) => {
    delete store[key];
  },
  clear: () => {
    for (const k in store) delete store[k];
  },
  length: 0,
  key: () => null,
};

export function runTests(): void {
  console.log("Running @bagodi/api-client unit tests...");

  // Test 1: Token storage and retrieval
  setTokens("mock_access_token_123", "mock_refresh_token_456");
  assert(getAccessToken() === "mock_access_token_123", "Access token matches");
  assert(getRefreshToken() === "mock_refresh_token_456", "Refresh token matches");

  // Test 2: Clear auth
  clearAuth();
  assert(getAccessToken() === null, "Access token cleared");
  assert(getRefreshToken() === null, "Refresh token cleared");

  // Test 3: JWT decoding & expiration
  const validFutureJwt =
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c3JfdGVzdCIsInJvbGUiOiJDVVNUT01FUiIsImV4cCI6MjUwMDAwMDAwMH0.signature";
  const payload = decodeJwtPayload(validFutureJwt);
  assert(Boolean(payload), "Payload is truthy");
  assert(payload?.sub === "usr_test", "Subject is usr_test");
  assert(payload?.role === "CUSTOMER", "Role is CUSTOMER");
  assert(isTokenExpired(validFutureJwt) === false, "Future token is not expired");

  const expiredJwt =
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c3JfdGVzdCIsImV4cCI6MTAwMH0.signature";
  assert(isTokenExpired(expiredJwt) === true, "Past token is expired");

  // Test 4: Structured error extraction
  const structuredError = {
    error: "INSUFFICIENT_AVAILABLE_STOCK",
    message: "Only 2 units remaining",
    details: { requested: 5, available: 2 },
  };
  const parsed1 = extractApiError(structuredError, 409);
  assert(parsed1.error === "INSUFFICIENT_AVAILABLE_STOCK", "Error code parsed");
  assert(parsed1.message === "Only 2 units remaining", "Message parsed");
  assert(parsed1.status === 409, "Status preserved");

  // Test 5: FastAPI validation error extraction
  const validationError = {
    detail: [
      { loc: ["body", "phone"], msg: "Invalid phone number format", type: "value_error" },
    ],
  };
  const parsed2 = extractApiError(validationError, 422);
  assert(parsed2.error === "VALIDATION_ERROR", "Validation error detected");
  assert(parsed2.message.includes("phone: Invalid phone number format"), "Validation message extracted");
  assert(formatErrorMessage(validationError) === parsed2.message, "Helper formatErrorMessage matches");

  // Test 6: Fallback status code errors
  const fallback401 = extractApiError(null, 401);
  assert(fallback401.error === "UNAUTHORIZED", "Fallback 401 recognized");

  // Test 7: Customer Address type checking
  const testAddress: import("./index.js").CustomerAddress = {
    id: "00000000-0000-0000-0000-000000000001",
    tenant_id: "00000000-0000-0000-0000-000000000002",
    customer_id: "00000000-0000-0000-0000-000000000003",
    full_name: "Anita Sharma",
    phone: "+919876543210",
    address_line1: "Near Gole Khana, Main Bazaar",
    address_line2: null,
    landmark: "Bidar Fort Road",
    city: "Bidar",
    state: "Karnataka",
    postal_code: "585401",
    address_type: "home",
    is_default: true,
    created_at: "2026-11-09T10:00:00Z",
    updated_at: "2026-11-09T10:00:00Z",
  };
  assert(testAddress.city === "Bidar", "Address city matches");
  assert(testAddress.postal_code === "585401", "Address postal code matches");

  // Test 8: Order Return / Size Exchange type checking
  const testReturn: import("./index.js").OrderReturnRequest = {
    id: "00000000-0000-0000-0000-000000000010",
    tenant_id: "00000000-0000-0000-0000-000000000002",
    order_id: "00000000-0000-0000-0000-000000000011",
    order_item_id: "00000000-0000-0000-0000-000000000012",
    customer_id: "00000000-0000-0000-0000-000000000003",
    request_type: "EXCHANGE",
    reason: "SIZE_FIT_ISSUE",
    detailed_reason: "Need Size L instead of Size M",
    requested_variant_id: "00000000-0000-0000-0000-000000000020",
    requested_size: "L",
    status: "REQUESTED",
    refund_amount: null,
    admin_notes: null,
    reviewed_by_user_id: null,
    reviewed_at: null,
    pickup_tracking_id: null,
    images: null,
    created_at: "2026-11-09T10:00:00Z",
    updated_at: "2026-11-09T10:00:00Z",
  };
  assert(testReturn.request_type === "EXCHANGE", "Exchange request type matches");
  assert(testReturn.requested_size === "L", "Requested size matches");

  console.log("All @bagodi/api-client unit tests passed successfully! (8/8 checks)");
}

runTests();

