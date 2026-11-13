import { useEffect, useRef } from 'react'

interface Props {
  /** The question; null = dialog closed. */
  question: string | null
  confirmLabel?: string
  onConfirm: () => void
  onCancel: () => void
}

/**
 * The same native <dialog> as in the Jinja2 UI, driven by React state instead of an htmx
 * event: the parent sets `question` to open it. showModal()/close() are imperative DOM
 * methods, so they're called from an effect via a ref.
 */
export default function ConfirmDialog({
  question,
  confirmLabel = 'Delete',
  onConfirm,
  onCancel,
}: Props) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (question !== null && !dialog.open) {
      dialog.returnValue = ''
      dialog.showModal()
    } else if (question === null && dialog.open) {
      dialog.close()
    }
  }, [question])

  // Fires for every way of closing: a button (via method="dialog") or Esc.
  function handleClose() {
    if (ref.current?.returnValue === 'confirm') onConfirm()
    else onCancel()
  }

  return (
    <dialog ref={ref} onClose={handleClose} aria-labelledby="confirm-question">
      <form method="dialog">
        <p id="confirm-question">{question}</p>
        <div className="dialog-buttons">
          <button value="cancel" autoFocus>
            Cancel
          </button>
          <button value="confirm" className="danger">
            {confirmLabel}
          </button>
        </div>
      </form>
    </dialog>
  )
}
