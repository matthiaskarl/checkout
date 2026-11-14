import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import {
  createItem,
  getItem,
  isAbort,
  NotFound,
  NotLoggedIn,
  updateItem,
  ValidationFailed,
  type FieldErrors,
  type Item,
} from './api'
import type { Notice } from './ItemsListPage'

/**
 * One component for "new" (/items/new) and "edit" (/items/:id/edit), like the shared
 * Jinja2 template item_form.html: `id` from the URL decides which.
 */
export default function ItemFormPage() {
  const { id } = useParams()
  const itemId = id === undefined ? null : Number(id)
  const navigate = useNavigate()

  const [item, setItem] = useState<Item | null>(null) // the stored item when editing
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Editing: load the item and prefill the fields. Re-runs if the id in the URL changes.
  useEffect(() => {
    if (itemId === null) return
    const controller = new AbortController()
    getItem(itemId, controller.signal)
      .then((loaded) => {
        setItem(loaded)
        setName(loaded.name)
        setDescription(loaded.description ?? '')
      })
      .catch((err: unknown) => {
        if (isAbort(err) || err instanceof NotLoggedIn) return
        setError(err instanceof NotFound ? err.message : String(err))
      })
    return () => controller.abort()
  }, [itemId])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setErrors({})
    setError(null)
    const data = { name: name.trim(), description: description.trim() || null }
    try {
      // Edit sends both fields: a full update, like the Jinja2 edit page (PATCH allows less).
      const saved = itemId === null ? await createItem(data) : await updateItem(itemId, data)
      const notice: Notice = {
        text: `${itemId === null ? 'Created' : 'Saved'} item #${saved.id}: ${saved.name}`,
        itemId: saved.id,
      }
      navigate('/items', { state: notice })
    } catch (err) {
      if (err instanceof ValidationFailed) setErrors(err.fieldErrors)
      else if (!(err instanceof NotLoggedIn)) setError(String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const heading = itemId === null ? 'New item' : `Edit item #${itemId}`
  const loadingItem = itemId !== null && item === null

  return (
    <>
      <h1>{heading}</h1>
      {error && <p className="error">{error}</p>}

      {loadingItem && !error ? (
        <p>Loading…</p>
      ) : (
        !error && (
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
              {submitting ? 'Saving…' : itemId === null ? 'Create' : 'Save'}
            </button>
            <Link className="cancel" to="/items">
              Cancel
            </Link>
          </form>
        )
      )}
    </>
  )
}
