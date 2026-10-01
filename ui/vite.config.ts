import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      // Allow importing the committed protocol-state artifact, which lives at
      // the repo root (`../data/json/protocol_states.json`), outside `ui/`.
      // See ui/CLAUDE.md §9 — the demo defers to that artifact as the protocol
      // source of truth rather than hardcoding states/transitions.
      allow: ['..', '.'],
    },
  },
})
