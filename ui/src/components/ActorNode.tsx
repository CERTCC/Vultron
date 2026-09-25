// Custom node component for actors with interactive action buttons

import { Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'

export interface Action {
  id: string
  label: string
  description: string
  enabled: boolean
}

export interface ActorNodeData {
  actorName: string
  actorRole: string
  rmState?: string
  emState?: string
  vfdState?: string
  pxaState?: string
  actions: Action[]
  onActionClick: (actionId: string) => void
}

export function ActorNode({ data }: NodeProps) {
  const nodeData = data as unknown as ActorNodeData
  return (
    <div
      style={{
        background: '#fff',
        border: '2px solid #333',
        borderRadius: '8px',
        padding: '1rem',
        minWidth: '250px',
        boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
      }}
    >
      <Handle type="target" position={Position.Left} />

      {/* Actor Header */}
      <div style={{ marginBottom: '0.75rem', borderBottom: '2px solid #ddd', paddingBottom: '0.5rem' }}>
        <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 'bold' }}>
          {nodeData.actorName}
        </h3>
        <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem', color: '#666' }}>
          {nodeData.actorRole}
        </p>
      </div>

      {/* State Indicators */}
      {(nodeData.rmState || nodeData.emState || nodeData.vfdState) && (
        <div
          style={{
            marginBottom: '0.75rem',
            padding: '0.5rem',
            background: '#f5f5f5',
            borderRadius: '4px',
            fontSize: '0.75rem',
          }}
        >
          {nodeData.rmState && (
            <div style={{ marginBottom: '0.25rem' }}>
              <strong>RM:</strong> {nodeData.rmState}
            </div>
          )}
          {nodeData.emState && (
            <div style={{ marginBottom: '0.25rem' }}>
              <strong>EM:</strong> {nodeData.emState}
            </div>
          )}
          {nodeData.vfdState && (
            <div style={{ marginBottom: '0.25rem' }}>
              <strong>VFD:</strong> {nodeData.vfdState}
            </div>
          )}
          {nodeData.pxaState && (
            <div>
              <strong>PXA:</strong> {nodeData.pxaState}
            </div>
          )}
        </div>
      )}

      {/* Available Actions */}
      {nodeData.actions.length > 0 && (
        <div>
          <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: '#666' }}>
            Available Actions:
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {nodeData.actions.map((action: Action) => (
              <button
                key={action.id}
                onClick={() => nodeData.onActionClick(action.id)}
                disabled={!action.enabled}
                title={action.description}
                style={{
                  padding: '0.5rem',
                  fontSize: '0.85rem',
                  textAlign: 'left',
                  background: action.enabled ? '#4CAF50' : '#ccc',
                  color: action.enabled ? 'white' : '#666',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: action.enabled ? 'pointer' : 'not-allowed',
                  transition: 'all 0.2s',
                  opacity: action.enabled ? 1 : 0.5,
                }}
                onMouseEnter={(e) => {
                  if (action.enabled) {
                    e.currentTarget.style.background = '#45a049'
                  }
                }}
                onMouseLeave={(e) => {
                  if (action.enabled) {
                    e.currentTarget.style.background = '#4CAF50'
                  }
                }}
              >
                {action.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <Handle type="source" position={Position.Right} />
    </div>
  )
}
