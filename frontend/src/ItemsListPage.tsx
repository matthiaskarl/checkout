import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { deleteItem, isAbort, listItems, NotLoggedIn, type Item } from './api'
import ConfirmDialog from './ConfirmDialog'

/** Passed by ItemFormPage via navigate(..., { state }) after saving. */
export interface Notice {
  text: string
  /** Row to highlight. */
  itemId?: number
}

const FADE_MS = 400 // keep in sync with the CSS transition on tr.removing

export default function ItemsListPage() {
  const location = useLocation()
  const navigate = useNavigate()
  // Read the notice once. It came with the navigation, not in the URL (unlike ?created=5).
  const [notice, setNotice] = useState<Notice | null>(() => location.state as Notice | null)
  const [items, setItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toDelete, setToDelete] = useState<Item | null>(null)
  const [removing, setRemoving] = useState<number | null>(null)

  useEffect(() => {
    // The browser keeps history state across reloads; clear it so a reload doesn't
    // show the notice again (like a one-time "flash message").
    if (location.state) navigate('.', { replace: true, state: null })
  }, [location.state, navigate])

  useEffect(() => {
    const controller = new AbortController()
    listItems(controller.signal)
      .then((all) => setItems([...all].sort((a, b) => b.id - a.id))) // newest first
      .catch((err: unknown) => {
        if (!isAbort(err) && !(err instanceof NotLoggedIn)) setError(String(err))
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  async function confirmDelete() {
    const item = toDelete
    setToDelete(null)
    if (!item) return
    try {
      await deleteItem(item.id)
    } catch (err) {
      if (!(err instanceof NotLoggedIn)) setError(String(err))
      return
    }
    // Fade the row out first, then drop it from the state (= from the DOM).
    setRemoving(item.id)
    setTimeout(() => {
      setItems((prev) => prev.filter((i) => i.id !== item.id))
      setRemoving(null)
      setNotice({ text: `Deleted item #${item.id}.` })
    }, FADE_MS)
  }

  return (
    <>
      <h1>Items</h1>
      {notice && <p className="notice">{notice.text}</p>}
      {error && <p className="error">{error}</p>}

      <Link className="button" to="/items/new">
        + New item
      </Link>

      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Name</th>
            <th>Description</th>
            <th>Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={5}>Loading…</td>
            </tr>
          ) : items.length === 0 ? (
            <tr>
              <td colSpan={5}>No items yet.</td>
            </tr>
          ) : (
            items.map((item) => (
              <tr
                key={item.id}
                className={
                  item.id === removing ? 'removing' : item.id === notice?.itemId ? 'new' : undefined
                }
              >
                <td>{item.id}</td>
                <td>{item.name}</td>
                <td>{item.description ?? ''}</td>
                <td>{item.created_at.replace('T', ' ').slice(0, 16)}</td>
                <td className="actions">
                  <Link to={`/items/${item.id}/edit`}>Edit</Link>
                  <button type="button" onClick={() => setToDelete(item)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      <ConfirmDialog
        question={toDelete && `Delete item #${toDelete.id} (${toDelete.name})?`}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      />
    </>
  )
}
