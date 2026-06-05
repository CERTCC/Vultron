import { useEffect, useRef } from 'react'
import { LANE_HEIGHT, NODE_WIDTH, NODE_WIDTH_HOVER, NODE_HEIGHT, NODE_HEIGHT_HOVER } from '../constants'

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
  onMouseEnter: () => void
  onMouseLeave: () => void
}

export function AnimatedNode({
  event,
  allEvents,
  isHovered,
  fillColor,
  onMouseEnter,
  onMouseLeave,
}: AnimatedNodeProps) {
  const gRef = useRef<SVGGElement>(null)
  const isDecision = event.type === 'decision'
  const y = event.lane * LANE_HEIGHT + LANE_HEIGHT / 2
  const width = isHovered ? NODE_WIDTH_HOVER : NODE_WIDTH
  const height = isHovered ? NODE_HEIGHT_HOVER : NODE_HEIGHT
  const rectX = event.x - width / 2
  const rectY = y - height / 2

  useEffect(() => {
    const isNewEvent = event.timestamp && Date.now() - event.timestamp < 100

    if (!isDecision && event.causedBy && isNewEvent && gRef.current) {
      const causeEvent = allEvents.find((e) => e.id === event.causedBy)
      if (causeEvent) {
        const causeY = causeEvent.lane * LANE_HEIGHT + LANE_HEIGHT / 2
        const offsetY = causeY - y

        gRef.current.animate(
          [
            { transform: `translate(0, ${offsetY}px)`, opacity: 0 },
            { transform: 'translate(0, 0)', opacity: 1 },
          ],
          {
            duration: 1500,
            easing: 'ease-out',
            fill: 'forwards',
          }
        )
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
        fontSize="13"
        fill={isDecision ? 'white' : 'black'}
        fontWeight="bold"
        style={{ pointerEvents: 'none', userSelect: 'none' }}
      >
        {event.label}
      </text>
    </g>
  )
}
