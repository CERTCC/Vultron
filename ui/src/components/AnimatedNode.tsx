import { useEffect, useRef, useState } from 'react'
import { LANE_HEIGHT, NODE_WIDTH, NODE_WIDTH_HOVER, NODE_HEIGHT, NODE_HEIGHT_HOVER, NODE_WIDTH_COLLAPSED, NODE_HEIGHT_COLLAPSED, NODE_ANIMATION_MS } from '../constants'

interface TimelineEvent {
  id: string
  actor: string
  participantId?: string
  label: string
  x: number
  lane: number
  type: 'decision' | 'consequence'
  consequences: string[]
  causedBy?: string
  enablesNext?: boolean
  timestamp?: number
}

interface AnimatedNodeProps {
  event: TimelineEvent
  allEvents: TimelineEvent[]
  isHovered: boolean
  fillColor: string
  yPosition?: number  // Optional override for dynamic lane heights
  getCauseEventY?: (eventId: string) => number  // Function to get Y position of cause event
  isCollapsed?: boolean  // Whether the participant lane is collapsed
  // Animate the slide-in on first mount regardless of event.timestamp. The
  // default trigger (timestamp within the last 100ms) only fires for nodes
  // created live, so it never fires in Log Replay where timestamps come from
  // the (old) log. Replay reveals nodes by mounting them as the step index
  // advances, so mount is the correct moment to animate. A ref guard keeps it
  // to a single run per mount.
  animateOnMount?: boolean
  onMouseEnter: () => void
  onMouseLeave: () => void
}

export function AnimatedNode({
  event,
  allEvents,
  isHovered,
  fillColor,
  yPosition,
  getCauseEventY,
  isCollapsed = false,
  animateOnMount = false,
  onMouseEnter,
  onMouseLeave,
}: AnimatedNodeProps) {
  const gRef = useRef<SVGGElement>(null)
  const hasAnimatedRef = useRef(false)
  const [showTooltip, setShowTooltip] = useState(false)
  const isDecision = event.type === 'decision'
  const y = yPosition !== undefined ? yPosition : (event.lane * LANE_HEIGHT + LANE_HEIGHT / 2)

  // Use collapsed dimensions if lane is collapsed, otherwise use normal/hover dimensions
  let width: number, height: number
  if (isCollapsed) {
    width = NODE_WIDTH_COLLAPSED
    height = NODE_HEIGHT_COLLAPSED
  } else {
    width = isHovered ? NODE_WIDTH_HOVER : NODE_WIDTH
    height = isHovered ? NODE_HEIGHT_HOVER : NODE_HEIGHT
  }

  const rectX = event.x - width / 2
  const rectY = y - height / 2

  useEffect(() => {
    // Live demos: animate when the event was just created. Replay: animate once
    // on mount (timestamps are from the log, so the "just created" test can't fire).
    const isNewEvent = event.timestamp && Date.now() - event.timestamp < 100
    const shouldAnimate = animateOnMount ? !hasAnimatedRef.current : isNewEvent

    if (!isDecision && event.causedBy && shouldAnimate && gRef.current) {
      const causeEvent = allEvents.find((e) => e.id === event.causedBy)
      if (causeEvent) {
        hasAnimatedRef.current = true
        // Use the provided function to get cause Y, or fallback to old calculation
        const causeY = getCauseEventY
          ? getCauseEventY(causeEvent.id)
          : causeEvent.lane * LANE_HEIGHT + LANE_HEIGHT / 2
        const offsetY = causeY - y

        gRef.current.animate(
          [
            { transform: `translate(0, ${offsetY}px)`, opacity: 0 },
            { transform: 'translate(0, 0)', opacity: 1 },
          ],
          {
            duration: NODE_ANIMATION_MS,
            easing: 'ease-out',
            fill: 'forwards',
          }
        )
      }
    }
  }, [event.timestamp, isDecision, event.causedBy, allEvents, y, getCauseEventY, animateOnMount])

  const handleMouseEnter = () => {
    setShowTooltip(true)
    onMouseEnter()
  }

  const handleMouseLeave = () => {
    setShowTooltip(false)
    onMouseLeave()
  }

  return (
    <g ref={gRef}>
      <rect
        x={rectX}
        y={rectY}
        width={width}
        height={height}
        rx={isCollapsed ? "4" : "8"}
        ry={isCollapsed ? "4" : "8"}
        fill={fillColor}
        stroke="none"
        strokeWidth="0"
        style={{ cursor: 'pointer', transition: 'all 0.2s' }}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      />
      {/* Only show text when NOT collapsed */}
      {!isCollapsed && (
        <foreignObject
          x={rectX}
          y={rectY}
          width={width}
          height={height}
          style={{ pointerEvents: 'none' }}
        >
          <div
            style={{
              width: '100%',
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '8px',
              boxSizing: 'border-box',
              fontSize: '20px',
              fontWeight: 'bold',
              color: isDecision ? 'white' : 'black',
              textAlign: 'center',
              lineHeight: '1.2',
              wordBreak: 'break-word',
              overflowWrap: 'break-word',
              userSelect: 'none',
            }}
          >
            {event.label}
          </div>
        </foreignObject>
      )}
      {/* Tooltip on hover when collapsed */}
      {isCollapsed && showTooltip && (
        <foreignObject
          x={rectX + width + 5}
          y={rectY - 10}
          width={250}
          height={80}
          style={{ pointerEvents: 'none', overflow: 'visible' }}
        >
          <div
            style={{
              background: 'white',
              border: '2px solid #333',
              borderRadius: '8px',
              padding: '8px 12px',
              boxShadow: '0 4px 6px rgba(0,0,0,0.2)',
              fontSize: '14px',
              fontWeight: 'bold',
              color: 'black',
              whiteSpace: 'normal',
              wordBreak: 'break-word',
              zIndex: 1000,
            }}
          >
            {event.label}
          </div>
        </foreignObject>
      )}
    </g>
  )
}
