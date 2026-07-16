import { useEffect, useRef } from 'react'
import { LANE_HEIGHT, NODE_WIDTH, NODE_WIDTH_HOVER, NODE_HEIGHT, NODE_HEIGHT_HOVER, NODE_HEIGHT_COLLAPSED, NODE_ANIMATION_MS } from '../constants'

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
  const isDecision = event.type === 'decision'
  const y = yPosition !== undefined ? yPosition : (event.lane * LANE_HEIGHT + LANE_HEIGHT / 2)

  // Collapsing affects HEIGHT ONLY — the node keeps its full width (and label) so
  // it stays readable when collapsed; only the vertical size shrinks.
  const width = isHovered ? NODE_WIDTH_HOVER : NODE_WIDTH
  const height = isCollapsed
    ? NODE_HEIGHT_COLLAPSED
    : (isHovered ? NODE_HEIGHT_HOVER : NODE_HEIGHT)

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
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
      />
      {/* Label always shows at the SAME font size whether collapsed or not —
          collapse only shrinks the box vertically, and the collapsed height fits
          two lines of this font, so labels wrap cleanly with no ellipsis. */}
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
            padding: isCollapsed ? '4px 8px' : '8px',
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
    </g>
  )
}
