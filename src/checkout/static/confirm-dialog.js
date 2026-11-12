// Custom confirmation dialog for htmx's hx-confirm, replacing the browser's confirm().
//
// htmx fires `htmx:confirm` before every request. Calling preventDefault() stops htmx
// (incl. its native confirm() box); we show our own <dialog> instead and, if the user
// confirms, let htmx continue with detail.issueRequest(true) ("true" = skip the
// native confirm). The dialog markup lives in base.html.
document.addEventListener('htmx:confirm', (event) => {
  const question = event.detail.question // the hx-confirm text, null without hx-confirm
  if (!question) return // not our business: let the request go ahead

  event.preventDefault()
  const dialog = document.getElementById('confirm-dialog')
  dialog.querySelector('[data-question]').textContent = question // textContent: no HTML injection
  dialog.returnValue = ''
  dialog.showModal() // modal: backdrop, focus trapped inside, Esc closes

  dialog.addEventListener(
    'close',
    () => {
      // <form method="dialog"> sets returnValue to the clicked button's value; Esc leaves ''.
      if (dialog.returnValue === 'confirm') event.detail.issueRequest(true)
    },
    { once: true },
  )
})
