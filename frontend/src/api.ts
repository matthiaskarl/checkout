// Typed client for the FastAPI backend (mirrors checkout/schemas.py).
//
// Auth model: the browser keeps the HttpOnly session cookie and sends it automatically
// (same origin). JavaScript can't read that cookie, so it asks GET /api/session who is
// logged in and gets the CSRF token, which it must send as X-CSRF-Token on every write.

export interface Item {
  id: number
  name: string
  description: string | null
  created_at: string
}

export interface ItemCreate {
  name: string
  description: string | null
}

/** PATCH body: only the fields that should change. */
export type ItemUpdate = Partial<ItemCreate>

export interface DiceResult {
  goal: string[]
  method: string
  probability: number
}

export interface SessionInfo {
  username: string
  csrf_token: string
}

/** Field name -> error message, built from FastAPI's 422 response. */
export type FieldErrors = Partial<Record<keyof ItemCreate, string>>

export class ValidationFailed extends Error {
  readonly fieldErrors: FieldErrors

  constructor(fieldErrors: FieldErrors) {
    super('Validation failed')
    this.fieldErrors = fieldErrors
  }
}

/** 401: not logged in (never was, logged out elsewhere, or the session expired). */
export class NotLoggedIn extends Error {
  constructor(message = 'Not logged in') {
    super(message)
  }
}

export class NotFound extends Error {}

// FastAPI's validation error format: {"detail": [{"loc": ["body", "name"], "msg": "..."}]}
interface FastApiValidationError {
  detail: { loc: (string | number)[]; msg: string }[]
}

const API = '/api'

// Module-level, set by getSession()/login(). Not in localStorage: it's only valid as long
// as the session cookie is, and the next page load fetches it again anyway.
let csrfToken: string | null = null

// Called on every 401, before the NotLoggedIn error is thrown. App registers it once to
// show the login form, so components don't each need an "onLoggedOut" prop.
let onNotLoggedIn: () => void = () => {}

export function setNotLoggedInHandler(handler: () => void): void {
  onNotLoggedIn = handler
}

/** Every request goes through here: adds the CSRF header to writes, maps 401. */
async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  const method = (init.method ?? 'GET').toUpperCase()
  if (method !== 'GET' && csrfToken) headers.set('X-CSRF-Token', csrfToken)
  if (init.body !== undefined) headers.set('Content-Type', 'application/json')

  // credentials: 'same-origin' is fetch's default: the cookie goes along to our own API only.
  const res = await fetch(`${API}${path}`, { ...init, headers })
  if (res.status === 401) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string }
    // Not for /session itself: there a 401 is an expected answer (login form / "who am I?").
    if (!path.startsWith('/session')) onNotLoggedIn()
    throw new NotLoggedIn(body.detail)
  }
  return res
}

// --- session ---------------------------------------------------------------------------

// `signal` (optional): from an AbortController; aborting cancels the request and the
// returned promise rejects with an AbortError (see isAbort).

/** True for the error a fetch throws when its AbortController was aborted. */
export function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError'
}

/** The current login, or null if not logged in. */
export async function getSession(signal?: AbortSignal): Promise<SessionInfo | null> {
  try {
    const res = await request('/session', { signal })
    if (!res.ok) throw new Error(`Checking login failed (HTTP ${res.status})`)
    const info = (await res.json()) as SessionInfo
    csrfToken = info.csrf_token
    return info
  } catch (err) {
    if (err instanceof NotLoggedIn) {
      csrfToken = null
      return null
    }
    throw err
  }
}

/** Throws NotLoggedIn with "Invalid username or password." on bad credentials. */
export async function login(username: string, password: string): Promise<SessionInfo> {
  const res = await request('/session', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) throw new Error(`Login failed (HTTP ${res.status})`)
  const info = (await res.json()) as SessionInfo
  csrfToken = info.csrf_token
  return info
}

export async function logout(): Promise<void> {
  try {
    await request('/session', { method: 'DELETE' })
  } catch (err) {
    if (!(err instanceof NotLoggedIn)) throw err // already logged out: fine
  } finally {
    csrfToken = null
  }
}

// --- items -----------------------------------------------------------------------------

export async function listItems(signal?: AbortSignal): Promise<Item[]> {
  const res = await request('/items', { signal })
  if (!res.ok) throw new Error(`Loading items failed (HTTP ${res.status})`)
  return res.json()
}

/** Throws NotFound for an unknown id. */
export async function getItem(id: number, signal?: AbortSignal): Promise<Item> {
  const res = await request(`/items/${id}`, { signal })
  if (res.status === 404) throw new NotFound(`Item #${id} not found`)
  if (!res.ok) throw new Error(`Loading item failed (HTTP ${res.status})`)
  return res.json()
}

export async function createItem(data: ItemCreate): Promise<Item> {
  const res = await request('/items', { method: 'POST', body: JSON.stringify(data) })
  return itemOrValidationError(res, 'Saving')
}

export async function updateItem(id: number, data: ItemUpdate): Promise<Item> {
  const res = await request(`/items/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
  if (res.status === 404) throw new NotFound(`Item #${id} not found`)
  return itemOrValidationError(res, 'Saving')
}

export async function deleteItem(id: number): Promise<void> {
  const res = await request(`/items/${id}`, { method: 'DELETE' })
  // 404: already gone (e.g. deleted in another tab) - the goal is reached either way.
  if (!res.ok && res.status !== 404) throw new Error(`Deleting failed (HTTP ${res.status})`)
}

/** Shared by create/update: 422 -> ValidationFailed with per-field messages. */
async function itemOrValidationError(res: Response, action: string): Promise<Item> {
  if (res.status === 422) {
    const body = (await res.json()) as FastApiValidationError
    const errors: FieldErrors = {}
    for (const err of body.detail) {
      const field = err.loc.at(-1)
      if (field === 'name' || field === 'description') errors[field] = err.msg
    }
    throw new ValidationFailed(errors)
  }
  if (!res.ok) throw new Error(`${action} failed (HTTP ${res.status})`)
  return res.json()
}

// --- dicesim -----------------------------------------------------------------------------

/** Exact probability via the public JSON API (uses our session, no API key needed). */
export async function getDiceProbability(goal: string[], signal?: AbortSignal): Promise<DiceResult> {
  const params = new URLSearchParams({ goal: goal.join(''), method: 'exact' })
  const res = await request(`/dicesim?${params}`, { signal })
  if (res.status === 422) {
    const body = (await res.json()) as FastApiValidationError
    throw new Error(body.detail[0]?.msg ?? 'Invalid goal')
  }
  if (!res.ok) throw new Error(`Calculation failed (HTTP ${res.status})`)
  return res.json()
}
