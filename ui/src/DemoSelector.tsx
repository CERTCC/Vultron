import { useState } from 'react'
import AppSingleVendor from './App.tsx'
import AppMultiVendor from './App-multivendor.tsx'
import AppMultiVendorValidated from './App-multivendor-validated.tsx'
import AppLogReplay from './App-logreplay.tsx'

export function DemoSelector() {
  const [demoType, setDemoType] = useState<
    'single' | 'multi' | 'multi-validated' | 'logreplay'
  >('multi')

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Demo toggle bar */}
      <div
        style={{
          background: '#0d47a1',
          color: 'white',
          padding: '0.5rem 1rem',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '1rem',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          zIndex: 1000,
        }}
      >
        <span style={{ fontSize: '0.875rem', fontWeight: 'bold' }}>Demo:</span>
        <button
          onClick={() => setDemoType('single')}
          style={{
            padding: '0.5rem 1rem',
            fontSize: '0.875rem',
            background: demoType === 'single' ? 'white' : 'rgba(255,255,255,0.15)',
            color: demoType === 'single' ? '#0d47a1' : 'rgba(255,255,255,0.7)',
            border: demoType === 'single' ? '2px solid white' : '1px solid rgba(255,255,255,0.3)',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: demoType === 'single' ? 'bold' : 'normal',
            transition: 'all 0.2s ease',
            boxShadow: demoType === 'single' ? '0 2px 4px rgba(0,0,0,0.2)' : 'none',
          }}
        >
          Single Vendor
        </button>
        <button
          onClick={() => setDemoType('multi')}
          style={{
            padding: '0.5rem 1rem',
            fontSize: '0.875rem',
            background: demoType === 'multi' ? 'white' : 'rgba(255,255,255,0.15)',
            color: demoType === 'multi' ? '#0d47a1' : 'rgba(255,255,255,0.7)',
            border: demoType === 'multi' ? '2px solid white' : '1px solid rgba(255,255,255,0.3)',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: demoType === 'multi' ? 'bold' : 'normal',
            transition: 'all 0.2s ease',
            boxShadow: demoType === 'multi' ? '0 2px 4px rgba(0,0,0,0.2)' : 'none',
          }}
        >
          Multi-Vendor
        </button>
        <button
          onClick={() => setDemoType('multi-validated')}
          style={{
            padding: '0.5rem 1rem',
            fontSize: '0.875rem',
            background: demoType === 'multi-validated' ? 'white' : 'rgba(255,255,255,0.15)',
            color: demoType === 'multi-validated' ? '#0d47a1' : 'rgba(255,255,255,0.7)',
            border: demoType === 'multi-validated' ? '2px solid white' : '1px solid rgba(255,255,255,0.3)',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: demoType === 'multi-validated' ? 'bold' : 'normal',
            transition: 'all 0.2s ease',
            boxShadow: demoType === 'multi-validated' ? '0 2px 4px rgba(0,0,0,0.2)' : 'none',
          }}
        >
          Multi-Vendor (Validated)
        </button>
        <button
          onClick={() => setDemoType('logreplay')}
          style={{
            padding: '0.5rem 1rem',
            fontSize: '0.875rem',
            background: demoType === 'logreplay' ? 'white' : 'rgba(255,255,255,0.15)',
            color: demoType === 'logreplay' ? '#0d47a1' : 'rgba(255,255,255,0.7)',
            border: demoType === 'logreplay' ? '2px solid white' : '1px solid rgba(255,255,255,0.3)',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: demoType === 'logreplay' ? 'bold' : 'normal',
            transition: 'all 0.2s ease',
            boxShadow: demoType === 'logreplay' ? '0 2px 4px rgba(0,0,0,0.2)' : 'none',
          }}
        >
          Log Replay
        </button>
      </div>

      {/* Demo content */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {demoType === 'single' && <AppSingleVendor />}
        {demoType === 'multi' && <AppMultiVendor />}
        {demoType === 'multi-validated' && <AppMultiVendorValidated />}
        {demoType === 'logreplay' && <AppLogReplay />}
      </div>
    </div>
  )
}
