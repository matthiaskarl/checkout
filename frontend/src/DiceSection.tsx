import { useRef, useState, type FormEvent } from 'react'
import { getDiceProbability, isAbort, NotLoggedIn, type DiceResult } from './api'

// The Jinja2 version gets these from the dicesim library; the browser only knows the API,
// so they're constants here (an /api/dicesim/config endpoint could provide them instead).
const FACES = ['A', 'B', 'C']
const DICE = 5

/**
 * Same section as _dice.html, but the result comes as JSON from /api/dicesim (via our
 * session, no API key) and React renders it. htmx got ready-made HTML from /ui/dice.
 */
export default function DiceSection() {
  const [selected, setSelected] = useState<string[]>(() => Array(DICE).fill(''))
  const [result, setResult] = useState<DiceResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [calculating, setCalculating] = useState(false)
  // A ref, not state: changing it must not re-render. Holds the running request's controller.
  const running = useRef<AbortController | null>(null)

  function choose(index: number, value: string) {
    setSelected((prev) => prev.map((v, i) => (i === index ? value : v)))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const goal = selected.filter(Boolean).sort()
    setError(null)
    setResult(null)
    if (goal.length === 0) {
      setError('Choose at least one symbol.') // no request needed for this one
      return
    }
    // Clicking again while a request is running: cancel the old one, so a slow first
    // answer can't overwrite the newer one ("last click wins").
    running.current?.abort()
    const controller = new AbortController()
    running.current = controller
    setCalculating(true)
    try {
      setResult(await getDiceProbability(goal, controller.signal))
    } catch (err) {
      if (!isAbort(err) && !(err instanceof NotLoggedIn)) setError(String(err))
    } finally {
      if (running.current === controller) setCalculating(false)
    }
  }

  return (
    <details className="dice">
      <summary>Dice probability</summary>
      <form onSubmit={handleSubmit}>
        <p className="hint">
          Roll 5 dice up to 3 times and keep what you need. How likely is it to get…
        </p>
        <div className="dice-selects">
          {selected.map((value, index) => (
            <select
              key={index} // fixed positions, so the index is a stable key here
              value={value}
              onChange={(e) => choose(index, e.target.value)}
              aria-label={`Die ${index + 1}`}
            >
              <option value="">–</option>
              {FACES.map((face) => (
                <option key={face} value={face}>
                  {face}
                </option>
              ))}
            </select>
          ))}
          <button type="submit" disabled={calculating}>
            {calculating ? 'Calculating…' : 'Calculate'}
          </button>
        </div>
      </form>
      <div aria-live="polite">
        {error && <p className="error">{error}</p>}
        {result && (
          <p className="dice-result">
            <strong>{result.goal.join(' ')}</strong>:{' '}
            <span className="probability">{(result.probability * 100).toFixed(2)} %</span>
            {result.probability > 0 && (
              <span className="hint">
                {' '}
                (about 1 in {(1 / result.probability).toFixed(1)} attempts)
              </span>
            )}
          </p>
        )}
      </div>
    </details>
  )
}
