import { useEffect, useState, type FormEvent } from 'react'
import {
  createItem,
  listItems,
  NotLoggedIn,
  ValidationFailed,
  type FieldErrors,
  type Item,
} from './api'

interface Props {
  /** Called when the API answers 401 (session expired or ended elsewhere). */
  onLoggedOut: () => void
}

export default function ItemsPage({ onLoggedOut }: Props) {
  // Component state: whenever one of these changes, React re-renders the component.
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<Item | null>(null)
  const [items, setItems] = useState<Item[]>([])
  const [submitting, setSubmitting] = useState(false)

  // Load existing items once, after the first render.
  useEffect(() => {
    listItems()
      .then(setItems)
      .catch((err: unknown) => {
        if (err instanceof NotLoggedIn) onLoggedOut()
        else setError(String(err))
      })
  }, [onLoggedOut])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault() // stop the browser's default full-page form submit
    setSubmitting(true)
    setErrors({})
    setError(null)
    try {
      const item = await createItem({
        name: name.trim(),
        description: description.trim() || null,
      })
      setCreated(item)
      setItems((prev) => [...prev, item]) // update the table without reloading
      setName('')
      setDescription('')
    } catch (err) {
      if (err instanceof NotLoggedIn) onLoggedOut()
      else if (err instanceof ValidationFailed) setErrors(err.fieldErrors)
      else setError(String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const latest = [...items].sort((a, b) => b.id - a.id).slice(0, 10)

  return (
    <>
      <h1>New item</h1>

      {created && (
        <p className="notice">
          Created item #{created.id}: <strong>{created.name}</strong>
        </p>
      )}
      {error && <p className="error">{error}</p>}

      <form onSubmit={handleSubmit}>
        <label htmlFor="name">Name</label>
        <input
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={100}
          required
          autoFocus
        />
        {errors.name && <p className="error">{errors.name}</p>}

        <label htmlFor="description">Description</label>
        <textarea
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          maxLength={500}
        />
        {errors.description && <p className="error">{errors.description}</p>}

        <button type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : 'Create'}
        </button>
      </form>

      <h2>Latest items</h2>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Name</th>
            <th>Description</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {latest.length === 0 ? (
            <tr>
              <td colSpan={4}>No items yet.</td>
            </tr>
          ) : (
            latest.map((item) => (
              <tr key={item.id}>
                <td>{item.id}</td>
                <td>{item.name}</td>
                <td>{item.description ?? ''}</td>
                <td>{item.created_at.replace('T', ' ').slice(0, 16)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </>
  )
}
