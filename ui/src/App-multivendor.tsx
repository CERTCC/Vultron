import { useState, useCallback, useEffect, useRef } from 'react'
import type { DemoState, ParticipantState } from './types'
import './App.css'
import { LANE_HEIGHT, ACTOR_PANEL_WIDTH, PARTICIPANT_COLORS, PARTICIPANT_ROLES, INITIAL_X_POSITION, NODE_COLORS } from './constants'
import { ActorPanel, AnimatedNode } from './components'
import {
  getActiveLanes,
  getTotalLaneCount,
} from './state/participantHelpers'
import {
  getFinderActions,
  getVendorActions,
  getCaseActorActions,
  getExternalActions,
} from './state/actionFilters'
import * as finderActions from './actions/finderActions'
import * as vendorActions from './actions/vendorActions'
import * as caseActorActions from './actions/caseActorActions'
import * as inviteActions from './actions/inviteActions'
import * as externalActionHandlers from './actions/externalActions'

function App() {
  const [demoState, setDemoState] = useState<DemoState>(() => {
    const participants = new Map<string, ParticipantState>()

    // Initialize Finder
    participants.set('finder', {
      id: 'finder',
      name: 'Finder',
      role: PARTICIPANT_ROLES.finder,
      color: PARTICIPANT_COLORS.finder,
      rmState: 'START',
      vfdState: 'vfd',
      embargoAccepted: false,
      hasPublished: false,
      hasClosed: false,
      visible: true,
      laneIndex: 0,
    })

    // Initialize first Vendor
    participants.set('vendor-1', {
      id: 'vendor-1',
      name: 'Vendor',
      role: PARTICIPANT_ROLES.vendor,
      color: PARTICIPANT_COLORS.vendor1,
      rmState: 'START',
      vfdState: 'vfd',
      embargoAccepted: false,
      hasPublished: false,
      hasClosed: false,
      visible: false,
      laneIndex: 1,
    })

    // Initialize CaseActor
    participants.set('caseactor', {
      id: 'caseactor',
      name: 'Case Actor',
      role: PARTICIPANT_ROLES.caseactor,
      color: PARTICIPANT_COLORS.caseactor,
      rmState: 'N/A',
      vfdState: 'N/A',
      embargoAccepted: false,
      hasPublished: false,
      hasClosed: false,
      visible: false,
      laneIndex: 2,
    })

    return {
      phase: 'start',
      participants,
      emState: 'NONE',
      pxaState: 'pxa',
      timelineEvents: [],
      eventLog: [],
      nextXPosition: INITIAL_X_POSITION,
      secondVendorInvited: false,
      secondVendorAccepted: false,
    }
  })

  const [hoveredEvent, setHoveredEvent] = useState<string | null>(null)
  const [stateHistory, setStateHistory] = useState<DemoState[]>([])
  const [eventLogCollapsed, setEventLogCollapsed] = useState(false)
  const timelineScrollRef = useRef<HTMLDivElement>(null)
  const sidebarScrollRef = useRef<HTMLDivElement>(null)

  // Synchronize vertical scrolling between sidebar and timeline
  const handleTimelineScroll = useCallback(() => {
    if (timelineScrollRef.current && sidebarScrollRef.current) {
      sidebarScrollRef.current.scrollTop = timelineScrollRef.current.scrollTop
    }
  }, [])

  const handleSidebarScroll = useCallback(() => {
    if (sidebarScrollRef.current && timelineScrollRef.current) {
      timelineScrollRef.current.scrollTop = sidebarScrollRef.current.scrollTop
    }
  }, [])

  // Auto-scroll to show the most recent event
  useEffect(() => {
    if (timelineScrollRef.current && demoState.timelineEvents.length > 0) {
      const decisionCount = demoState.timelineEvents.filter((e) => e.type === 'decision').length

      if (decisionCount > 4) {
        const mostRecentEvent = demoState.timelineEvents[demoState.timelineEvents.length - 1]
        const scrollLeft = mostRecentEvent.x - 200
        timelineScrollRef.current.scrollTo({
          left: Math.max(0, scrollLeft),
          behavior: 'smooth',
        })
      }
    }
  }, [demoState.timelineEvents.length])

  // Undo handler
  const handleUndo = useCallback(() => {
    if (stateHistory.length === 0) return

    const previousState = stateHistory[stateHistory.length - 1]
    const newHistory = stateHistory.slice(0, -1)

    setDemoState(previousState)
    setStateHistory(newHistory)
  }, [stateHistory])

  // Start Over handler
  const handleStartOver = useCallback(() => {
    const participants = new Map<string, ParticipantState>()

    participants.set('finder', {
      id: 'finder',
      name: 'Finder',
      role: PARTICIPANT_ROLES.finder,
      color: PARTICIPANT_COLORS.finder,
      rmState: 'START',
      vfdState: 'vfd',
      embargoAccepted: false,
      hasPublished: false,
      hasClosed: false,
      visible: true,
      laneIndex: 0,
    })

    participants.set('vendor-1', {
      id: 'vendor-1',
      name: 'Vendor',
      role: PARTICIPANT_ROLES.vendor,
      color: PARTICIPANT_COLORS.vendor1,
      rmState: 'START',
      vfdState: 'vfd',
      embargoAccepted: false,
      hasPublished: false,
      hasClosed: false,
      visible: false,
      laneIndex: 1,
    })

    participants.set('caseactor', {
      id: 'caseactor',
      name: 'Case Actor',
      role: PARTICIPANT_ROLES.caseactor,
      color: PARTICIPANT_COLORS.caseactor,
      rmState: 'N/A',
      vfdState: 'N/A',
      embargoAccepted: false,
      hasPublished: false,
      hasClosed: false,
      visible: false,
      laneIndex: 2,
    })

    setDemoState({
      phase: 'start',
      participants,
      emState: 'NONE',
      pxaState: 'pxa',
      timelineEvents: [],
      eventLog: [],
      nextXPosition: INITIAL_X_POSITION,
      secondVendorInvited: false,
      secondVendorAccepted: false,
    })
    setStateHistory([])
  }, [])

  // Main action handler
  const handleAction = useCallback(
    (participantId: string, actionId: string) => {
      console.log(`Action: ${participantId} -> ${actionId}`)

      // Save current state for undo
      setStateHistory((prev) => [...prev, demoState])

      let newState = demoState

      // Route to appropriate action handler
      if (participantId === 'finder') {
        if (actionId === 'submit-report') {
          newState = finderActions.handleSubmitReport(newState)
        } else if (actionId === 'finder-accept-embargo') {
          newState = finderActions.handleFinderAcceptEmbargo(newState)
        } else if (actionId === 'finder-reject-embargo') {
          newState = finderActions.handleFinderRejectEmbargo(newState)
        } else if (actionId === 'finder-add-note') {
          newState = finderActions.handleFinderAddNote(newState)
        } else if (actionId === 'finder-notify-published') {
          newState = finderActions.handleFinderNotifyPublished(newState)
        } else if (actionId === 'finder-close-case') {
          newState = finderActions.handleFinderCloseCase(newState)
        } else if (actionId === 'finder-invite-vendor') {
          newState = inviteActions.handleInviteSecondVendor(newState, 'finder')
        }
      } else if (participantId === 'vendor-2-pending') {
        console.log('Handling vendor-2-pending action:', actionId)
        if (actionId === 'accept-invite') {
          console.log('Calling handleAcceptSecondVendorInvite')
          newState = inviteActions.handleAcceptSecondVendorInvite(newState)
          console.log('After handleAcceptSecondVendorInvite, vendor-2 visible:', newState.participants.get('vendor-2')?.visible)
        } else if (actionId === 'reject-invite') {
          newState = inviteActions.handleRejectSecondVendorInvite(newState)
        }
      } else if (participantId === 'caseactor') {
        if (actionId === 'propose-embargo') {
          newState = caseActorActions.handleProposeEmbargo(newState)
        }
      } else if (participantId.startsWith('vendor-')) {
        if (actionId === 'validate-report') {
          newState = vendorActions.handleValidateReport(newState, participantId)
        } else if (actionId === 'invalidate-report') {
          newState = vendorActions.handleInvalidateReport(newState, participantId)
        } else if (actionId === 'accept-embargo') {
          newState = vendorActions.handleAcceptEmbargo(newState, participantId)
        } else if (actionId === 'reject-embargo') {
          newState = vendorActions.handleRejectEmbargo(newState, participantId)
        } else if (actionId === 'notify-fix-ready') {
          newState = vendorActions.handleNotifyFixReady(newState, participantId)
        } else if (actionId === 'notify-fix-deployed') {
          newState = vendorActions.handleNotifyFixDeployed(newState, participantId)
        } else if (actionId === 'vendor-notify-published') {
          newState = vendorActions.handleVendorNotifyPublished(newState, participantId)
        } else if (actionId === 'vendor-reply-note') {
          newState = vendorActions.handleVendorReplyNote(newState, participantId)
        } else if (actionId === 'vendor-close-case') {
          newState = vendorActions.handleVendorCloseCase(newState, participantId)
        } else if (actionId === 'vendor-invite-second-vendor') {
          newState = inviteActions.handleInviteSecondVendor(newState, participantId)
        }
      } else if (participantId === 'external') {
        if (actionId === 'trigger-exploit') {
          newState = externalActionHandlers.handleTriggerExploit(newState)
        } else if (actionId === 'trigger-attacks') {
          newState = externalActionHandlers.handleTriggerAttacks(newState)
        }
      }

      setDemoState(newState)
    },
    [demoState]
  )

  const activeLanes = getActiveLanes(demoState)
  const totalLanes = getTotalLaneCount(demoState)

  // Debug: log participant lane indices when vendor-2 is invited
  if (demoState.secondVendorInvited) {
    console.log('Rendering with secondVendorInvited=true')
    console.log('All participants:', Array.from(demoState.participants.entries()).map(([id, p]) =>
      `${id}: lane ${p.laneIndex}, visible: ${p.visible}`
    ))
    console.log('Active lanes:', activeLanes.map(p => `${p.id}: lane ${p.laneIndex}`))
  }

  // Calculate max lane index to ensure SVG height accounts for all lanes with events
  const maxLaneIndex = Math.max(
    ...Array.from(demoState.participants.values()).map(p => p.laneIndex),
    ...demoState.timelineEvents.map(e => e.lane)
  )
  const svgLaneCount = maxLaneIndex + 1  // +1 because indices are 0-based
  const minWidth = Math.max(2000, demoState.nextXPosition + 500)
  const externalActions = getExternalActions(demoState)

  // Check if vendor-2 invite is pending
  const vendor2Pending = demoState.secondVendorInvited && !demoState.secondVendorAccepted

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header with buttons in upper right */}
      <div style={{ padding: '1rem', background: '#f5f5f5', borderBottom: '1px solid #ddd', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', color: '#666' }}>
            Vultron Interactive Demo (Multi-Vendor)
          </h1>
          <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.9rem', color: '#666' }}>
            CERT/CC — Research Prototype | Click actions on actors to progress through the demo
          </p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          {/* External event triggers */}
          {externalActions.length > 0 && (
            <div style={{ display: 'flex', gap: '0.5rem', marginRight: '1rem', paddingRight: '1rem', borderRight: '2px solid #ddd' }}>
              <span style={{ fontSize: '0.85rem', color: '#666', alignSelf: 'center', fontWeight: 'bold' }}>
                External Events:
              </span>
              {externalActions.map((action) => {
                const isExploit = action.id === 'trigger-exploit'
                const buttonColor = isExploit ? '#ff5722' : '#d32f2f'
                const emoji = isExploit ? '⚠️' : '🔥'
                const shortLabel = isExploit ? 'Exploit' : 'Attacks'

                return (
                  <button
                    key={action.id}
                    onClick={() => handleAction('external', action.id)}
                    disabled={!action.enabled}
                    title={action.description}
                    style={{
                      padding: '0.5rem 1rem',
                      fontSize: '0.85rem',
                      background: action.enabled ? buttonColor : '#ccc',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: action.enabled ? 'pointer' : 'not-allowed',
                      fontWeight: 'bold',
                      opacity: action.enabled ? 1 : 0.5,
                    }}
                  >
                    {emoji} {shortLabel}
                  </button>
                )
              })}
            </div>
          )}
          <button
            onClick={handleStartOver}
            style={{
              padding: '0.75rem 1.5rem',
              fontSize: '0.9rem',
              background: '#2196F3',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: 'bold',
            }}
          >
            ↺ Start Over
          </button>
          <button
            onClick={handleUndo}
            disabled={stateHistory.length === 0}
            style={{
              padding: '0.75rem 1.5rem',
              fontSize: '0.9rem',
              background: stateHistory.length > 0 ? '#ff9800' : '#ccc',
              color: stateHistory.length > 0 ? 'white' : '#666',
              border: 'none',
              borderRadius: '4px',
              cursor: stateHistory.length > 0 ? 'pointer' : 'not-allowed',
              fontWeight: 'bold',
            }}
          >
            ← Go Back
          </button>
        </div>
      </div>

      {/* Main content area with sidebar and timeline */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left sidebar - Actor panels */}
        <div
          ref={sidebarScrollRef}
          onScroll={handleSidebarScroll}
          style={{
            width: ACTOR_PANEL_WIDTH,
            borderRight: '2px solid #ccc',
            display: 'flex',
            flexDirection: 'column',
            flexShrink: 0,
            overflowY: 'auto',
          }}
        >
          {/* Render panels in lane order, inserting pending vendor-2 at lane 2 */}
          {Array.from(demoState.participants.values())
            .sort((a, b) => a.laneIndex - b.laneIndex)
            .map((participant) => {
              // Skip vendor-2 if not visible - we'll render it separately as pending
              if (participant.id === 'vendor-2' && !participant.visible) {
                // Render pending vendor-2 panel at its correct position in lane order
                if (vendor2Pending) {
                  return (
                    <ActorPanel
                      key="vendor-2-pending"
                      name="Vendor 2 (Invited)"
                      role="VENDOR (pending)"
                      color={PARTICIPANT_COLORS.vendor2}
                      rmState="RECEIVED"
                      vfdState="vfd"
                      pxaState={undefined}
                      actions={[
                        {
                          id: 'accept-invite',
                          label: 'Accept Invitation',
                          description: 'Accept the invitation and receive the vulnerability report',
                          enabled: true,
                        },
                        {
                          id: 'reject-invite',
                          label: 'Reject Invitation',
                          description: 'Decline the invitation',
                          enabled: true,
                        },
                      ]}
                      onActionClick={(actionId) => handleAction('vendor-2-pending', actionId)}
                    />
                  )
                }
                return null
              }

              // Only render visible participants
              if (!participant.visible) return null

              return (
                <ActorPanel
                  key={participant.id}
                  name={participant.name}
                  role={participant.role}
                  color={participant.color}
                  rmState={participant.rmState}
                  emState={demoState.emState}
                  vfdState={participant.id.startsWith('vendor-') && participant.vfdState !== 'N/A' ? participant.vfdState : undefined}
                  pxaState={participant.id === 'caseactor' ? demoState.pxaState : undefined}
                  actions={
                    participant.id === 'finder'
                      ? getFinderActions(demoState)
                      : participant.id.startsWith('vendor-')
                      ? getVendorActions(demoState, participant.id)
                      : participant.id === 'caseactor'
                      ? getCaseActorActions(demoState)
                      : []
                  }
                  onActionClick={(actionId) => handleAction(participant.id, actionId)}
                />
              )
            })}
        </div>

        {/* Right side - Timeline visualization */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Swimlane timeline */}
          <div
            ref={timelineScrollRef}
            onScroll={handleTimelineScroll}
            style={{
              flex: 1,
              overflowX: 'auto',
              overflowY: 'auto',
              position: 'relative',
            }}
          >
            <div style={{ position: 'relative', minWidth, height: LANE_HEIGHT * svgLaneCount }}>
              {/* Swimlane backgrounds for visible participants */}
              {activeLanes.map((participant) => (
                <div
                  key={`lane-${participant.id}`}
                  style={{
                    position: 'absolute',
                    top: participant.laneIndex * LANE_HEIGHT,
                    left: 0,
                    width: minWidth,
                    height: LANE_HEIGHT,
                    background: participant.color,
                    opacity: 0.3,
                  }}
                />
              ))}

              {/* Pending vendor-2 swimlane (dimmed) */}
              {vendor2Pending && (
                <div
                  key="lane-vendor-2-pending"
                  style={{
                    position: 'absolute',
                    top: 2 * LANE_HEIGHT,  // lane 2
                    left: 0,
                    width: minWidth,
                    height: LANE_HEIGHT,
                    background: PARTICIPANT_COLORS.vendor2,
                    opacity: 0.15,  // More transparent to show it's pending
                    borderTop: '2px dashed rgba(76, 175, 80, 0.5)',
                    borderBottom: '2px dashed rgba(76, 175, 80, 0.5)',
                  }}
                />
              )}

              {/* SVG for nodes and edges */}
              <svg style={{ position: 'absolute', top: 0, left: 0, width: minWidth, height: LANE_HEIGHT * svgLaneCount }}>
                {/* Arrow marker definitions */}
                <defs>
                  <marker
                    id="arrowhead"
                    markerWidth="10"
                    markerHeight="10"
                    refX="9"
                    refY="3"
                    orient="auto"
                  >
                    <polygon points="0 0, 10 3, 0 6" fill="#666" />
                  </marker>
                  <marker
                    id="arrowhead-blue"
                    markerWidth="10"
                    markerHeight="10"
                    refX="9"
                    refY="3"
                    orient="auto"
                  >
                    <polygon points="0 0, 10 3, 0 6" fill="#BBDEFB" />
                  </marker>
                  <marker
                    id="arrowhead-purple"
                    markerWidth="10"
                    markerHeight="10"
                    refX="9"
                    refY="3"
                    orient="auto"
                  >
                    <polygon points="0 0, 10 3, 0 6" fill="#E1BEE7" />
                  </marker>
                  <marker
                    id="arrowhead-green"
                    markerWidth="10"
                    markerHeight="10"
                    refX="9"
                    refY="3"
                    orient="auto"
                  >
                    <polygon points="0 0, 10 3, 0 6" fill="#C8E6C9" />
                  </marker>
                  <marker
                    id="arrowhead-orange"
                    markerWidth="10"
                    markerHeight="10"
                    refX="9"
                    refY="3"
                    orient="auto"
                  >
                    <polygon points="0 0, 10 3, 0 6" fill="#FFE0B2" />
                  </marker>
                </defs>

                {/* Draw edges */}
                {demoState.timelineEvents.map((event) => {
                  if (event.causedBy) {
                    const causeEvent = demoState.timelineEvents.find((e) => e.id === event.causedBy)
                    if (causeEvent) {
                      const y1 = causeEvent.lane * LANE_HEIGHT + LANE_HEIGHT / 2
                      const y2 = event.lane * LANE_HEIGHT + LANE_HEIGHT / 2

                      // Adjust endpoints to account for rectangle height (70px / 2 = 35px from center)
                      const rectHalfHeight = 35
                      const direction = y2 > y1 ? 1 : -1  // downward or upward
                      const adjustedY1 = y1 + (rectHalfHeight * direction)
                      const adjustedY2 = y2 - (rectHalfHeight * direction)

                      // Find the participant for the TARGET (consequence) event
                      const targetParticipant = activeLanes.find(p => p.laneIndex === event.lane)

                      // Determine arrow color based on target participant (consequence node color)
                      let arrowColor: string
                      let arrowMarker: string
                      if (targetParticipant) {
                        if (targetParticipant.id === 'finder') {
                          arrowColor = '#BBDEFB'
                          arrowMarker = 'url(#arrowhead-blue)'
                        } else if (targetParticipant.id === 'vendor-1') {
                          arrowColor = '#E1BEE7'
                          arrowMarker = 'url(#arrowhead-purple)'
                        } else if (targetParticipant.id === 'vendor-2') {
                          arrowColor = '#C8E6C9'
                          arrowMarker = 'url(#arrowhead-green)'
                        } else if (targetParticipant.id === 'caseactor') {
                          arrowColor = '#FFE0B2'
                          arrowMarker = 'url(#arrowhead-orange)'
                        } else {
                          arrowColor = '#999'
                          arrowMarker = ''
                        }
                      } else {
                        arrowColor = '#999'
                        arrowMarker = ''
                      }

                      return (
                        <line
                          key={`edge-${event.id}`}
                          x1={causeEvent.x}
                          y1={adjustedY1}
                          x2={event.x}
                          y2={adjustedY2}
                          stroke={arrowColor}
                          strokeWidth="2"
                          strokeDasharray="5,5"
                          markerEnd={arrowMarker}
                        />
                      )
                    }
                  }
                  return null
                })}

                {/* Draw horizontal flow arrows within each lane */}
                {demoState.timelineEvents.map((event) => {
                  // Find next node in the SAME lane with a DIFFERENT x position
                  const eventIdx = demoState.timelineEvents.indexOf(event)
                  const nextInLane = demoState.timelineEvents.find(
                    (e, i) => i > eventIdx && e.lane === event.lane && e.x !== event.x
                  )
                  if (!nextInLane) return null

                  // Only draw arrow if it represents an enabling relationship:
                  // - consequence → decision (consequence enables actor to make decision)
                  // - decision → decision (one decision leads to another)
                  // Don't draw:
                  // - decision → consequence (caused by other actor, shown by vertical arrow)
                  // - consequence → consequence (no direct enabling)
                  const shouldDrawArrow =
                    (event.type === 'consequence' && nextInLane.type === 'decision') ||
                    (event.type === 'decision' && nextInLane.type === 'decision')

                  if (!shouldDrawArrow) return null

                  const y = event.lane * LANE_HEIGHT + LANE_HEIGHT / 2
                  const startX = event.x + 60 // Start from edge of rectangle (width/2)
                  const endX = nextInLane.x - 60 // End at edge of next rectangle

                  return (
                    <g key={`arrow-horizontal-${event.id}`}>
                      <line
                        x1={startX}
                        y1={y}
                        x2={endX}
                        y2={y}
                        stroke="#666"
                        strokeWidth={2}
                        markerEnd="url(#arrowhead)"
                      />
                    </g>
                  )
                })}

                {/* Draw timeline nodes */}
                {demoState.timelineEvents.map((event) => {
                  const isHovered = hoveredEvent === event.id
                  const isDecision = event.type === 'decision'

                  // Find which participant this event's lane belongs to - search ALL participants, not just visible
                  const allParticipants = Array.from(demoState.participants.values())
                  const participant = allParticipants.find(p => p.laneIndex === event.lane)

                  // Determine node color based on participant and event type
                  let fillColor: string
                  if (participant) {
                    // Map participant ID to color key (vendor-1 → vendor1, vendor-2 → vendor2)
                    let colorKey: keyof typeof NODE_COLORS
                    if (participant.id === 'vendor-1') {
                      colorKey = 'vendor1'
                    } else if (participant.id === 'vendor-2') {
                      colorKey = 'vendor2'
                    } else {
                      colorKey = participant.id as keyof typeof NODE_COLORS
                    }

                    const colors = NODE_COLORS[colorKey] || NODE_COLORS.finder

                    if (isDecision) {
                      fillColor = isHovered ? colors.decisionHover : colors.decision
                    } else {
                      fillColor = isHovered ? colors.consequenceHover : colors.consequence
                    }
                  } else {
                    // Fallback colors if participant not found
                    fillColor = isDecision ? '#1976d2' : '#BBDEFB'
                  }

                  return (
                    <AnimatedNode
                      key={event.id}
                      event={event}
                      allEvents={demoState.timelineEvents}
                      isHovered={isHovered}
                      fillColor={fillColor}
                      onMouseEnter={() => setHoveredEvent(event.id)}
                      onMouseLeave={() => setHoveredEvent(null)}
                    />
                  )
                })}
              </svg>

              {/* Hover tooltip */}
              {hoveredEvent &&
                (() => {
                  const event = demoState.timelineEvents.find((e) => e.id === hoveredEvent)
                  if (!event) return null
                  const y = event.lane * LANE_HEIGHT + LANE_HEIGHT / 2
                  return (
                    <div
                      style={{
                        position: 'absolute',
                        top: y + 50,
                        left: event.x - 100,
                        background: 'white',
                        border: '2px solid #333',
                        borderRadius: '8px',
                        padding: '0.75rem',
                        boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                        zIndex: 1000,
                        minWidth: '200px',
                        maxWidth: '300px',
                      }}
                    >
                      <div style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>{event.label}</div>
                      <div style={{ fontSize: '0.75rem', color: '#666' }}>
                        {event.consequences.map((c, i) => (
                          <div key={i} style={{ marginBottom: '0.25rem' }}>
                            • {c}
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })()}
            </div>
          </div>
        </div>
      </div>

      {/* Event log footer */}
      <div
        style={{
          borderTop: '2px solid #ccc',
          background: '#f9f9f9',
          transition: 'max-height 0.3s ease',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '0.5rem 1rem',
            cursor: 'pointer',
            userSelect: 'none',
          }}
          onClick={() => setEventLogCollapsed(!eventLogCollapsed)}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem' }}>{eventLogCollapsed ? '▶' : '▼'}</span>
            <h3 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 'bold' }}>Event Log</h3>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#666' }}>
            <strong>Current Phase:</strong> {demoState.phase} | <strong>Active Participants:</strong> {totalLanes}
          </div>
        </div>
        {!eventLogCollapsed && (
          <div style={{
            padding: '0 1rem 0.5rem 1rem',
            maxHeight: '150px',
            overflowY: 'auto',
          }}>
            <div style={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>
              {demoState.eventLog.map((log, i) => (
                <div key={i} style={{ marginBottom: '0.25rem' }}>
                  {log}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
