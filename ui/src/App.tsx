import { useState, useCallback, useEffect, useRef } from 'react'
import './App.css'

// Define swimlane layout
const LANE_HEIGHT = 280
const ACTOR_PANEL_WIDTH = 300

// Animated node component for consequence nodes
interface AnimatedNodeProps {
  event: TimelineEvent
  allEvents: TimelineEvent[]
  isHovered: boolean
  fillColor: string
  onMouseEnter: () => void
  onMouseLeave: () => void
}

function AnimatedNode({ event, allEvents, isHovered, fillColor, onMouseEnter, onMouseLeave }: AnimatedNodeProps) {
  const gRef = useRef<SVGGElement>(null)
  const isDecision = event.type === 'decision'
  const y = event.lane * LANE_HEIGHT + LANE_HEIGHT / 2
  const width = isHovered ? 130 : 120
  const height = isHovered ? 77 : 70
  const rectX = event.x - width / 2
  const rectY = y - height / 2

  useEffect(() => {
    // Only animate if this is a consequence node that was just created (within 100ms)
    const isNewEvent = event.timestamp && (Date.now() - event.timestamp < 100)

    if (!isDecision && event.causedBy && isNewEvent && gRef.current) {
      const causeEvent = allEvents.find(e => e.id === event.causedBy)
      if (causeEvent) {
        const causeY = causeEvent.lane * LANE_HEIGHT + LANE_HEIGHT / 2
        const offsetY = causeY - y

        // Use Web Animations API for reliable animation
        gRef.current.animate([
          { transform: `translate(0, ${offsetY}px)`, opacity: 0 },
          { transform: 'translate(0, 0)', opacity: 1 }
        ], {
          duration: 1500,
          easing: 'ease-out',
          fill: 'forwards'
        })
      }
    }
  }, [event.timestamp, isDecision, event.causedBy, allEvents, y])

  return (
    <g ref={gRef}>
      <rect
        x={rectX}
        y={rectY}
        width={width}
        height={height}
        rx="8"
        ry="8"
        fill={fillColor}
        stroke="none"
        strokeWidth="0"
        style={{ cursor: 'pointer', transition: 'all 0.2s' }}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
      />
      <text
        x={event.x}
        y={y + 5}
        textAnchor="middle"
        fontSize="11"
        fill={isDecision ? "white" : "black"}
        fontWeight="bold"
        style={{ pointerEvents: 'none', userSelect: 'none' }}
      >
        {event.label}
      </text>
    </g>
  )
}

interface ActorPanelProps {
  name: string
  role: string
  color: string
  rmState: string
  emState?: string
  vfdState?: string
  pxaState?: string
  actions: Array<{
    id: string
    label: string
    description: string
    enabled: boolean
  }>
  onActionClick: (actionId: string) => void
}

