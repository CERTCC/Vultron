import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { DemoSelector } from './DemoSelector.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DemoSelector />
  </StrictMode>,
)
