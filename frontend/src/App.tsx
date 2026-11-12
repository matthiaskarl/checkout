import { useCallback, useEffect, useState } from 'react'
import { getSession, isAbort, logout, type SessionInfo } from './api'
import ItemsPage from './ItemsPage'
import LoginForm from './LoginForm'
import './App.css'

/**
 * The login "gate": asks the server once who is logged in, then shows either the login
 * form or the app. undefined = still asking, null = not logged in.
 */
export default function App() {
  const [session, setSession] = useState<SessionInfo | null | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
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

  // useCallback: a stable function identity, so ItemsPage's effect doesn't re-run each render.
  const handleLoggedOut = useCallback(() => setSession(null), [])

  async function handleLogout() {
    await logout()
    setSession(null)
  }

  if (error) return <p className="error">{error}</p>
  if (session === undefined) return <p>Loading…</p>
  if (session === null) return <LoginForm onLogin={setSession} />

  return (
    <>
      <nav className="userbar">
        <span>
          Logged in as <strong>{session.username}</strong>
        </span>
        <button type="button" onClick={handleLogout}>
          Log out
        </button>
      </nav>
      <ItemsPage onLoggedOut={handleLoggedOut} />
    </>
  )
}
