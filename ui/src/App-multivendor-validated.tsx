import { useState, useCallback, useEffect, useLayoutEffect, useRef } from 'react'
import type { DemoState, ParticipantState } from './types'
import './App.css'
import { LANE_HEIGHT, LANE_HEIGHT_COLLAPSED, ACTOR_PANEL_WIDTH, PARTICIPANT_COLORS, PARTICIPANT_ROLES, INITIAL_X_POSITION, NODE_COLORS, NODE_WIDTH, NODE_HEIGHT, NODE_WIDTH_COLLAPSED, NODE_HEIGHT_COLLAPSED, getVendorNodeColors } from './constants'
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
} from './state/validated/actionFilters'
import * as finderActions from './actions/validated/finderActions'
import * as vendorActions from './actions/validated/vendorActions'
import * as caseActorActions from './actions/validated/caseActorActions'
import * as inviteActions from './actions/validated/inviteActions'
import * as externalActionHandlers from './actions/validated/externalActions'

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
      invitedVendors: new Set<string>(),
    }
  })

  const [hoveredEvent, setHoveredEvent] = useState<string | null>(null)
  const [stateHistory, setStateHistory] = useState<DemoState[]>([])
  const [eventLogCollapsed, setEventLogCollapsed] = useState(false)
  const [collapsedParticipants, setCollapsedParticipants] = useState<Set<string>>(new Set())
  const timelineScrollRef = useRef<HTMLDivElement>(null)
  const sidebarScrollRef = useRef<HTMLDivElement>(null)
  const scrollAdjustmentRef = useRef<{
    participantId: string
    wasCollapsed: boolean
    scrollTopBefore: number
    clickedPanelIndex: number
  } | null>(null)
  const isAdjustingScrollRef = useRef(false)

  // Toggle participant collapse
  const toggleParticipantCollapse = useCallback((participantId: string) => {
    if (!sidebarScrollRef.current) return

    // Find the button element and measure its viewport position
    const button = document.querySelector(`[data-collapse-button="${participantId}"]`)
    if (!button) {
      // Fallback: just toggle without scroll adjustment
      setCollapsedParticipants(prev => {
        const newSet = new Set(prev)
        if (newSet.has(participantId)) {
          newSet.delete(participantId)
        } else {
          newSet.add(participantId)
        }
        return newSet
      })
      return
    }

    const buttonRect = button.getBoundingClientRect()
    const buttonTopBeforeToggle = buttonRect.top

    // Store the info for useLayoutEffect to use after DOM update
    scrollAdjustmentRef.current = {
      participantId,
      wasCollapsed: collapsedParticipants.has(participantId),
      scrollTopBefore: sidebarScrollRef.current.scrollTop,
      clickedPanelIndex: buttonTopBeforeToggle, // Reuse this field to store button position
    }

    setCollapsedParticipants(prev => {
      const newSet = new Set(prev)
      if (newSet.has(participantId)) {
        newSet.delete(participantId)
      } else {
        newSet.add(participantId)
      }
      return newSet
    })
  }, [collapsedParticipants])

  // Adjust scroll after DOM updates but before paint
  useLayoutEffect(() => {
    if (!scrollAdjustmentRef.current || !sidebarScrollRef.current) return

    // Set flag to prevent scroll sync from interfering
    isAdjustingScrollRef.current = true

    const { participantId, scrollTopBefore, clickedPanelIndex: buttonTopBeforeToggle } = scrollAdjustmentRef.current

    // Measure the button's position after React has updated the DOM
    const button = document.querySelector(`[data-collapse-button="${participantId}"]`)
    if (!button) {
      scrollAdjustmentRef.current = null
      isAdjustingScrollRef.current = false
      return
    }

    const buttonRect = button.getBoundingClientRect()
    const buttonTopAfterToggle = buttonRect.top
    const delta = buttonTopAfterToggle - buttonTopBeforeToggle

    // Adjust scroll to compensate for the button movement
    if (Math.abs(delta) > 0.5) {
      const newScrollTop = Math.max(0, scrollTopBefore + delta)
      const maxScrollTop = sidebarScrollRef.current.scrollHeight - sidebarScrollRef.current.clientHeight
      const clampedScrollTop = Math.min(newScrollTop, maxScrollTop)

      sidebarScrollRef.current.scrollTop = clampedScrollTop
      // Also adjust timeline scroll to match
      if (timelineScrollRef.current) {
        timelineScrollRef.current.scrollTop = clampedScrollTop
      }
    }

    // Clear the adjustment request and flag
    scrollAdjustmentRef.current = null
    isAdjustingScrollRef.current = false
  }, [collapsedParticipants])

  // Calculate cumulative Y position for a participant based on collapsed states
  const getParticipantYPosition = useCallback((participant: ParticipantState, allParticipants: ParticipantState[]) => {
    const sortedParticipants = allParticipants
      .filter(p => p.visible)
      .sort((a, b) => a.laneIndex - b.laneIndex)

    let yPos = 0
    for (const p of sortedParticipants) {
      if (p.laneIndex >= participant.laneIndex) break
      yPos += collapsedParticipants.has(p.id) ? LANE_HEIGHT_COLLAPSED : LANE_HEIGHT
    }
    return yPos
  }, [collapsedParticipants])

  // Calculate total height of all lanes
  const getTotalHeight = useCallback((participants: ParticipantState[]) => {
    return participants
      .filter(p => p.visible)
      .reduce((total, p) => {
        return total + (collapsedParticipants.has(p.id) ? LANE_HEIGHT_COLLAPSED : LANE_HEIGHT)
      }, 0)
  }, [collapsedParticipants])

  // Get Y position for a specific lane index (for drawing arrows and nodes)
  const getYPositionForLane = useCallback((laneIndex: number, allParticipants: ParticipantState[]) => {
    const participant = allParticipants.find(p => p.laneIndex === laneIndex)
    if (!participant) {
      // Fallback to old calculation
      return laneIndex * LANE_HEIGHT + LANE_HEIGHT / 2
    }
    const baseYPos = getParticipantYPosition(participant, allParticipants)
    const laneHeight = collapsedParticipants.has(participant.id) ? LANE_HEIGHT_COLLAPSED : LANE_HEIGHT
    return baseYPos + laneHeight / 2
  }, [collapsedParticipants, getParticipantYPosition])

  // Synchronize vertical scrolling between sidebar and timeline
  const handleTimelineScroll = useCallback(() => {
    if (isAdjustingScrollRef.current) return // Don't sync during collapse adjustment
    if (timelineScrollRef.current && sidebarScrollRef.current) {
      sidebarScrollRef.current.scrollTop = timelineScrollRef.current.scrollTop
    }
  }, [])

  const handleSidebarScroll = useCallback(() => {
    if (isAdjustingScrollRef.current) return // Don't sync during collapse adjustment
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
      invitedVendors: new Set<string>(),
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
        } else if (actionId === 'finder-propose-revision') {
          newState = finderActions.handleFinderProposeRevision(newState)
        } else if (actionId === 'finder-accept-revision') {
          newState = finderActions.handleFinderAcceptRevision(newState)
        } else if (actionId === 'finder-reject-revision') {
          newState = finderActions.handleFinderRejectRevision(newState)
        } else if (actionId === 'finder-add-note') {
          newState = finderActions.handleFinderAddNote(newState)
        } else if (actionId === 'finder-notify-published') {
          newState = finderActions.handleFinderNotifyPublished(newState)
        } else if (actionId === 'finder-close-case') {
          newState = finderActions.handleFinderCloseCase(newState)
        } else if (actionId === 'finder-invite-vendor') {
          newState = inviteActions.handleInviteVendor(newState, 'finder')
        }
      } else if (participantId === 'caseactor') {
        if (actionId === 'propose-embargo') {
          newState = caseActorActions.handleProposeEmbargo(newState)
        } else if (actionId === 'caseactor-propose-revision') {
          newState = caseActorActions.handleCaseActorProposeRevision(newState)
        } else if (actionId === 'caseactor-accept-revision') {
          newState = caseActorActions.handleCaseActorAcceptRevision(newState)
        } else if (actionId === 'caseactor-reject-revision') {
          newState = caseActorActions.handleCaseActorRejectRevision(newState)
        }
      } else if (participantId.startsWith('vendor-')) {
        if (actionId === 'validate-report') {
          newState = vendorActions.handleValidateReport(newState, participantId)
        } else if (actionId === 'invalidate-report') {
          newState = vendorActions.handleInvalidateReport(newState, participantId)
        } else if (actionId === 'accept-report') {
          newState = vendorActions.handleAcceptReport(newState, participantId)
        } else if (actionId === 'defer-report') {
          newState = vendorActions.handleDeferReport(newState, participantId)
        } else if (actionId === 'accept-embargo') {
          newState = vendorActions.handleAcceptEmbargo(newState, participantId)
        } else if (actionId === 'reject-embargo') {
          newState = vendorActions.handleRejectEmbargo(newState, participantId)
        } else if (actionId === 'vendor-propose-revision') {
          newState = vendorActions.handleVendorProposeRevision(newState, participantId)
        } else if (actionId === 'vendor-accept-revision') {
          newState = vendorActions.handleVendorAcceptRevision(newState, participantId)
        } else if (actionId === 'vendor-reject-revision') {
          newState = vendorActions.handleVendorRejectRevision(newState, participantId)
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
        } else if (actionId === 'vendor-invite-next-vendor') {
          newState = inviteActions.handleInviteVendor(newState, participantId)
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

  // Debug: log participant lane indices when vendors are invited
  if (demoState.invitedVendors.size > 0) {
    console.log('Rendering with invited vendors:', Array.from(demoState.invitedVendors))
    console.log('All participants:', Array.from(demoState.participants.entries()).map(([id, p]) =>
      `${id}: lane ${p.laneIndex}, visible: ${p.visible}`
    ))
    console.log('Active lanes:', activeLanes.map(p => `${p.id}: lane ${p.laneIndex}`))
  }

  const minWidth = Math.max(2000, demoState.nextXPosition + 500)
  const externalActions = getExternalActions(demoState)

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
          {/* Render panels in lane order */}
          {Array.from(demoState.participants.values())
            .sort((a, b) => a.laneIndex - b.laneIndex)
            .filter(participant => participant.visible)
            .map((participant) => (
              <ActorPanel
                key={participant.id}
                participantId={participant.id}
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
                isCollapsed={collapsedParticipants.has(participant.id)}
                onToggleCollapse={() => toggleParticipantCollapse(participant.id)}
              />
            ))}
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
            <div style={{ position: 'relative', minWidth, height: getTotalHeight(activeLanes) }}>
              {/* Swimlane backgrounds for visible participants */}
              {activeLanes.map((participant) => {
                const yPos = getParticipantYPosition(participant, activeLanes)
                const height = collapsedParticipants.has(participant.id) ? LANE_HEIGHT_COLLAPSED : LANE_HEIGHT
                return (
                  <div
                    key={`lane-${participant.id}`}
                    style={{
                      position: 'absolute',
                      top: yPos,
                      // Stretch edge-to-edge instead of pinning to a fixed
                      // `width: minWidth`. With few events minWidth floors at
                      // 2000px, so on a wider viewport the fixed-width lane left a
                      // bare gap on the right. left:0/right:0 fills the parent in
                      // every case (parent width = max(viewport, minWidth)).
                      left: 0,
                      right: 0,
                      height,
                      background: participant.color,
                      opacity: 0.3,
                    }}
                  />
                )
              })}

              {/* SVG for nodes and edges */}
              <svg style={{ position: 'absolute', top: 0, left: 0, width: minWidth, height: getTotalHeight(activeLanes) }}>
                {/* Arrow marker definitions */}
                <defs>
                  <marker
                    id="arrowhead"
                    markerWidth="16"
                    markerHeight="16"
                    refX="14"
                    refY="5"
                    orient="auto"
                  >
                    <polygon points="0 0, 16 5, 0 10" fill="#666" />
                  </marker>
                  <marker
                    id="arrowhead-blue"
                    markerWidth="16"
                    markerHeight="16"
                    refX="14"
                    refY="5"
                    orient="auto"
                  >
                    <polygon points="0 0, 16 5, 0 10" fill="#BBDEFB" />
                  </marker>
                  <marker
                    id="arrowhead-purple"
                    markerWidth="16"
                    markerHeight="16"
                    refX="14"
                    refY="5"
                    orient="auto"
                  >
                    <polygon points="0 0, 16 5, 0 10" fill="#E1BEE7" />
                  </marker>
                  <marker
                    id="arrowhead-green"
                    markerWidth="16"
                    markerHeight="16"
                    refX="14"
                    refY="5"
                    orient="auto"
                  >
                    <polygon points="0 0, 16 5, 0 10" fill="#C8E6C9" />
                  </marker>
                  <marker
                    id="arrowhead-orange"
                    markerWidth="16"
                    markerHeight="16"
                    refX="14"
                    refY="5"
                    orient="auto"
                  >
                    <polygon points="0 0, 16 5, 0 10" fill="#FFE0B2" />
                  </marker>
                  {/* Small arrowheads for collapsed lanes */}
                  <marker
                    id="arrowhead-small"
                    markerWidth="8"
                    markerHeight="8"
                    refX="7"
                    refY="2.5"
                    orient="auto"
                  >
                    <polygon points="0 0, 8 2.5, 0 5" fill="#666" />
                  </marker>
                  <marker
                    id="arrowhead-blue-small"
                    markerWidth="8"
                    markerHeight="8"
                    refX="7"
                    refY="2.5"
                    orient="auto"
                  >
                    <polygon points="0 0, 8 2.5, 0 5" fill="#BBDEFB" />
                  </marker>
                  <marker
                    id="arrowhead-purple-small"
                    markerWidth="8"
                    markerHeight="8"
                    refX="7"
                    refY="2.5"
                    orient="auto"
                  >
                    <polygon points="0 0, 8 2.5, 0 5" fill="#E1BEE7" />
                  </marker>
                  <marker
                    id="arrowhead-green-small"
                    markerWidth="8"
                    markerHeight="8"
                    refX="7"
                    refY="2.5"
                    orient="auto"
                  >
                    <polygon points="0 0, 8 2.5, 0 5" fill="#C8E6C9" />
                  </marker>
                  <marker
                    id="arrowhead-orange-small"
                    markerWidth="8"
                    markerHeight="8"
                    refX="7"
                    refY="2.5"
                    orient="auto"
                  >
                    <polygon points="0 0, 8 2.5, 0 5" fill="#FFE0B2" />
                  </marker>
                  {/* Arrowheads for vendors 3, 4, 5 */}
                  <marker
                    id="arrowhead-yellow"
                    markerWidth="16"
                    markerHeight="16"
                    refX="14"
                    refY="5"
                    orient="auto"
                  >
                    <polygon points="0 0, 16 5, 0 10" fill="#FFE082" />
                  </marker>
                  <marker
                    id="arrowhead-lightorange"
                    markerWidth="16"
                    markerHeight="16"
                    refX="14"
                    refY="5"
                    orient="auto"
                  >
                    <polygon points="0 0, 16 5, 0 10" fill="#FFCCBC" />
                  </marker>
                  <marker
                    id="arrowhead-lavender"
                    markerWidth="16"
                    markerHeight="16"
                    refX="14"
                    refY="5"
                    orient="auto"
                  >
                    <polygon points="0 0, 16 5, 0 10" fill="#E1BEE7" />
                  </marker>
                </defs>

                {/* Draw edges */}
                {demoState.timelineEvents.map((event) => {
                  if (event.causedBy) {
                    const causeEvent = demoState.timelineEvents.find((e) => e.id === event.causedBy)
                    if (causeEvent) {
                      const allParticipants = Array.from(demoState.participants.values())
                      const y1 = getYPositionForLane(causeEvent.lane, allParticipants)
                      const y2 = getYPositionForLane(event.lane, allParticipants)

                      // Find participants for source and target
                      const sourceParticipant = allParticipants.find(p => p.laneIndex === causeEvent.lane)
                      const targetParticipant = allParticipants.find(p => p.laneIndex === event.lane)

                      // Use collapsed node height if participant is collapsed
                      const sourceCollapsed = sourceParticipant ? collapsedParticipants.has(sourceParticipant.id) : false
                      const targetCollapsed = targetParticipant ? collapsedParticipants.has(targetParticipant.id) : false

                      const sourceRectHalfHeight = sourceCollapsed ? NODE_HEIGHT_COLLAPSED / 2 : NODE_HEIGHT / 2
                      const targetRectHalfHeight = targetCollapsed ? NODE_HEIGHT_COLLAPSED / 2 : NODE_HEIGHT / 2

                      const direction = y2 > y1 ? 1 : -1  // downward or upward
                      const adjustedY1 = y1 + (sourceRectHalfHeight * direction)
                      const adjustedY2 = y2 - (targetRectHalfHeight * direction)

                      // Determine arrow color and marker based on target participant (consequence node color)
                      // No arrowheads when target is collapsed
                      let arrowColor: string
                      let arrowMarker: string
                      if (targetParticipant) {
                        if (targetParticipant.id === 'finder') {
                          arrowColor = '#BBDEFB'
                          arrowMarker = targetCollapsed ? '' : 'url(#arrowhead-blue)'
                        } else if (targetParticipant.id === 'vendor-1') {
                          arrowColor = '#E1BEE7'
                          arrowMarker = targetCollapsed ? '' : 'url(#arrowhead-purple)'
                        } else if (targetParticipant.id === 'vendor-2') {
                          arrowColor = '#C8E6C9'
                          arrowMarker = targetCollapsed ? '' : 'url(#arrowhead-green)'
                        } else if (targetParticipant.id === 'vendor-3') {
                          arrowColor = '#FFE082'
                          arrowMarker = targetCollapsed ? '' : 'url(#arrowhead-yellow)'
                        } else if (targetParticipant.id === 'vendor-4') {
                          arrowColor = '#FFCCBC'
                          arrowMarker = targetCollapsed ? '' : 'url(#arrowhead-lightorange)'
                        } else if (targetParticipant.id === 'vendor-5') {
                          arrowColor = '#E1BEE7'
                          arrowMarker = targetCollapsed ? '' : 'url(#arrowhead-lavender)'
                        } else if (targetParticipant.id === 'caseactor') {
                          arrowColor = '#FFE0B2'
                          arrowMarker = targetCollapsed ? '' : 'url(#arrowhead-orange)'
                        } else {
                          // For vendors beyond 5, use gray as fallback
                          arrowColor = '#999'
                          arrowMarker = targetCollapsed ? '' : ''
                        }
                      } else {
                        arrowColor = '#999'
                        arrowMarker = ''
                      }

                      // Use thinner stroke for collapsed target
                      const strokeWidth = targetCollapsed ? 1.5 : 3
                      const strokeDasharray = targetCollapsed ? "3,3" : "6,6"

                      return (
                        <line
                          key={`edge-${event.id}`}
                          x1={causeEvent.x}
                          y1={adjustedY1}
                          x2={event.x}
                          y2={adjustedY2}
                          stroke={arrowColor}
                          strokeWidth={strokeWidth}
                          strokeDasharray={strokeDasharray}
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

                  const allParticipants = Array.from(demoState.participants.values())
                  const participant = allParticipants.find(p => p.laneIndex === event.lane)

                  // Use collapsed node width if participant is collapsed
                  const isCollapsed = participant ? collapsedParticipants.has(participant.id) : false
                  const rectHalfWidth = isCollapsed ? NODE_WIDTH_COLLAPSED / 2 : NODE_WIDTH / 2

                  const y = getYPositionForLane(event.lane, allParticipants)
                  const startX = event.x + rectHalfWidth // Start from edge of rectangle
                  const endX = nextInLane.x - rectHalfWidth // End at edge of next rectangle

                  // Keep regular arrowhead for horizontal arrows even in collapsed lanes
                  const arrowMarker = 'url(#arrowhead)'
                  const strokeWidth = isCollapsed ? 1.5 : 3

                  return (
                    <g key={`arrow-horizontal-${event.id}`}>
                      <line
                        x1={startX}
                        y1={y}
                        x2={endX}
                        y2={y}
                        stroke="#666"
                        strokeWidth={strokeWidth}
                        markerEnd={arrowMarker}
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

                  // Check if this participant's lane is collapsed
                  const isCollapsed = participant ? collapsedParticipants.has(participant.id) : false

                  // Calculate Y position based on collapsed state
                  let yPos: number
                  if (participant) {
                    const baseYPos = getParticipantYPosition(participant, allParticipants)
                    const laneHeight = isCollapsed ? LANE_HEIGHT_COLLAPSED : LANE_HEIGHT
                    yPos = baseYPos + laneHeight / 2
                  } else {
                    // Fallback to old calculation if participant not found
                    yPos = event.lane * LANE_HEIGHT + LANE_HEIGHT / 2
                  }

                  // Determine node color based on participant and event type
                  let fillColor: string
                  if (participant) {
                    let colors: { decision: string; decisionHover: string; consequence: string; consequenceHover: string }

                    // Check if participant is a vendor (vendor-1, vendor-2, vendor-3, etc.)
                    if (participant.id.startsWith('vendor-')) {
                      const vendorNumber = parseInt(participant.id.split('-')[1], 10)
                      colors = getVendorNodeColors(vendorNumber)
                    } else {
                      // Use base colors for non-vendor participants (finder, caseactor)
                      const colorKey = participant.id as keyof typeof NODE_COLORS
                      colors = NODE_COLORS[colorKey] || NODE_COLORS.finder
                    }

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
                      yPosition={yPos}
                      getCauseEventY={(eventId) => {
                        const causeEvent = demoState.timelineEvents.find(e => e.id === eventId)
                        if (!causeEvent) return 0
                        return getYPositionForLane(causeEvent.lane, allParticipants)
                      }}
                      isCollapsed={isCollapsed}
                      onMouseEnter={() => setHoveredEvent(event.id)}
                      onMouseLeave={() => setHoveredEvent(null)}
                    />
                  )
                })}
              </svg>

              {/* Hover tooltip - only show for non-collapsed nodes */}
              {hoveredEvent &&
                (() => {
                  const event = demoState.timelineEvents.find((e) => e.id === hoveredEvent)
                  if (!event) return null

                  // Find the participant to check if collapsed
                  const allParticipants = Array.from(demoState.participants.values())
                  const participant = allParticipants.find(p => p.laneIndex === event.lane)
                  const isCollapsed = participant ? collapsedParticipants.has(participant.id) : false

                  // Don't show detailed tooltip for collapsed nodes (they have their own inline tooltip)
                  if (isCollapsed) return null

                  // Calculate Y position based on collapsed state
                  const y = getYPositionForLane(event.lane, allParticipants)

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
