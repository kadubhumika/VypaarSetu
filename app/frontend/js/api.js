// api.js — shared across every page. Include after config.js.
//
// Token storage: sessionStorage (not localStorage) so each browser tab keeps its
// own session — this matters here because you'll often have a merchant tab and a
// customer tab open side by side while testing.

const TOKEN_KEY = "vs_token";
const ROLE_KEY = "vs_role";

function saveSession(token, role) {
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(ROLE_KEY, role);
}

function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

function getRole() {
  return sessionStorage.getItem(ROLE_KEY);
}

function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(ROLE_KEY);
}

/**
 * Core fetch wrapper. Attaches the bearer token automatically if present.
 * Throws an Error with the backend's message on non-2xx responses so callers
 * can just try/catch and show err.message to the user.
 */
 async function handleGoogleLogin(response) {
  try {
    const payload = { token: response.credential };
    const data = await apiFetch("/merchant/auth/google", {
      method: "POST",
      body: payload
    });
    saveSession(data.access_token, data.role);
    window.location.href = data.role === "merchant" ? "/frontend/merchant-dashboard.html" : "/frontend/customer-dashboard.html";

  } catch (err) {
    alert("Google Sign-In failed: " + err.message);
  }
}

async function apiFetch(path, { method = "GET", body = null, isFormData = false, auth = true } = {}) {
  const headers = {};
  if (!isFormData) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
  });

  let data = null;
  try {
    data = await response.json();
  } catch (_) {
    // some endpoints (e.g. 204s) have no body
  }

  if (!response.ok) {
    const message = (data && data.detail) ? data.detail : `Request failed (${response.status})`;
    throw new Error(message);
  }

  return data;
}

/** Redirect to login if there's no token — call at the top of every protected page. */
function requireAuth(expectedRole, loginPage = "login.html") {
  const token = getToken();
  const role = getRole();
  if (!token || (expectedRole && role !== expectedRole)) {
    window.location.href = loginPage;
  }
}