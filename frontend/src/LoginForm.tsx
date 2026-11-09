import { useState, type FormEvent } from 'react'
import { login, NotLoggedIn, type SessionInfo } from './api'

interface Props {
  onLogin: (session: SessionInfo) => void
}

export default function LoginForm({ onLogin }: Props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      onLogin(await login(username, password))
    } catch (err) {
      // NotLoggedIn carries the server's deliberately vague message.
      setError(err instanceof NotLoggedIn ? err.message : String(err))
      setPassword('')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <h1>Log in</h1>
      {error && <p className="error">{error}</p>}
      <form onSubmit={handleSubmit}>
        <label htmlFor="username">Username</label>
        <input
          id="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          required
          autoFocus
        />

        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />

        <button type="submit" disabled={submitting}>
          {submitting ? 'Logging in…' : 'Log in'}
        </button>
      </form>
    </>
  )
}
