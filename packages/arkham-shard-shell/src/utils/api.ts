/**
 * API client utilities with automatic authentication header injection.
 *
 * Use these functions instead of raw fetch() to ensure auth tokens are included
 * and handle 401 responses gracefully.
 */

/** localStorage key for the current user's JWT. Same key app-wide; the value is per-user (whoever is logged in). Not secret — the token value is what must be protected. */
const TOKEN_KEY = 'arkham_token';

/**
 * Fetch wrapper that automatically includes auth token and handles 401 responses.
 */
export async function apiFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = localStorage.getItem(TOKEN_KEY);

  const headers = new Headers(options.headers);

  // Add auth token if present
  // Allow callers to override Authorization explicitly (e.g. login flows)
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Set Content-Type for JSON if not FormData
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, { ...options, headers });

  // Handle 401 Unauthorized - token expired or invalid
  if (response.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    // Only redirect if not already on auth pages
    if (!window.location.pathname.startsWith('/login') &&
        !window.location.pathname.startsWith('/setup')) {
      window.location.href = '/login';
    }
  }

  return response;
}

/**
 * GET request with JSON response.
 */
export async function apiGet<T>(url: string): Promise<T> {
  const res = await apiFetch(url);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }
  return res.json();
}

/**
 * POST request with JSON body and response.
 */
export async function apiPost<T>(url: string, data?: unknown): Promise<T> {
  const res = await apiFetch(url, {
    method: 'POST',
    body: data ? JSON.stringify(data) : undefined,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }
  return res.json();
}

/**
 * PUT request with JSON body and response.
 */
export async function apiPut<T>(url: string, data: unknown): Promise<T> {
  const res = await apiFetch(url, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }
  return res.json();
}

/**
 * PATCH request with JSON body and response.
 */
export async function apiPatch<T>(url: string, data: unknown): Promise<T> {
  const res = await apiFetch(url, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }
  return res.json();
}

/**
 * DELETE request.
 */
export async function apiDelete<T = void>(url: string): Promise<T> {
  const res = await apiFetch(url, { method: 'DELETE' });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }
  // Some DELETE endpoints return data, some don't
  const text = await res.text();
  return text ? JSON.parse(text) : (undefined as T);
}

/**
 * Upload file(s) with multipart form data.
 */
export async function apiUpload<T>(
  url: string,
  formData: FormData
): Promise<T> {
  const res = await apiFetch(url, {
    method: 'POST',
    body: formData,
    // Don't set Content-Type - browser will set it with boundary
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(error.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Check if user is currently authenticated (has valid token).
 */
export function isAuthenticated(): boolean {
  return !!localStorage.getItem(TOKEN_KEY);
}

/**
 * Get the current auth token.
 */
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * Clear auth token (logout).
 */
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}