function ActorPanel({ name, role, color, rmState, emState, vfdState, pxaState, actions, onActionClick }: ActorPanelProps) {
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
        <div><strong>RM:</strong> {rmState}</div>
        {emState && <div><strong>EM:</strong> {emState}</div>}
        {vfdState && <div><strong>VFD:</strong> {vfdState}</div>}
        {pxaState && <div><strong>PXA:</strong> {pxaState}</div>}
      </div>

      {/* Actions */}
      {actions.length > 0 && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
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

interface TimelineEvent {
  id: string
  actor: string
  label: string
  x: number  // horizontal position
  lane: number  // which swimlane (0=finder, 1=vendor, 2=caseactor)
  type: 'decision' | 'consequence'
  consequences: string[]  // what happened (for hover)
  causedBy?: string  // ID of the decision that caused this consequence
  enablesNext?: boolean  // True if this consequence enables a next decision (dark green), false for tracking only (pale orange)
  timestamp?: number  // When this event was created, for animation
}

// Demo state machine
interface DemoState {
  phase: string
  finderRmState: string
  vendorRmState: string
  emState: string
  vendorVfdState: string
  pxaState: string  // Case-level PXA state (Public/eXploit/Attacks)
  timelineEvents: TimelineEvent[]
  eventLog: string[]
  vendorVisible: boolean
  caseActorVisible: boolean
  nextXPosition: number  // Track x position for uniform spacing
  finderHasClosed: boolean
  vendorHasClosed: boolean
  finderEmbargoAccepted: boolean  // Track if finder accepted current embargo proposal
  vendorEmbargoAccepted: boolean  // Track if vendor accepted current embargo proposal
}

function App() {
  const [demoState, setDemoState] = useState<DemoState>({
    phase: 'start',
    finderRmState: 'START',
    vendorRmState: 'START',
    emState: 'NONE',
    vendorVfdState: 'vfd',
    pxaState: 'pxa',  // Start with no public, no exploit, no attacks
    timelineEvents: [],
    eventLog: [],
    vendorVisible: false,
    caseActorVisible: false,
    nextXPosition: 100,  // Start at 100px, increment by 250px for each decision column
    finderHasClosed: false,
    vendorHasClosed: false,
    finderEmbargoAccepted: false,
    vendorEmbargoAccepted: false,
  })

  const [hoveredEvent, setHoveredEvent] = useState<string | null>(null)
  const [stateHistory, setStateHistory] = useState<DemoState[]>([])
  const timelineScrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to show the most recent event (only after 4+ decision nodes)
  useEffect(() => {
    if (timelineScrollRef.current && demoState.timelineEvents.length > 0) {
      // Count decision nodes
      const decisionCount = demoState.timelineEvents.filter(e => e.type === 'decision').length

      // Only auto-scroll if we have more than 4 decision nodes
      if (decisionCount > 4) {
        const mostRecentEvent = demoState.timelineEvents[demoState.timelineEvents.length - 1]
        // Scroll to show the most recent event with some padding
        const scrollLeft = mostRecentEvent.x - 200
        timelineScrollRef.current.scrollTo({
          left: Math.max(0, scrollLeft),
          behavior: 'smooth'
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
    setDemoState({
      phase: 'start',
      finderRmState: 'START',
      vendorRmState: 'START',
      emState: 'NONE',
      vendorVfdState: 'vfd',
      pxaState: 'pxa',
      timelineEvents: [],
      eventLog: [],
      vendorVisible: false,
      caseActorVisible: false,
      nextXPosition: 100,
      finderHasClosed: false,
      vendorHasClosed: false,
      finderEmbargoAccepted: false,
      vendorEmbargoAccepted: false,
    })
    setStateHistory([])
  }, [])

  // Action handler
  const handleAction = useCallback((actorId: string, actionId: string) => {
    console.log(`Action: ${actorId} -> ${actionId}`)

    // Save current state to history before making changes
    setStateHistory(prev => [...prev, demoState])

    // Handle different actions
    if (actionId === 'submit-report') {
      // Finder submits report
      const nextX = demoState.nextXPosition
      const submitEventId = 'event-1'
      const now = Date.now()

      setDemoState(prev => ({
        ...prev,
        phase: 'case-created',
        vendorRmState: 'RECEIVED',
        finderRmState: 'RECEIVED',
        emState: 'NONE',
        vendorVfdState: 'Vfd',
        vendorVisible: true,
        caseActorVisible: true,
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Decision node in Finder lane
          {
            id: submitEventId,
            actor: 'Finder',
            label: 'Submit Report',
            x: nextX,
            lane: 0,
            type: 'decision',
            timestamp: now,
            consequences: [
              'VulnerabilityReport object created',
              'Offer(VulnerabilityReport) activity created',
              'Offer sent to Vendor\'s inbox',
              'Triggers automatic case creation',
            ],
          },
          // Consequence node in Vendor lane
          {
            id: `${submitEventId}-vendor-consequence`,
            actor: 'Vendor',
            label: 'Report Received',
            x: nextX,
            lane: 1,
            type: 'consequence',
            causedBy: submitEventId,
            enablesNext: true,
            timestamp: now + 1,
            consequences: [
              'Offer received in inbox',
              'SubmitReportReceived handler triggered',
              'VulnerabilityReport stored in DataLayer',
              'Vendor\'s RM state → RECEIVED',
              'Case creation BT executes automatically',
            ],
          },
          // Consequence node in CaseActor lane (automatic case creation)
          {
            id: `${submitEventId}-case-consequence`,
            actor: 'CaseActor',
            label: 'Case Created',
            x: nextX,
            lane: 2,
            type: 'consequence',
            causedBy: submitEventId,
            timestamp: now + 2,
            consequences: [
              'VulnerabilityCase created automatically',
              'Case creation BT: create_receive_report_case_tree',
              'Vendor participant created (attributed_to: Vendor)',
              'Vendor\'s RM → RECEIVED, VFD → Vfd',
              'Case Actor acts as authoritative ledger',
            ],
          },
          // Consequence node in Finder lane (case announced to finder)
          {
            id: `${submitEventId}-finder-case-consequence`,
            actor: 'Finder',
            label: 'Case Announced',
            x: nextX,
            lane: 0,
            type: 'consequence',
            causedBy: submitEventId,
            timestamp: now + 3,
            consequences: [
              'Announce(Case) received in inbox',
              'Case replica created in DataLayer',
              'Finder participant record created',
              'Finder\'s RM → RECEIVED',
              'Trust established with CaseActor',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          'Finder submitted report to Vendor',
          'Case created automatically (at RM.RECEIVED)',
        ],
      }))
    } else if (actionId === 'propose-embargo') {
      // CaseActor proposes embargo
      const nextX = demoState.nextXPosition
      const proposeEventId = `event-${demoState.timelineEvents.length + 1}`
      const now = Date.now()

      setDemoState(prev => ({
        ...prev,
        phase: 'embargo-proposed',
        emState: 'PROPOSED',
        finderEmbargoAccepted: false,
        vendorEmbargoAccepted: false,
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Decision node in CaseActor lane
          {
            id: proposeEventId,
            actor: 'CaseActor',
            label: 'Propose Embargo',
            x: nextX,
            lane: 2,
            type: 'decision',
            timestamp: now,
            consequences: [
              'EmbargoEvent created (90-day proposal)',
              'EmProposeEmbargoActivity created',
              'Proposal sent to Vendor inbox',
              'EM state → PROPOSED',
              'Awaiting Vendor decision',
            ],
          },
          // Consequence node in Vendor lane (enables Accept/Reject)
          {
            id: `${proposeEventId}-vendor-consequence`,
            actor: 'Vendor',
            label: 'Proposal Received',
            x: nextX,
            lane: 1,
            type: 'consequence',
            timestamp: now + 1,
            causedBy: proposeEventId,
            enablesNext: true,  // Enables Accept/Reject decision
            consequences: [
              'EmProposeEmbargoActivity received',
              'EmbargoEvent stored in DataLayer',
              'Vendor sees 90-day embargo proposal',
              'Must accept or reject',
            ],
          },
          // Consequence node in Finder lane (enables Accept/Reject)
          {
            id: `${proposeEventId}-finder-consequence`,
            actor: 'Finder',
            label: 'Proposal Received',
            x: nextX,
            lane: 0,
            type: 'consequence',
            timestamp: now + 2,
            causedBy: proposeEventId,
            enablesNext: true,
            consequences: [
              'EmProposeEmbargoActivity received',
              'Finder sees 90-day embargo proposal',
              'EM state → PROPOSED',
              'Must accept or reject',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          'CaseActor proposed 90-day embargo',
        ],
      }))
    } else if (actionId === 'accept-embargo') {
      // Vendor accepts embargo proposal
      const nextX = demoState.nextXPosition
      const acceptEventId = `event-${demoState.timelineEvents.length + 1}`
      const now = Date.now()
      const bothAccepted = demoState.finderEmbargoAccepted  // Has finder already accepted?

      setDemoState(prev => ({
        ...prev,
        phase: bothAccepted ? 'embargo-accepted' : 'embargo-proposed',
        emState: bothAccepted ? 'ACTIVE' : 'PROPOSED',
        vendorEmbargoAccepted: true,
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Decision node in Vendor lane
          {
            id: acceptEventId,
            actor: 'Vendor',
            label: 'Accept Embargo',
            x: nextX,
            lane: 1,
            type: 'decision',
            timestamp: now,
            consequences: bothAccepted ? [
              'EmAcceptEmbargoActivity created',
              'Both parties have accepted',
              'ActivateEmbargoActivity triggered',
              'EM state → ACTIVE',
              'Triggers announcement to participants',
            ] : [
              'EmAcceptEmbargoActivity created',
              'Acceptance sent to CaseActor',
              'Awaiting Finder acceptance',
              'EM state remains PROPOSED',
            ],
          },
          // Consequence node in CaseActor lane
          {
            id: `${acceptEventId}-caseactor-consequence`,
            actor: 'CaseActor',
            label: bothAccepted ? 'Embargo Activated' : 'Vendor Accepted',
            x: nextX,
            lane: 2,
            type: 'consequence',
            timestamp: now + 1,
            causedBy: acceptEventId,
            enablesNext: bothAccepted,
            consequences: bothAccepted ? [
              'EmAcceptEmbargoActivity received from both',
              'ActivateEmbargoActivity processed',
              'Case active_embargo set',
              'EM state → ACTIVE',
              'Authoritative ledger updated',
            ] : [
              'Vendor EmAcceptEmbargoActivity received',
              'Awaiting Finder acceptance',
              'EM state remains PROPOSED',
            ],
          },
          // Consequence node in Finder lane
          {
            id: `${acceptEventId}-finder-consequence`,
            actor: 'Finder',
            label: bothAccepted ? 'Embargo Active' : 'Vendor Accepted',
            x: nextX,
            lane: 0,
            type: 'consequence',
            timestamp: now + 2,
            causedBy: acceptEventId,
            consequences: bothAccepted ? [
              'AnnounceEmbargoActivity received',
              'Finder\'s EM state → ACTIVE',
              '90-day embargo now in effect',
              '✓ M1 REACHED: Case active, embargo established',
            ] : [
              'Vendor has accepted embargo',
              'Finder must still accept or reject',
              'EM state remains PROPOSED',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          bothAccepted
            ? '✓ M1 REACHED: Case active with 3 participants, embargo active'
            : 'Vendor accepted embargo (awaiting Finder)',
        ],
      }))
    } else if (actionId === 'finder-accept-embargo') {
      // Finder accepts embargo proposal
      const nextX = demoState.nextXPosition
      const finderAcceptEventId = `event-${demoState.timelineEvents.length + 1}`
      const now = Date.now()
      const bothAccepted = demoState.vendorEmbargoAccepted  // Has vendor already accepted?

      setDemoState(prev => ({
        ...prev,
        phase: bothAccepted ? 'embargo-accepted' : 'embargo-proposed',
        emState: bothAccepted ? 'ACTIVE' : 'PROPOSED',
        finderEmbargoAccepted: true,
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Decision node in Finder lane
          {
            id: finderAcceptEventId,
            actor: 'Finder',
            label: 'Accept Embargo',
            x: nextX,
            lane: 0,
            type: 'decision',
            timestamp: now,
            consequences: bothAccepted ? [
              'EmAcceptEmbargoActivity created',
              'Both parties have accepted',
              'ActivateEmbargoActivity triggered',
              'EM state → ACTIVE',
              'Triggers announcement to participants',
            ] : [
              'EmAcceptEmbargoActivity created',
              'Acceptance sent to CaseActor',
              'Awaiting Vendor acceptance',
              'EM state remains PROPOSED',
            ],
          },
          // Consequence node in Vendor lane
          {
            id: `${finderAcceptEventId}-vendor-consequence`,
            actor: 'Vendor',
            label: bothAccepted ? 'Embargo Active' : 'Finder Accepted',
            x: nextX,
            lane: 1,
            type: 'consequence',
            timestamp: now + 1,
            causedBy: finderAcceptEventId,
            consequences: bothAccepted ? [
              'AnnounceEmbargoActivity received',
              'Vendor\'s EM state → ACTIVE',
              '90-day embargo now in effect',
              '✓ M1 REACHED: Case active, embargo established',
            ] : [
              'Finder has accepted embargo',
              'Vendor must still accept or reject',
              'EM state remains PROPOSED',
            ],
          },
          // Consequence node in CaseActor lane
          {
            id: `${finderAcceptEventId}-caseactor-consequence`,
            actor: 'CaseActor',
            label: bothAccepted ? 'Embargo Activated' : 'Finder Accepted',
            x: nextX,
            lane: 2,
            type: 'consequence',
            timestamp: now + 2,
            causedBy: finderAcceptEventId,
            enablesNext: bothAccepted,
            consequences: bothAccepted ? [
              'EmAcceptEmbargoActivity received from both',
              'ActivateEmbargoActivity processed',
              'Case active_embargo set',
              'EM state → ACTIVE',
              'Authoritative ledger updated',
            ] : [
              'Finder EmAcceptEmbargoActivity received',
              'Awaiting Vendor acceptance',
              'EM state remains PROPOSED',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          bothAccepted
            ? '✓ M1 REACHED: Case active with 3 participants, embargo active'
            : 'Finder accepted embargo (awaiting Vendor)',
        ],
      }))
    } else if (actionId === 'reject-embargo' || actionId === 'finder-reject-embargo') {
      // Vendor or Finder rejects embargo proposal
      const isFinderRejecting = actionId === 'finder-reject-embargo'
      const nextX = demoState.nextXPosition
      const rejectEventId = `event-${demoState.timelineEvents.length + 1}`
      const now = Date.now()

      setDemoState(prev => ({
        ...prev,
        phase: 'embargo-rejected',
        emState: 'NONE',
        finderEmbargoAccepted: false,
        vendorEmbargoAccepted: false,
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Decision node in rejecting actor's lane
          {
            id: rejectEventId,
            actor: isFinderRejecting ? 'Finder' : 'Vendor',
            label: 'Reject Embargo',
            x: nextX,
            lane: isFinderRejecting ? 0 : 1,
            type: 'decision',
            timestamp: now,
            consequences: [
              'EmRejectEmbargoActivity created',
              'Rejection sent to CaseActor',
              'EM state → NONE',
              'No embargo will be activated',
              'Any prior acceptances nullified',
            ],
          },
          // Consequence node in CaseActor lane (enables repropose)
          {
            id: `${rejectEventId}-caseactor-consequence`,
            actor: 'CaseActor',
            label: 'Embargo Rejected',
            x: nextX,
            lane: 2,
            type: 'consequence',
            timestamp: now + 1,
            causedBy: rejectEventId,
            enablesNext: true,
            consequences: [
              'EmRejectEmbargoActivity received',
              'Embargo proposal discarded',
              'EM state → NONE',
              'Can repropose with revised terms',
              'Or case can continue without embargo',
            ],
          },
          // Consequence node in non-rejecting participant lane
          {
            id: `${rejectEventId}-participant-consequence`,
            actor: isFinderRejecting ? 'Vendor' : 'Finder',
            label: 'Embargo Rejected',
            x: nextX,
            lane: isFinderRejecting ? 1 : 0,
            type: 'consequence',
            timestamp: now + 2,
            causedBy: rejectEventId,
            consequences: [
              `${isFinderRejecting ? 'Finder' : 'Vendor'} rejected embargo`,
              'EM state remains NONE',
              'Awaiting reproposal or continuation',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          `${isFinderRejecting ? 'Finder' : 'Vendor'} rejected embargo proposal (can be reproposed)`,
        ],
      }))
    } else if (actionId === 'trigger-exploit') {
      // External event: exploit published in the wild (not a participant action)
      const nextX = demoState.nextXPosition
      const exploitEventId = `event-${demoState.timelineEvents.length + 1}`
      const now = Date.now()

      // Determine new PXA state
      const currentPxa = demoState.pxaState
      let newPxa = currentPxa
      if (currentPxa === 'pxa') {
        newPxa = 'pXa'  // exploit published
      } else if (currentPxa === 'pxA') {
        newPxa = 'pXA'  // exploit + attacks
      } else if (currentPxa === 'Pxa') {
        newPxa = 'PXa'  // public + exploit
      } else if (currentPxa === 'PxA') {
        newPxa = 'PXA'  // public + exploit + attacks
      }

      setDemoState(prev => ({
        ...prev,
        pxaState: newPxa,
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Consequence node in Finder lane (external event affects all)
          {
            id: `${exploitEventId}-finder-consequence`,
            actor: 'Finder',
            label: 'Exploit Published',
            x: nextX,
            lane: 0,
            type: 'consequence',
            timestamp: now,
            consequences: [
              'External event: exploit published in the wild',
              'Finder becomes aware of exploit',
              'Participant pxa_state updated',
            ],
          },
          // Consequence node in Vendor lane
          {
            id: `${exploitEventId}-vendor-consequence`,
            actor: 'Vendor',
            label: 'Exploit Published',
            x: nextX,
            lane: 1,
            type: 'consequence',
            timestamp: now + 1,
            consequences: [
              'External event: exploit published in the wild',
              'Vendor becomes aware of exploit',
              'Participant pxa_state updated',
            ],
          },
          // Consequence node in CaseActor lane
          {
            id: `${exploitEventId}-caseactor-consequence`,
            actor: 'CaseActor',
            label: 'Exploit Tracked',
            x: nextX,
            lane: 2,
            type: 'consequence',
            timestamp: now + 2,
            consequences: [
              'External event: exploit published',
              `Case PXA state: ${newPxa}`,
              'Authoritative ledger updated',
              'All participants notified',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          'Exploit published in the wild (external event)',
        ],
      }))
    } else if (actionId === 'trigger-attacks') {
      // External event: attacks observed in the wild (not a participant action)
      const nextX = demoState.nextXPosition
      const attackEventId = `event-${demoState.timelineEvents.length + 1}`
      const now = Date.now()

      // Determine new PXA state
      const currentPxa = demoState.pxaState
      let newPxa = currentPxa
      if (currentPxa === 'pxa') {
        newPxa = 'pxA'  // attacks observed
      } else if (currentPxa === 'pXa') {
        newPxa = 'pXA'  // exploit + attacks
      } else if (currentPxa === 'Pxa') {
        newPxa = 'PxA'  // public + attacks
      } else if (currentPxa === 'PXa') {
        newPxa = 'PXA'  // public + exploit + attacks
      }

      setDemoState(prev => ({
        ...prev,
        pxaState: newPxa,
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Consequence node in Finder lane (external event affects all)
          {
            id: `${attackEventId}-finder-consequence`,
            actor: 'Finder',
            label: 'Attacks Observed',
            x: nextX,
            lane: 0,
            type: 'consequence',
            timestamp: now,
            consequences: [
              'External event: attacks observed in the wild',
              'Finder becomes aware of attacks',
              'Participant pxa_state updated',
            ],
          },
          // Consequence node in Vendor lane
          {
            id: `${attackEventId}-vendor-consequence`,
            actor: 'Vendor',
            label: 'Attacks Observed',
            x: nextX,
            lane: 1,
            type: 'consequence',
            timestamp: now + 1,
            consequences: [
              'External event: attacks observed in the wild',
              'Vendor becomes aware of attacks',
              'Participant pxa_state updated',
            ],
          },
          // Consequence node in CaseActor lane
          {
            id: `${attackEventId}-caseactor-consequence`,
            actor: 'CaseActor',
            label: 'Attacks Tracked',
            x: nextX,
            lane: 2,
            type: 'consequence',
            timestamp: now + 2,
            consequences: [
              'External event: attacks observed',
              `Case PXA state: ${newPxa}`,
              'Authoritative ledger updated',
              'All participants notified',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          'Attacks observed in the wild (external event)',
        ],
      }))
    } else if (actionId === 'commit-log') {
      // Vendor commits log entry for replica sync verification
      const nextX = demoState.nextXPosition
      const logEventId = `event-${demoState.timelineEvents.length + 1}`
      const now = Date.now()

      setDemoState(prev => ({
        ...prev,
        phase: 'log-committed',
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Decision node in Vendor lane (GREEN)
          {
            id: logEventId,
            actor: 'Vendor',
            label: 'Commit Log',
            x: nextX,
            lane: 1,
            type: 'decision',
            timestamp: now,
            consequences: [
              'CaseEvent created with hash',
              'Announce(CaseEvent) activity created',
              'Sent to participants',
              'Triggers replica sync and Case Actor tracking',
            ],
          },
          // Consequence node in Finder lane (enables Ask Question)
          {
            id: `${logEventId}-finder-consequence`,
            actor: 'Finder',
            label: 'Replica Synced',
            x: nextX,
            lane: 0,
            type: 'consequence',
            timestamp: now + 1,
            causedBy: logEventId,
            enablesNext: true,  // Enables Ask Question decision
            consequences: [
              'Announce received in inbox',
              'CaseEvent stored in DataLayer',
              'Finder\'s replica synchronized',
              'Hash verified',
              '✓ M2 REACHED: Replica state verified (SYNC-2)',
            ],
          },
          // Consequence node in CaseActor lane (BLUE)
          {
            id: `${logEventId}-caseactor-consequence`,
            actor: 'CaseActor',
            label: 'Event Logged',
            x: nextX,
            lane: 2,
            type: 'consequence',
            timestamp: now + 2,
            causedBy: logEventId,
            consequences: [
              'CaseEvent tracked by Case Actor',
              'Event hash recorded',
              'Authoritative ledger updated',
              'Event becomes part of case history',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          '✓ M2 REACHED: Finder replica synchronized',
        ],
      }))
    } else if (actionId === 'finder-add-note') {
      // Finder asks question
      const nextX = demoState.nextXPosition
      const noteEventId = `event-${demoState.timelineEvents.length + 1}`
      const now = Date.now()

      setDemoState(prev => ({
        ...prev,
        phase: 'finder-asked',
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Decision node in Finder lane (GREEN)
          {
            id: noteEventId,
            actor: 'Finder',
            label: 'Ask Question',
            x: nextX,
            lane: 0,
            type: 'decision',
            timestamp: now,
            consequences: [
              'Note created: "Question from Finder"',
              'Content: "Is there a workaround available?"',
              'Add(Note, target=Case) activity created',
              'Activity sent via Finder\'s outbox',
              'Triggers delivery to participants',
            ],
          },
          // Consequence node in Vendor lane (enables Reply)
          {
            id: `${noteEventId}-vendor-consequence`,
            actor: 'Vendor',
            label: 'Note Received',
            x: nextX,
            lane: 1,
            type: 'consequence',
            timestamp: now + 1,
            causedBy: noteEventId,
            enablesNext: true,  // Enables Reply decision
            consequences: [
              'Add(Note) received in inbox',
              'Note delivered to Vendor\'s DataLayer',
              'Vendor can now see question',
            ],
          },
          // Consequence node in CaseActor lane (BLUE)
          {
            id: `${noteEventId}-caseactor-consequence`,
            actor: 'CaseActor',
            label: 'Note Tracked',
            x: nextX,
            lane: 2,
            type: 'consequence',
            timestamp: now + 2,
            causedBy: noteEventId,
            consequences: [
              'Note tracked by Case Actor',
              'Note added to case history',
              'Authoritative ledger updated',
              'Part of case audit trail',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          'Finder asked: "Is there a workaround available?"',
        ],
      }))
    } else if (actionId === 'vendor-reply-note') {
      // Vendor replies
      const nextX = demoState.nextXPosition
      const replyEventId = `event-${demoState.timelineEvents.length + 1}`
      const now = Date.now()

      setDemoState(prev => ({
        ...prev,
        phase: 'vendor-replied',
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Decision node in Vendor lane (GREEN)
          {
            id: replyEventId,
            actor: 'Vendor',
            label: 'Reply',
            x: nextX,
            lane: 1,
            type: 'decision',
            timestamp: now,
            consequences: [
              'Note created: "Vendor Response"',
              'Content: "Yes, disable the network stack component"',
              'inReplyTo: previous note',
              'Add(Note, target=Case) activity created',
              'Activity sent via Vendor\'s outbox',
              'Triggers delivery to participants',
            ],
          },
          // Consequence node in Finder lane (BLUE)
          {
            id: `${replyEventId}-finder-consequence`,
            actor: 'Finder',
            label: 'Reply Received',
            x: nextX,
            lane: 0,
            type: 'consequence',
            timestamp: now + 1,
            causedBy: replyEventId,
            consequences: [
              'Add(Note) received in inbox',
              'Reply delivered to Finder\'s DataLayer',
              'Finder can now see workaround',
              '✓ M3 REACHED: Notes exchanged',
            ],
          },
          // Consequence node in CaseActor lane (BLUE)
          {
            id: `${replyEventId}-caseactor-consequence`,
            actor: 'CaseActor',
            label: 'Reply Tracked',
            x: nextX,
            lane: 2,
            type: 'consequence',
            timestamp: now + 2,
            causedBy: replyEventId,
            consequences: [
              'Reply tracked by Case Actor',
              'Reply added to case history',
              'Authoritative ledger updated',
              'Case state finalized',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          'Vendor replied with workaround guidance',
          '✓ M3 REACHED: Notes exchanged successfully',
        ],
      }))
    } else if (actionId === 'notify-fix-ready') {
      // Vendor notifies fix is ready
      const nextX = demoState.nextXPosition
      const fixReadyEventId = `event-${demoState.timelineEvents.length + 1}`
      const now = Date.now()

      setDemoState(prev => ({
        ...prev,
        phase: 'fix-ready',
        vendorVfdState: 'VFd',
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Decision node in Vendor lane (GREEN)
          {
            id: fixReadyEventId,
            actor: 'Vendor',
            label: 'Notify Fix Ready',
            x: nextX,
            lane: 1,
            type: 'decision',
            timestamp: now,
            consequences: [
              'Vendor creates UpdateParticipantStatus',
              'vfd_state → VFd (fix ready)',
              'Announce activity sent to participants',
              'Triggers state update on Finder and Case Actor',
            ],
          },
          // Consequence node in Finder lane (BLUE)
          {
            id: `${fixReadyEventId}-finder-consequence`,
            actor: 'Finder',
            label: 'Fix Ready Noted',
            x: nextX,
            lane: 0,
            type: 'consequence',
            timestamp: now + 1,
            causedBy: fixReadyEventId,
            consequences: [
              'Announce received in inbox',
              'Vendor participant status updated',
              'Finder sees fix is ready',
              '✓ M4 REACHED: Fix ready on both replicas',
            ],
          },
          // Consequence node in CaseActor lane (BLUE)
          {
            id: `${fixReadyEventId}-caseactor-consequence`,
            actor: 'CaseActor',
            label: 'Fix Status Tracked',
            x: nextX,
            lane: 2,
            type: 'consequence',
            timestamp: now + 2,
            causedBy: fixReadyEventId,
            consequences: [
              'Vendor participant status updated',
              'VFD state tracked: VFd',
              'Authoritative ledger updated',
              'Case shows fix ready',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          '✓ M4 REACHED: Fix ready',
        ],
      }))
    } else if (actionId === 'notify-fix-deployed') {
      // Vendor notifies fix is deployed
      const nextX = demoState.nextXPosition
      const fixDeployedEventId = `event-${demoState.timelineEvents.length + 1}`
      const now = Date.now()

      setDemoState(prev => ({
        ...prev,
        phase: 'fix-deployed',
        vendorVfdState: 'VFD',
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Decision node in Vendor lane (GREEN)
          {
            id: fixDeployedEventId,
            actor: 'Vendor',
            label: 'Notify Fix Deployed',
            x: nextX,
            lane: 1,
            type: 'decision',
            timestamp: now,
            consequences: [
              'Vendor creates UpdateParticipantStatus',
              'vfd_state → VFD (fix deployed)',
              'Announce activity sent to participants',
              'Triggers state update on Finder and Case Actor',
            ],
          },
          // Consequence node in Finder lane (BLUE)
          {
            id: `${fixDeployedEventId}-finder-consequence`,
            actor: 'Finder',
            label: 'Fix Deployed Noted',
            x: nextX,
            lane: 0,
            type: 'consequence',
            timestamp: now + 1,
            causedBy: fixDeployedEventId,
            consequences: [
              'Announce received in inbox',
              'Vendor participant status updated',
              'Finder sees fix is deployed',
              '✓ M5 REACHED: Fix deployed on both replicas',
            ],
          },
          // Consequence node in CaseActor lane (BLUE)
          {
            id: `${fixDeployedEventId}-caseactor-consequence`,
            actor: 'CaseActor',
            label: 'Deployment Tracked',
            x: nextX,
            lane: 2,
            type: 'consequence',
            timestamp: now + 2,
            causedBy: fixDeployedEventId,
            consequences: [
              'Vendor participant status updated',
              'VFD state tracked: VFD',
              'Authoritative ledger updated',
              'Case shows fix deployed',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          '✓ M5 REACHED: Fix deployed',
        ],
      }))
    } else if (actionId === 'vendor-notify-published') {
      // Vendor notifies publication
      const nextX = demoState.nextXPosition
      const vendorPubEventId = `event-${demoState.timelineEvents.length + 1}`
      const now = Date.now()

      setDemoState(prev => ({
        ...prev,
        phase: 'vendor-published',
        emState: 'EXITED',
        pxaState: 'Pxa',  // Public awareness achieved
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Decision node in Vendor lane (GREEN)
          {
            id: vendorPubEventId,
            actor: 'Vendor',
            label: 'Notify Published',
            x: nextX,
            lane: 1,
            type: 'decision',
            timestamp: now,
            consequences: [
              'Vendor creates UpdateParticipantStatus',
              'pxa_state → public-aware',
              'EM → EXITED (embargo terminated)',
              'Case PXA → Pxa (public awareness)',
              'Announce activity sent to participants',
            ],
          },
          // Consequence node in Finder lane (enables Acknowledge Publication)
          {
            id: `${vendorPubEventId}-finder-consequence`,
            actor: 'Finder',
            label: 'Publication Noted',
            x: nextX,
            lane: 0,
            type: 'consequence',
            timestamp: now + 1,
            causedBy: vendorPubEventId,
            enablesNext: true,  // Enables Acknowledge Publication decision
            consequences: [
              'Announce received in inbox',
              'Vendor participant status updated',
              'Embargo terminated (EM.EXITED)',
              'Finder sees publication',
            ],
          },
          // Consequence node in CaseActor lane (BLUE)
          {
            id: `${vendorPubEventId}-caseactor-consequence`,
            actor: 'CaseActor',
            label: 'Publication Tracked',
            x: nextX,
            lane: 2,
            type: 'consequence',
            timestamp: now + 2,
            causedBy: vendorPubEventId,
            consequences: [
              'Vendor participant pxa_state updated',
              'Embargo state: EM.EXITED',
              'Case PXA state: Pxa (public awareness)',
              'Authoritative ledger updated',
              'Case shows public disclosure',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          'Vendor notified publication',
        ],
      }))
    } else if (actionId === 'finder-notify-published') {
      // Finder acknowledges publication
      const nextX = demoState.nextXPosition
      const finderPubEventId = `event-${demoState.timelineEvents.length + 1}`
      const now = Date.now()

      setDemoState(prev => ({
        ...prev,
        phase: 'finder-published',
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Decision node in Finder lane (GREEN)
          {
            id: finderPubEventId,
            actor: 'Finder',
            label: 'Acknowledge Publication',
            x: nextX,
            lane: 0,
            type: 'decision',
            timestamp: now,
            consequences: [
              'Finder creates UpdateParticipantStatus',
              'pxa_state → public-aware',
              'Announce activity sent to participants',
              '✓ M6 REACHED: CS.VFDPxa, EM.EXITED',
            ],
          },
          // Consequence node in Vendor lane (enables Close Case)
          {
            id: `${finderPubEventId}-vendor-consequence`,
            actor: 'Vendor',
            label: 'Ack Received',
            x: nextX,
            lane: 1,
            type: 'consequence',
            timestamp: now + 1,
            causedBy: finderPubEventId,
            enablesNext: true,  // Enables Close Case decision
            consequences: [
              'Announce received in inbox',
              'Finder participant status updated',
              'Both participants public-aware',
            ],
          },
          // Consequence node in CaseActor lane (BLUE)
          {
            id: `${finderPubEventId}-caseactor-consequence`,
            actor: 'CaseActor',
            label: 'Full Disclosure',
            x: nextX,
            lane: 2,
            type: 'consequence',
            timestamp: now + 2,
            causedBy: finderPubEventId,
            consequences: [
              'Finder participant pxa_state updated',
              'All participants public-aware',
              'Case PXA state: Pxa (public awareness)',
              'CS.VFDPxa state achieved',
              '✓ M6: Public disclosure complete',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          '✓ M6 REACHED: Publicly disclosed',
        ],
      }))
    } else if (actionId === 'vendor-close-case') {
      // Vendor closes case
      const nextX = demoState.nextXPosition
      const vendorCloseEventId = `event-${demoState.timelineEvents.length + 1}`
      const bothClosed = demoState.finderHasClosed  // Will both be closed after this action?
      const now = Date.now()

      // Determine new phase based on current state
      let newPhase = bothClosed ? 'case-closed' : 'vendor-closed'

      setDemoState(prev => ({
        ...prev,
        phase: newPhase,
        vendorRmState: 'CLOSED',
        vendorHasClosed: true,
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Decision node in Vendor lane (GREEN)
          {
            id: vendorCloseEventId,
            actor: 'Vendor',
            label: 'Close Case',
            x: nextX,
            lane: 1,
            type: 'decision',
            timestamp: now,
            consequences: [
              'Vendor creates UpdateParticipantStatus',
              'rm_state → CLOSED',
              'Announce activity sent to participants',
            ],
          },
          // Consequence node in Finder lane (enables Close Case if not already closed)
          {
            id: `${vendorCloseEventId}-finder-consequence`,
            actor: 'Finder',
            label: 'Closure Noted',
            x: nextX,
            lane: 0,
            type: 'consequence',
            timestamp: now + 1,
            causedBy: vendorCloseEventId,
            enablesNext: true,  // Enables Close Case decision
            consequences: [
              'Announce received in inbox',
              'Vendor participant status updated',
              'Vendor RM → CLOSED',
            ],
          },
          // Consequence node in CaseActor lane (BLUE)
          {
            id: `${vendorCloseEventId}-caseactor-consequence`,
            actor: 'CaseActor',
            label: 'Closure Tracked',
            x: nextX,
            lane: 2,
            type: 'consequence',
            timestamp: now + 2,
            causedBy: vendorCloseEventId,
            consequences: [
              'Vendor participant RM → CLOSED',
              'Authoritative ledger updated',
              'Waiting for all participants to close',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          bothClosed ? '✓ M7 REACHED: Case closed' : 'Vendor closed case',
        ],
      }))
    } else if (actionId === 'finder-close-case') {
      // Finder closes case
      const nextX = demoState.nextXPosition
      const finderCloseEventId = `event-${demoState.timelineEvents.length + 1}`
      const bothClosed = demoState.vendorHasClosed  // Will both be closed after this action?
      const now = Date.now()

      // Determine new phase based on current state
      let newPhase = bothClosed ? 'case-closed' : 'finder-closed'

      setDemoState(prev => ({
        ...prev,
        phase: newPhase,
        finderRmState: 'CLOSED',
        finderHasClosed: true,
        nextXPosition: prev.nextXPosition + 250,
        timelineEvents: [
          ...prev.timelineEvents,
          // Decision node in Finder lane (GREEN)
          {
            id: finderCloseEventId,
            actor: 'Finder',
            label: 'Close Case',
            x: nextX,
            lane: 0,
            type: 'decision',
            timestamp: now,
            consequences: [
              'Finder creates UpdateParticipantStatus',
              'rm_state → CLOSED',
              'Announce activity sent to participants',
              '✓ M7 REACHED: All participants closed',
            ],
          },
          // Consequence node in Vendor lane (BLUE)
          {
            id: `${finderCloseEventId}-vendor-consequence`,
            actor: 'Vendor',
            label: 'Closure Complete',
            x: nextX,
            lane: 1,
            type: 'consequence',
            timestamp: now + 1,
            causedBy: finderCloseEventId,
            consequences: [
              'Announce received in inbox',
              'Finder participant status updated',
              'All participants RM.CLOSED',
            ],
          },
          // Consequence node in CaseActor lane (BLUE)
          {
            id: `${finderCloseEventId}-caseactor-consequence`,
            actor: 'CaseActor',
            label: 'Case Closed',
            x: nextX,
            lane: 2,
            type: 'consequence',
            timestamp: now + 2,
            causedBy: finderCloseEventId,
            consequences: [
              'Finder participant RM → CLOSED',
              'All participants RM.CLOSED',
              'Case Actor closes case',
              '✓ M7: Case closure complete',
            ],
          },
        ],
        eventLog: [
          ...prev.eventLog,
          bothClosed ? '✓ M7 REACHED: Case closed' : 'Finder closed case',
        ],
      }))
    }
  }, [demoState.timelineEvents.length])

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ padding: '1rem', background: '#f5f5f5', borderBottom: '1px solid #ddd', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', color: '#666' }}>
            Vultron Interactive Demo — Two-Actor CVD
          </h1>
          <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.9rem', color: '#666' }}>
            CERT/CC — Research Prototype | Click actions on actors to progress through the demo
          </p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          {/* External Event Triggers */}
          {demoState.caseActorVisible && (
            <div style={{ display: 'flex', gap: '0.5rem', marginRight: '1rem', paddingRight: '1rem', borderRight: '2px solid #ddd' }}>
              <span style={{ fontSize: '0.85rem', color: '#666', alignSelf: 'center', fontWeight: 'bold' }}>
                External Events:
              </span>
              <button
                onClick={() => handleAction('external', 'trigger-exploit')}
                disabled={demoState.pxaState.includes('X')}
                style={{
                  padding: '0.5rem 1rem',
                  fontSize: '0.85rem',
                  background: demoState.pxaState.includes('X') ? '#ccc' : '#ff5722',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: demoState.pxaState.includes('X') ? 'not-allowed' : 'pointer',
                  fontWeight: 'bold',
                  opacity: demoState.pxaState.includes('X') ? 0.5 : 1,
                }}
                title="Trigger external event: exploit published in the wild"
              >
                ⚠️ Exploit
              </button>
              <button
                onClick={() => handleAction('external', 'trigger-attacks')}
                disabled={demoState.pxaState.includes('A')}
                style={{
                  padding: '0.5rem 1rem',
                  fontSize: '0.85rem',
                  background: demoState.pxaState.includes('A') ? '#ccc' : '#d32f2f',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: demoState.pxaState.includes('A') ? 'not-allowed' : 'pointer',
                  fontWeight: 'bold',
                  opacity: demoState.pxaState.includes('A') ? 0.5 : 1,
                }}
                title="Trigger external event: attacks observed in the wild"
              >
                🔥 Attacks
              </button>
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
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#1976D2'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#2196F3'
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
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              if (stateHistory.length > 0) {
                e.currentTarget.style.background = '#f57c00'
              }
            }}
            onMouseLeave={(e) => {
              if (stateHistory.length > 0) {
                e.currentTarget.style.background = '#ff9800'
              }
            }}
          >
            ← Go Back
          </button>
        </div>
      </div>

      {/* Main content area */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left panel: Actor controls */}
        <div style={{ width: ACTOR_PANEL_WIDTH, borderRight: '3px solid #333', flexShrink: 0 }}>
          <ActorPanel
            name="Finder"
            role="REPORTER"
            color="#e3f2fd"
            rmState={demoState.finderRmState}
            emState={demoState.emState}
            actions={
              demoState.phase === 'start' ? [{
                id: 'submit-report',
                label: 'Submit Report',
                description: 'Create and submit a vulnerability report to the Vendor',
                enabled: true,
              }] : demoState.phase === 'embargo-proposed' && !demoState.finderEmbargoAccepted ? [{
                id: 'finder-accept-embargo',
                label: 'Accept Embargo',
                description: 'Accept the 90-day embargo proposal',
                enabled: true,
              }, {
                id: 'finder-reject-embargo',
                label: 'Reject Embargo',
                description: 'Reject the embargo proposal',
                enabled: true,
              }] : (demoState.phase === 'log-committed' || demoState.phase === 'vendor-replied') ? [{
                id: 'finder-add-note',
                label: demoState.phase === 'vendor-replied' ? 'Ask Another Question' : 'Ask Question',
                description: demoState.phase === 'vendor-replied'
                  ? 'Add another note to the case asking for more information'
                  : 'Add a note to the case asking for information',
                enabled: true,
              }] : (demoState.phase === 'fix-deployed' || demoState.phase === 'vendor-closed') && !demoState.finderHasClosed ? [{
                id: 'finder-close-case',
                label: 'Close Case',
                description: 'Finder closes their participation in the case',
                enabled: true,
              }] : demoState.phase === 'vendor-published' ? [{
                id: 'finder-notify-published',
                label: 'Acknowledge Publication',
                description: 'Finder acknowledges publication',
                enabled: true,
              }, {
                id: 'finder-close-case',
                label: 'Close Case',
                description: 'Finder closes their participation in the case',
                enabled: true,
              }] : (demoState.phase === 'finder-published' || demoState.phase === 'vendor-closed') && !demoState.finderHasClosed ? [{
                id: 'finder-close-case',
                label: 'Close Case',
                description: 'Finder closes their participation in the case',
                enabled: true,
              }] : []
            }
            onActionClick={(actionId) => handleAction('finder', actionId)}
          />
          {demoState.vendorVisible && (
            <ActorPanel
              name="Vendor"
              role="VENDOR, CASE_OWNER"
              color="#f3e5f5"
              rmState={demoState.vendorRmState}
              emState={demoState.emState}
              vfdState={demoState.vendorVfdState}
              actions={
                demoState.phase === 'embargo-proposed' && !demoState.vendorEmbargoAccepted ? [{
                  id: 'accept-embargo',
                  label: 'Accept Embargo',
                  description: 'Accept the 90-day embargo proposal',
                  enabled: true,
                }, {
                  id: 'reject-embargo',
                  label: 'Reject Embargo',
                  description: 'Reject the embargo proposal',
                  enabled: true,
                }] : demoState.phase === 'embargo-accepted' ? [{
                  id: 'commit-log',
                  label: 'Commit Log Entry',
                  description: 'Create log entry for replica synchronization verification',
                  enabled: true,
                }] : demoState.phase === 'log-committed' ? [{
                  id: 'notify-fix-ready',
                  label: 'Notify Fix Ready',
                  description: 'Vendor notifies that a fix is ready',
                  enabled: true,
                }] : demoState.phase === 'finder-asked' ? [{
                  id: 'vendor-reply-note',
                  label: 'Reply to Question',
                  description: 'Respond to Finder\'s question about workarounds',
                  enabled: true,
                }] : demoState.phase === 'vendor-replied' ? [{
                  id: 'notify-fix-ready',
                  label: 'Notify Fix Ready',
                  description: 'Vendor notifies that a fix is ready',
                  enabled: true,
                }] : demoState.phase === 'fix-ready' ? [{
                  id: 'notify-fix-deployed',
                  label: 'Notify Fix Deployed',
                  description: 'Vendor notifies that the fix has been deployed',
                  enabled: true,
                }] : demoState.phase === 'fix-deployed' ? [{
                  id: 'vendor-notify-published',
                  label: 'Notify Published',
                  description: 'Vendor notifies that vulnerability is publicly disclosed',
                  enabled: true,
                }, {
                  id: 'vendor-close-case',
                  label: 'Close Case',
                  description: 'Vendor closes their participation in the case',
                  enabled: true,
                }] : (demoState.phase === 'vendor-published' || demoState.phase === 'finder-published' || demoState.phase === 'finder-closed') && !demoState.vendorHasClosed ? [{
                  id: 'vendor-close-case',
                  label: 'Close Case',
                  description: 'Vendor closes their participation in the case',
                  enabled: true,
                }] : []
              }
              onActionClick={(actionId) => handleAction('vendor', actionId)}
            />
          )}
          {demoState.caseActorVisible && (
            <ActorPanel
              name="Case Actor"
              role="COORDINATOR, CASE_MANAGER (virtual)"
              color="#fff3e0"
              rmState="N/A"
              emState={demoState.emState}
              pxaState={demoState.pxaState}
              actions={
                (demoState.phase === 'case-created' || demoState.phase === 'embargo-rejected') ? [{
                  id: 'propose-embargo',
                  label: demoState.phase === 'embargo-rejected' ? 'Repropose Embargo' : 'Propose Embargo',
                  description: demoState.phase === 'embargo-rejected'
                    ? 'Propose a revised embargo to the Vendor'
                    : 'Propose a 90-day embargo to the Vendor',
                  enabled: true,
                }] : []
              }
              onActionClick={(actionId) => handleAction('caseactor', actionId)}
            />
          )}
        </div>

        {/* Right panel: Timeline visualization */}
        <div ref={timelineScrollRef} style={{ flex: 1, position: 'relative', background: '#fafafa', overflowX: 'auto', overflowY: 'hidden' }}>
          {/* Calculate required width based on events */}
          {(() => {
            const maxX = demoState.timelineEvents.length > 0
              ? Math.max(...demoState.timelineEvents.map(e => e.x)) + 500
              : 2000
            const minWidth = Math.max(maxX, 2000)

            return (
              <>
                {/* Swimlane backgrounds - extend to minWidth */}
                <div style={{ position: 'absolute', top: 0, left: 0, width: minWidth, height: LANE_HEIGHT, background: '#e3f2fd', opacity: 0.3 }} />
                {demoState.vendorVisible && (
                  <div style={{ position: 'absolute', top: LANE_HEIGHT, left: 0, width: minWidth, height: LANE_HEIGHT, background: '#f3e5f5', opacity: 0.3 }} />
                )}
                {demoState.caseActorVisible && (
                  <div style={{ position: 'absolute', top: LANE_HEIGHT * 2, left: 0, width: minWidth, height: LANE_HEIGHT, background: '#fff3e0', opacity: 0.3 }} />
                )}

                {/* Timeline events */}
                <svg style={{ position: 'absolute', top: 0, left: 0, width: minWidth, height: LANE_HEIGHT * 3 }}>
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

            {/* Draw connecting arrows */}
            {demoState.timelineEvents.map((event, idx) => {
              // Draw vertical arrow from decision to consequence
              if (event.type === 'consequence' && event.causedBy) {
                const causeEvent = demoState.timelineEvents.find(e => e.id === event.causedBy)
                if (causeEvent) {
                  const y1 = causeEvent.lane * LANE_HEIGHT + LANE_HEIGHT / 2
                  const y2 = event.lane * LANE_HEIGHT + LANE_HEIGHT / 2

                  // Adjust endpoints to account for rectangle height (70px / 2 = 35px from center)
                  const rectHalfHeight = 35
                  const direction = y2 > y1 ? 1 : -1  // downward or upward
                  const adjustedY1 = y1 + (rectHalfHeight * direction)
                  const adjustedY2 = y2 - (rectHalfHeight * direction)

                  // Arrow color matches the target lane (lighter for consequences)
                  let arrowColor: string
                  let arrowMarker: string
                  if (event.lane === 0) {  // Finder
                    arrowColor = '#BBDEFB'
                    arrowMarker = 'url(#arrowhead-blue)'
                  } else if (event.lane === 1) {  // Vendor
                    arrowColor = '#E1BEE7'
                    arrowMarker = 'url(#arrowhead-purple)'
                  } else {  // CaseActor
                    arrowColor = '#FFE0B2'
                    arrowMarker = 'url(#arrowhead-orange)'
                  }

                  return (
                    <g key={`arrow-vertical-${event.id}`}>
                      <line
                        x1={event.x}
                        y1={adjustedY1}
                        x2={event.x}
                        y2={adjustedY2}
                        stroke={arrowColor}
                        strokeWidth={2}
                        strokeDasharray="5,5"
                        markerEnd={arrowMarker}
                      />
                    </g>
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

            {/* Draw nodes (decisions and consequences) */}
            {demoState.timelineEvents.map((event) => {
              const isHovered = hoveredEvent === event.id
              const isDecision = event.type === 'decision'

              // Color based on lane and node type
              let fillColor: string
              if (event.lane === 0) {  // Finder lane
                if (isDecision) {
                  fillColor = isHovered ? '#1565C0' : '#1976D2'  // Dark blue for decisions
                } else {
                  fillColor = isHovered ? '#90CAF9' : '#BBDEFB'  // Light blue for consequences
                }
              } else if (event.lane === 1) {  // Vendor lane
                if (isDecision) {
                  fillColor = isHovered ? '#6A1B9A' : '#7B1FA2'  // Dark purple for decisions
                } else {
                  fillColor = isHovered ? '#CE93D8' : '#E1BEE7'  // Light purple for consequences
                }
              } else {  // CaseActor lane
                if (isDecision) {
                  fillColor = isHovered ? '#E65100' : '#F57C00'  // Dark orange for decisions
                } else {
                  fillColor = isHovered ? '#FFCC80' : '#FFE0B2'  // Light orange for consequences
                }
              }

              return (
                <AnimatedNode
                  key={`${event.id}-${event.timestamp || 0}`}
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

          {/* Consequences tooltip */}
          {hoveredEvent && (() => {
            const event = demoState.timelineEvents.find(e => e.id === hoveredEvent)
            if (!event) return null

            const isDecision = event.type === 'decision'
            let titleColor: string
            if (event.lane === 0) {  // Finder
              titleColor = isDecision ? '#1976D2' : '#90CAF9'
            } else if (event.lane === 1) {  // Vendor
              titleColor = isDecision ? '#7B1FA2' : '#CE93D8'
            } else {  // CaseActor
              titleColor = isDecision ? '#F57C00' : '#FFCC80'
            }

            return (
              <div
                style={{
                  position: 'absolute',
                  left: event.x + 40,
                  top: event.lane * LANE_HEIGHT + 50,
                  background: '#fff',
                  border: `2px solid ${titleColor}`,
                  borderRadius: '8px',
                  padding: '1rem',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                  width: '400px',
                  zIndex: 1000,
                }}
              >
                {!isDecision && (
                  <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: titleColor }}>
                    Effects on this Actor:
                  </h4>
                )}
                <ul style={{ margin: 0, padding: '0 0 0 1.25rem', fontSize: '0.8rem', lineHeight: '1.5' }}>
                  {event.consequences.map((consequence, idx) => (
                    <li key={idx} style={{ marginBottom: '0.25rem' }}>
                      {consequence}
                    </li>
                  ))}
                </ul>
              </div>
            )
          })()}
              </>
            )
          })()}
        </div>
      </div>

      {/* Bottom: Event log */}
      <div
        style={{
          height: '150px',
          background: '#fff',
          borderTop: '2px solid #ddd',
          padding: '1rem',
          overflowY: 'auto',
        }}
      >
        <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1rem' }}>Event Timeline</h3>
        {demoState.eventLog.length === 0 ? (
          <p style={{ color: '#999', fontStyle: 'italic' }}>
            No events yet. Click "Submit Report" on the Finder to begin.
          </p>
        ) : (
          <ul style={{ margin: 0, padding: '0 0 0 1.5rem', fontSize: '0.85rem' }}>
            {demoState.eventLog.map((event, idx) => (
              <li key={idx} style={{ marginBottom: '0.25rem' }}>
                {event}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default App
