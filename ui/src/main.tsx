import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
// Activate this line to view the multivendor demo:
// import App from './App-multivendor.tsx'
// Activate this line to view the one vendor demo:
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
