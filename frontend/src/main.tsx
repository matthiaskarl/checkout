import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import App from './App.tsx'

// Mount the React app into <div id="root"> from index.html.
// BrowserRouter: real URLs (/app/items/5/edit) via the History API. basename matches Vite's
// `base` and Apache's /app/ alias; FallbackResource serves index.html for any deep link.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename="/app">
      <App />
    </BrowserRouter>
  </StrictMode>,
)
