import { LANE_HEIGHT } from '../constants'

interface Action {
  id: string
  label: string
  description: string
  enabled: boolean
}

interface ActorPanelProps {
  name: string
  role: string
  color: string
  rmState: string
  emState?: string
  vfdState?: string
  pxaState?: string
  actions: Action[]
  onActionClick: (actionId: string) => void
}

export function ActorPanel({
  name,
  role,
  color,
  rmState,
  emState,
  vfdState,
  pxaState,
  actions,
  onActionClick,
}: ActorPanelProps) {
  return (
    <div
      style={{
        height: LANE_HEIGHT,
        minHeight: LANE_HEIGHT,
        maxHeight: LANE_HEIGHT,
        background: color,
        borderBottom: '2px solid #ddd',
        padding: '1rem',
        display: 'flex',
        flexDirection: 'column',
        boxSizing: 'border-box',
        overflow: 'hidden',
      }}
    >
      <div style={{ marginBottom: '0.5rem' }}>
        <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 'bold' }}>
          {name}
        </h3>
        <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.75rem', color: '#666' }}>
          {role}
        </p>
      </div>

      {/* State indicators */}
      <div
        style={{
          marginBottom: '0.5rem',
          padding: '0.5rem',
          background: 'rgba(255,255,255,0.6)',
          borderRadius: '4px',
          fontSize: '0.7rem',
        }}
      >
        <div>
          <strong>RM:</strong> {rmState}
        </div>
        {emState && (
          <div>
            <strong>EM:</strong> {emState}
          </div>
        )}
        {vfdState && (
          <div>
            <strong>VFD:</strong> {vfdState}
          </div>
        )}
        {pxaState && (
          <div>
            <strong>PXA:</strong> {pxaState}
          </div>
        )}
      </div>

      {/* Actions */}
      {actions.length > 0 && (
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: '0.5rem',
            overflowY: 'auto',
          }}
        >
          {actions.map((action) => (
            <button
              key={action.id}
              onClick={() => onActionClick(action.id)}
              disabled={!action.enabled}
              title={action.description}
              style={{
                padding: '0.5rem',
                fontSize: '0.75rem',
                textAlign: 'left',
                background: action.enabled ? '#4CAF50' : '#ccc',
                color: action.enabled ? 'white' : '#666',
                border: 'none',
                borderRadius: '4px',
                cursor: action.enabled ? 'pointer' : 'not-allowed',
                opacity: action.enabled ? 1 : 0.5,
                flexShrink: 0,
              }}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
