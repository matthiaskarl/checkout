import { useState, type FormEvent, type KeyboardEvent, type MouseEvent } from 'react'
import { Link } from 'react-router'
import { NotLoggedIn, updateItem, ValidationFailed, type FieldErrors, type Item } from './api'

interface Props {
  item: Item
  highlight: boolean
  removing: boolean
  onDelete: (item: Item) => void
  onSaved: (item: Item) => void
}

/**
 * One table row with inline editing, like _item_row.html + _item_row_edit.html. The
 * difference: htmx asked the server for the other version of the row; here the row
 * switches by itself (`editing` state) and only talks to the server to save.
 */
export default function ItemRow({ item, highlight, removing, onDelete, onSaved }: Props) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(item.name)
  const [description, setDescription] = useState(item.description ?? '')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  function startEditing(event: MouseEvent<HTMLAnchorElement>) {
    // Like the htmx version: a plain click edits inline; Ctrl/Cmd/Shift-click (and
    // middle-click, which isn't a "click" event) keep the link's normal behaviour and open
    // the edit page.
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    setName(item.name) // start from the stored values, not from an earlier cancelled edit
    setDescription(item.description ?? '')
    setErrors({})
    setError(null)
    setEditing(true)
  }

  function cancel() {
    setEditing(false)
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setErrors({})
    setError(null)
    try {
      const saved = await updateItem(item.id, {
        name: name.trim(),
        description: description.trim() || null,
      })
      setEditing(false)
      onSaved(saved)
    } catch (err) {
      if (err instanceof ValidationFailed) setErrors(err.fieldErrors)
      else if (!(err instanceof NotLoggedIn)) setError(String(err))
    } finally {
      setSaving(false)
    }
  }

  function handleKeyUp(event: KeyboardEvent<HTMLTableRowElement>) {
    if (event.key === 'Escape') cancel()
  }

  const created = item.created_at.replace('T', ' ').slice(0, 16)

  if (!editing) {
    return (
      <tr className={removing ? 'removing' : highlight ? 'new' : undefined}>
        <td>{item.id}</td>
        <td>{item.name}</td>
        <td>{item.description ?? ''}</td>
        <td>{created}</td>
        <td className="actions">
          <Link to={`/items/${item.id}/edit`} onClick={startEditing}>
            Edit
          </Link>
          <button type="button" onClick={() => onDelete(item)}>
            Delete
          </button>
        </td>
      </tr>
    )
  }

  // Same trick as the Jinja2 edit row: a <form> can't wrap a <tr>, so it sits in the last
  // cell and the inputs join it via form="..." (Enter in a field submits).
  const formId = `edit-item-${item.id}`
  return (
    <tr className="editing" onKeyUp={handleKeyUp}>
      <td>{item.id}</td>
      <td>
        <input
          form={formId}
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={100}
          aria-label="Name"
          required
          autoFocus
        />
        {errors.name && <p className="error">{errors.name}</p>}
      </td>
      <td>
        <input
          form={formId}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={500}
          aria-label="Description"
        />
        {errors.description && <p className="error">{errors.description}</p>}
        {error && <p className="error">{error}</p>}
      </td>
      <td>{created}</td>
      <td className="actions">
        <form id={formId} onSubmit={save}>
          <button type="submit" disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
          <button type="button" onClick={cancel}>
            Cancel
          </button>
        </form>
      </td>
    </tr>
  )
}
