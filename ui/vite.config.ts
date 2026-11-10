import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Unit tests of pure modules (ui/AGENTS.md §7): `npm test` runs them once.
  test: {
    include: ['src/**/*.test.ts'],
    environment: 'node',
  },
})
