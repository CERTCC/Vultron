import { LANE_HEIGHT, LANE_HEIGHT_COLLAPSED } from '../constants'

interface Action {
  id: string
  label: string
  description: string
  enabled: boolean
}

interface ActorPanelProps {
  participantId: string
  name: string
  role: string
  color: string
  rmState: string
  emState?: string
  vfdState?: string
  pxaState?: string
  actions: Action[]
  onActionClick: (actionId: string) => void
  isCollapsed?: boolean
  onToggleCollapse?: () => void
}

export function ActorPanel({
  participantId,
  name,
  role,
  color,
  rmState,
  emState,
  vfdState,
  pxaState,
  actions,
  onActionClick,
  isCollapsed = false,
  onToggleCollapse,
}: ActorPanelProps) {
  const height = isCollapsed ? LANE_HEIGHT_COLLAPSED : LANE_HEIGHT

  return (
    <div
      data-participant-id={participantId}
      style={{
        height,
        minHeight: height,
        maxHeight: height,
        background: color,
        borderBottom: '2px solid #ddd',
        padding: '1rem',
        display: 'flex',
        flexDirection: 'column',
        boxSizing: 'border-box',
      }}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        marginBottom: '0.5rem',
      }}>
        {onToggleCollapse && (
          <span
            data-collapse-button={participantId}
            onClick={onToggleCollapse}
            style={{
              cursor: 'pointer',
              fontSize: '0.75rem',
              userSelect: 'none',
              flexShrink: 0,
            }}
            title={isCollapsed ? 'Expand lane' : 'Collapse lane'}
          >
            {isCollapsed ? '▶' : '▼'}
          </span>
        )}
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 'bold' }}>
            {name}
          </h3>
          {!isCollapsed && (
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.75rem', color: '#666' }}>
              {role}
            </p>
          )}
        </div>
      </div>

      {/* State indicators - only show when not collapsed */}
      {!isCollapsed && (
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
      )}

      {/* Actions - only show when not collapsed */}
      {!isCollapsed && actions.length > 0 && (
        <div
          // Forces a persistent (non-overlay) scrollbar so the overflow is visible
          // and discoverable — see .always-show-scrollbar in App.css. The class is
          // global (App.css is loaded by the parent app), so no import here.
          className="always-show-scrollbar"
          style={{
            // This div scrolls INTERNALLY when the buttons exceed the space left in
            // the panel. The panel is locked to LANE_HEIGHT (it must match the
            // timeline lane height — the sidebar & timeline scroll in lockstep via
            // scrollTop, see App-multivendor handleSidebarScroll — so the panel
            // CANNOT grow to fit its buttons). That makes an inner scroller
            // unavoidable, nested inside the sidebar's own scroller.
            //
            // Getting that nested scroller to work reliably across browsers/machines
            // needs THREE things (missing any one made it scroll on some Macs but
            // not others):
            //   1. flex:1 + minHeight:0 — a flex item defaults to min-height:auto and
            //      refuses to shrink below its content, so without minHeight:0 it
            //      grows past the panel and never becomes an overflow container.
            //   2. An explicit bound (flexBasis:0) so the item's height is driven by
            //      the flex container, not its content — belt-and-suspenders with (1)
            //      for engines that still resolve `flex:1` against content height.
            //   3. overscrollBehavior:'contain' so wheel events consumed here don't
            //      bubble up and scroll the SIBLING sidebar instead — the ambiguity
            //      that let the outer scroller "win" on some machines.
            flex: '1 1 0',
            minHeight: 0,
            flexBasis: 0,
            overscrollBehavior: 'contain',
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
