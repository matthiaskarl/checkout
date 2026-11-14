import { useEffect, useState } from 'react'
import { Navigate, NavLink, Route, Routes } from 'react-router'
import { getSession, isAbort, logout, setNotLoggedInHandler, type SessionInfo } from './api'
import ItemFormPage from './ItemFormPage'
import ItemsListPage from './ItemsListPage'
import LoginForm from './LoginForm'
import './App.css'

/**
 * The login "gate" plus the page layout. Asks the server once who is logged in, then shows
 * the login form or the routed pages. undefined = still asking, null = not logged in.
 * The URL stays as it is while logged out, so after login you land on the page you wanted.
 */
export default function App() {
  const [session, setSession] = useState<SessionInfo | null | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Any 401 anywhere (session expired, logged out in another tab) -> back to the login form.
    setNotLoggedInHandler(() => setSession(null))
    const controller = new AbortController()
    getSession(controller.signal)
      .then(setSession)
      .catch((err: unknown) => {
        if (!isAbort(err)) setError(String(err))
      })
    // Cleanup: React calls this before the effect runs again and on unmount. In dev,
    // StrictMode mounts twice, so the first request shows up as "(canceled)".
    return () => controller.abort()
  }, [])

  async function handleLogout() {
    await logout()
    setSession(null)
  }

  if (error) return <p className="error">{error}</p>
  if (session === undefined) return <p>Loading…</p>
  if (session === null) return <LoginForm onLogin={setSession} />

  return (
    <>
      <header>
        <nav>
          {/* NavLink adds class="active" to the link of the current page. */}
          <NavLink to="/items" end>
            Items
          </NavLink>
          <NavLink to="/items/new">New item</NavLink>
        </nav>
        <div className="userbar">
          <span>
            Logged in as <strong>{session.username}</strong>
          </span>
          <button type="button" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </header>

      {/* Same URLs as the Jinja2 UI, under /app instead of /ui. */}
      <Routes>
        <Route path="/" element={<Navigate to="/items" replace />} />
        <Route path="/items" element={<ItemsListPage />} />
        <Route path="/items/new" element={<ItemFormPage />} />
        <Route path="/items/:id/edit" element={<ItemFormPage />} />
        <Route path="*" element={<p className="error">Page not found.</p>} />
      </Routes>
    </>
  )
}
