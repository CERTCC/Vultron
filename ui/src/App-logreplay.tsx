import { useState, useCallback, useRef } from 'react'
import type { DemoState } from './types'
import './App.css'
import { LANE_HEIGHT, ACTOR_PANEL_WIDTH, NODE_COLORS, NODE_HEIGHT } from './constants'
import { ActorPanel, AnimatedNode } from './components'
import { getActiveLanes } from './state/participantHelpers'
import { parseJsonl, mergeLogEntries, type CaseLogEntry } from './utils/jsonlParser'
import { buildTimelineFromLogs } from './utils/logEventMapper'

function AppLogReplay() {
  const [demoState, setDemoState] = useState<DemoState | null>(null)
  const [accumulatedEntries, setAccumulatedEntries] = useState<CaseLogEntry[]>([])
  const [uploadCount, setUploadCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hoveredEvent, setHoveredEvent] = useState<string | null>(null)
  const [eventLogCollapsed, setEventLogCollapsed] = useState(false)
  const [currentEventIndex, setCurrentEventIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const timelineScrollRef = useRef<HTMLDivElement>(null)
  const sidebarScrollRef = useRef<HTMLDivElement>(null)
  const playIntervalRef = useRef<number | null>(null)

  // Handle file input - accumulates entries from multiple uploads
  const handleFileUpload = useCallback(async (files: FileList | null, shouldAccumulate = true) => {
    if (!files || files.length === 0) return

    setLoading(true)
    setError(null)

    try {
      const newEntries: CaseLogEntry[] = []

      // Read all uploaded files
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        const content = await file.text()
        const entries = parseJsonl(content)
        newEntries.push(...entries)
      }

      // Either accumulate or replace
      const allEntries = shouldAccumulate ? [...accumulatedEntries, ...newEntries] : newEntries
      setAccumulatedEntries(allEntries)
      setUploadCount(prev => prev + 1)

      // Merge and build timeline
      const mergedEntries = mergeLogEntries(allEntries)
      const state = buildTimelineFromLogs(mergedEntries)

      setDemoState(state)

      // Start at the first event (index 0)
      if (state.timelineEvents.length > 0) {
        setCurrentEventIndex(0)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load log files')
      console.error('Error processing log files:', err)
    } finally {
      setLoading(false)
    }
  }, [accumulatedEntries])

  // Load demo logs from known location
  const handleLoadDemoLogs = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      // Find the most recent case ID in devlogs/two-actor
      const response = await fetch('/devlogs/two-actor/case-list.json')
      if (!response.ok) {
        throw new Error('Could not find demo logs. Make sure the dev server is serving the devlogs folder.')
      }

      const { caseId } = await response.json()

      // Load all three log files
      const paths = [
        `/devlogs/two-actor/finder/${caseId}-case-log.jsonl`,
        `/devlogs/two-actor/vendor/${caseId}-case-log.jsonl`,
        `/devlogs/two-actor/case-actor/${caseId}-case-log.jsonl`,
      ]

      const allEntries: CaseLogEntry[] = []

      for (const path of paths) {
        try {
          const response = await fetch(path)
          if (response.ok) {
            const content = await response.text()
            const entries = parseJsonl(content)
            allEntries.push(...entries)
          }
        } catch (err) {
          console.warn(`Failed to load ${path}:`, err)
        }
      }

      if (allEntries.length === 0) {
        throw new Error('No log entries found. Please use file upload instead.')
      }

      setAccumulatedEntries(allEntries)

      // Merge and build timeline
      const mergedEntries = mergeLogEntries(allEntries)
      const state = buildTimelineFromLogs(mergedEntries)

      setDemoState(state)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load demo logs')
      console.error('Error loading demo logs:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  // NOTE: `handleLoadDemoLogs` is intentionally defined but not yet wired to a
  // button. The "load demo logs from a known location" feature is on hold until
  // the log generator emits the data this path needs — a `case-list.json` index
  // plus per-actor logs that carry causal links and aren't byte-identical
  // duplicates (see ui/CLAUDE.md §5–6). Referencing it here keeps the parked
  // implementation in the build (noUnusedLocals) without faking a wire-up.
  void handleLoadDemoLogs

  // Reset everything
  const handleReset = useCallback(() => {
    if (playIntervalRef.current) {
      clearInterval(playIntervalRef.current)
      playIntervalRef.current = null
    }
    setIsPlaying(false)
    setDemoState(null)
    setAccumulatedEntries([])
    setUploadCount(0)
    setCurrentEventIndex(0)
    setError(null)
  }, [])

  // Playback controls
  const handlePlay = useCallback(() => {
    if (!demoState) return
    setIsPlaying(true)

    playIntervalRef.current = window.setInterval(() => {
      setCurrentEventIndex(prev => {
        if (prev >= demoState.timelineEvents.length - 1) {
          if (playIntervalRef.current) {
            clearInterval(playIntervalRef.current)
            playIntervalRef.current = null
          }
          setIsPlaying(false)
          return prev
        }
        return prev + 1
      })
    }, 1000) // 1 second per event
  }, [demoState])

  const handlePause = useCallback(() => {
    if (playIntervalRef.current) {
      clearInterval(playIntervalRef.current)
      playIntervalRef.current = null
    }
    setIsPlaying(false)
  }, [])

  const handleStepForward = useCallback(() => {
    if (!demoState) return
    setCurrentEventIndex(prev => Math.min(prev + 1, demoState.timelineEvents.length - 1))
  }, [demoState])

  const handleStepBackward = useCallback(() => {
    setCurrentEventIndex(prev => Math.max(prev - 1, 0))
  }, [])

  const handleRewind = useCallback(() => {
    if (playIntervalRef.current) {
      clearInterval(playIntervalRef.current)
      playIntervalRef.current = null
    }
    setIsPlaying(false)
    setCurrentEventIndex(0)
  }, [])

  // Sync scrolling between timeline and sidebar
  const handleTimelineScroll = useCallback(() => {
    if (timelineScrollRef.current && sidebarScrollRef.current) {
      sidebarScrollRef.current.scrollTop = timelineScrollRef.current.scrollTop
    }
  }, [])

  const handleSidebarScroll = useCallback(() => {
    if (timelineScrollRef.current && sidebarScrollRef.current) {
      timelineScrollRef.current.scrollTop = sidebarScrollRef.current.scrollTop
    }
  }, [])

  // If no state loaded, show file upload UI
  if (!demoState) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        padding: '2rem',
        background: '#f5f5f5',
      }}>
        <div style={{
          background: 'white',
          padding: '2rem',
          borderRadius: '8px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          maxWidth: '600px',
          textAlign: 'center',
        }}>
          <h2 style={{ marginTop: 0, color: '#0d47a1' }}>Log Replay Demo</h2>
          <p style={{ color: '#666', marginBottom: '0.5rem' }}>
            Upload participant JSONL log files to visualize the Vultron protocol execution.
          </p>

          {uploadCount > 0 && accumulatedEntries.length > 0 && (
            <div style={{
              background: '#e8f5e9',
              border: '1px solid #4caf50',
              borderRadius: '4px',
              padding: '0.75rem 1rem',
              margin: '1rem 0',
              color: '#2e7d32',
            }}>
              ✓ Loaded {accumulatedEntries.length} log entries from {uploadCount} upload(s)
            </div>
          )}

          <div style={{
            margin: '2rem 0',
            padding: '2rem',
            border: '2px dashed #0d47a1',
            borderRadius: '4px',
            background: '#f0f7ff',
          }}>
            <input
              type="file"
              accept=".jsonl"
              multiple
              onChange={(e) => handleFileUpload(e.target.files, true)}
              id="log-file-input"
              style={{
                display: 'none',
              }}
            />
            <label
              htmlFor="log-file-input"
              style={{
                display: 'block',
                padding: '1rem 2rem',
                background: '#0d47a1',
                color: 'white',
                borderRadius: '4px',
                cursor: 'pointer',
                textAlign: 'center',
                fontWeight: 'bold',
                fontSize: '1rem',
                margin: '0 auto',
                width: 'fit-content',
              }}
            >
              📁 {uploadCount > 0 ? 'Add More Log Files' : 'Select Log Files'}
            </label>
            <p style={{
              textAlign: 'center',
              marginTop: '1rem',
              fontSize: '0.875rem',
              color: '#666',
              lineHeight: '1.5',
            }}>
              {uploadCount === 0 ? (
                <>
                  <strong>Upload from each folder separately:</strong><br />
                  1. Select file(s) from <code style={{ background: '#fff', padding: '0.125rem 0.375rem', borderRadius: '3px' }}>devlogs/two-actor/finder/</code><br />
                  2. Click "Add More" and select from <code style={{ background: '#fff', padding: '0.125rem 0.375rem', borderRadius: '3px' }}>vendor/</code><br />
                  3. Click "Add More" and select from <code style={{ background: '#fff', padding: '0.125rem 0.375rem', borderRadius: '3px' }}>case-actor/</code>
                </>
              ) : (
                <>You can add more files from other folders</>
              )}
            </p>

            {uploadCount > 0 && (
              <button
                onClick={handleReset}
                style={{
                  display: 'block',
                  margin: '1rem auto 0',
                  padding: '0.5rem 1rem',
                  background: '#f44336',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                }}
              >
                🔄 Start Over
              </button>
            )}
          </div>

          {loading && (
            <p style={{ color: '#0d47a1', fontWeight: 'bold' }}>
              Loading and processing log files...
            </p>
          )}

          {error && (
            <p style={{ color: '#d32f2f', fontWeight: 'bold' }}>
              Error: {error}
            </p>
          )}

          <div style={{ marginTop: '2rem', fontSize: '0.875rem', color: '#666' }}>
            <p><strong>Example logs location:</strong></p>
            <code style={{
              display: 'block',
              background: '#f5f5f5',
              padding: '0.5rem',
              borderRadius: '4px',
              marginTop: '0.5rem',
            }}>
              devlogs/two-actor/*/urn_uuid_*-case-log.jsonl
            </code>
          </div>
        </div>
      </div>
    )
  }

  // Render timeline visualization
  const activeLanes = getActiveLanes(demoState)
  const totalHeight = activeLanes.length * LANE_HEIGHT

  return (
    <div style={{
      display: 'flex',
      height: '100%',
      overflow: 'hidden',
      position: 'relative',
    }}>
      {/* Left sidebar with actor panels */}
      <div
        ref={sidebarScrollRef}
        onScroll={handleSidebarScroll}
        style={{
          width: `${ACTOR_PANEL_WIDTH}px`,
          background: '#f5f5f5',
          overflowY: 'auto',
          overflowX: 'hidden',
          position: 'relative',
          zIndex: 10,
          boxShadow: '2px 0 8px rgba(0,0,0,0.1)',
        }}
      >
        <div style={{ height: `${totalHeight}px`, position: 'relative' }}>
          {activeLanes.map((participant) => (
            <ActorPanel
              key={participant.id}
              participantId={participant.id}
              name={participant.name}
              role={participant.role}
              color={participant.color}
              rmState={participant.rmState}
              emState={demoState.emState}
              vfdState={participant.vfdState}
              pxaState={demoState.pxaState}
              actions={[]} // No actions in replay mode
              onActionClick={() => {}}
              isCollapsed={false}
              onToggleCollapse={() => {}}
            />
          ))}
        </div>
      </div>

      {/* Main timeline area */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {/* Timeline header */}
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '80px',
          background: '#2d2d2d',
          borderBottom: '2px solid #0d47a1',
          display: 'flex',
          flexDirection: 'column',
          padding: '0.5rem 1rem',
          gap: '0.5rem',
          zIndex: 5,
        }}>
          {/* Top row - title and file controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <h3 style={{ margin: 0, color: 'white', fontSize: '1.125rem' }}>
              Case Timeline ({demoState.timelineEvents.length} events)
            </h3>
            <div style={{
              marginLeft: 'auto',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}>
              <span style={{
                color: '#4caf50',
                fontSize: '0.875rem',
                background: 'rgba(76, 175, 80, 0.1)',
                padding: '0.25rem 0.75rem',
                borderRadius: '4px',
              }}>
                ✓ {accumulatedEntries.length} entries from {uploadCount} upload(s)
              </span>
              <input
                type="file"
                accept=".jsonl"
                multiple
                onChange={(e) => handleFileUpload(e.target.files, true)}
                id="add-more-files"
                style={{ display: 'none' }}
              />
              <label
                htmlFor="add-more-files"
                style={{
                  padding: '0.5rem 1rem',
                  background: '#4caf50',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                  fontWeight: 'bold',
                }}
              >
                📁 Add More Files
              </label>
              <button
                onClick={handleReset}
                style={{
                  padding: '0.5rem 1rem',
                  background: '#f44336',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                }}
              >
                🔄 Start Over
              </button>
            </div>
          </div>

          {/* Bottom row - playback controls */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.25rem',
            background: '#e3f2fd',
            borderRadius: '4px',
          }}>
            <button
              onClick={handleRewind}
              disabled={currentEventIndex === 0}
              style={{
                padding: '0.375rem 0.75rem',
                background: currentEventIndex === 0 ? '#555' : '#0d47a1',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: currentEventIndex === 0 ? 'not-allowed' : 'pointer',
                fontSize: '0.875rem',
              }}
              title="Rewind to start"
            >
              ⏮
            </button>
            <button
              onClick={handleStepBackward}
              disabled={currentEventIndex === 0}
              style={{
                padding: '0.375rem 0.75rem',
                background: currentEventIndex === 0 ? '#555' : '#0d47a1',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: currentEventIndex === 0 ? 'not-allowed' : 'pointer',
                fontSize: '0.875rem',
              }}
              title="Previous event"
            >
              ⏪
            </button>
            <button
              onClick={isPlaying ? handlePause : handlePlay}
              style={{
                padding: '0.375rem 1rem',
                background: '#4caf50',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '0.875rem',
                fontWeight: 'bold',
              }}
              title={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? '⏸ Pause' : '▶ Play'}
            </button>
            <button
              onClick={handleStepForward}
              disabled={currentEventIndex >= demoState.timelineEvents.length - 1}
              style={{
                padding: '0.375rem 0.75rem',
                background: currentEventIndex >= demoState.timelineEvents.length - 1 ? '#555' : '#0d47a1',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: currentEventIndex >= demoState.timelineEvents.length - 1 ? 'not-allowed' : 'pointer',
                fontSize: '0.875rem',
              }}
              title="Next event"
            >
              ⏩
            </button>
            <span style={{
              color: '#ddd',
              fontSize: '0.875rem',
              marginLeft: '0.5rem',
            }}>
              Event {currentEventIndex + 1} of {demoState.timelineEvents.length}
            </span>
          </div>
        </div>

        {/* Scrollable timeline */}
        <div
          ref={timelineScrollRef}
          onScroll={handleTimelineScroll}
          style={{
            position: 'absolute',
            top: '80px',
            left: 0,
            right: 0,
            bottom: eventLogCollapsed ? '40px' : '200px',
            overflowY: 'auto',
            overflowX: 'auto',
            background: '#fafafa',
          }}
        >
          <div style={{
            height: `${totalHeight}px`,
            width: '100%',
            minWidth: '1200px',
            position: 'relative',
          }}>
            {/* Lane backgrounds */}
            {activeLanes.map((participant) => (
              <div
                key={`lane-${participant.id}`}
                style={{
                  position: 'absolute',
                  top: participant.laneIndex * LANE_HEIGHT,
                  left: 0,
                  right: 0,
                  height: LANE_HEIGHT,
                  borderBottom: '1px solid #ddd',
                  background: participant.laneIndex % 2 === 0 ? '#ffffff' : '#f9f9f9',
                }}
              />
            ))}

            {/* SVG layer for timeline events */}
            <svg
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                pointerEvents: 'none',
              }}
            >
              {/* Arrow markers */}
              <defs>
                <marker
                  id="arrowhead-blue"
                  markerWidth="16"
                  markerHeight="10"
                  refX="16"
                  refY="5"
                  orient="auto"
                >
                  <polygon points="0 0, 16 5, 0 10" fill="#BBDEFB" />
                </marker>
                <marker
                  id="arrowhead-purple"
                  markerWidth="16"
                  markerHeight="10"
                  refX="16"
                  refY="5"
                  orient="auto"
                >
                  <polygon points="0 0, 16 5, 0 10" fill="#E1BEE7" />
                </marker>
                <marker
                  id="arrowhead-orange"
                  markerWidth="16"
                  markerHeight="10"
                  refX="16"
                  refY="5"
                  orient="auto"
                >
                  <polygon points="0 0, 16 5, 0 10" fill="#FFE0B2" />
                </marker>
              </defs>

              {/* Draw arrows from decision to consequence nodes */}
              {demoState.timelineEvents.slice(0, currentEventIndex + 1).map((event) => {
                if (event.causedBy) {
                  const causeEvent = demoState.timelineEvents.find((e) => e.id === event.causedBy)
                  if (causeEvent) {
                    const allParticipants = Array.from(demoState.participants.values())
                    const y1 = causeEvent.lane * LANE_HEIGHT + LANE_HEIGHT / 2
                    const y2 = event.lane * LANE_HEIGHT + LANE_HEIGHT / 2

                    const sourceRectHalfHeight = NODE_HEIGHT / 2
                    const targetRectHalfHeight = NODE_HEIGHT / 2

                    const direction = y2 > y1 ? 1 : -1
                    const adjustedY1 = y1 + (sourceRectHalfHeight * direction)
                    const adjustedY2 = y2 - (targetRectHalfHeight * direction)

                    // Determine arrow color based on target participant
                    let arrowColor: string
                    let arrowMarker: string
                    const targetParticipant = allParticipants.find(p => p.laneIndex === event.lane)

                    if (targetParticipant) {
                      if (targetParticipant.id === 'finder') {
                        arrowColor = '#BBDEFB'
                        arrowMarker = 'url(#arrowhead-blue)'
                      } else if (targetParticipant.id === 'vendor-1') {
                        arrowColor = '#E1BEE7'
                        arrowMarker = 'url(#arrowhead-purple)'
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
                        strokeWidth={3}
                        strokeDasharray="6,6"
                        markerEnd={arrowMarker}
                      />
                    )
                  }
                }
                return null
              })}

              {/* Draw timeline event nodes */}
              {demoState.timelineEvents.slice(0, currentEventIndex + 1).map((event) => {
              const participant = demoState.participants.get(event.participantId || event.actor)
              if (!participant) return null

              // Get the appropriate colors for this participant
              let participantColors: { decision: string; decisionHover: string; consequence: string; consequenceHover: string }
              const pid = event.participantId || event.actor
              if (pid === 'finder') {
                participantColors = NODE_COLORS.finder
              } else if (pid === 'vendor-1') {
                participantColors = NODE_COLORS.vendor1
              } else if (pid === 'caseactor') {
                participantColors = NODE_COLORS.caseactor
              } else {
                participantColors = NODE_COLORS.finder // fallback
              }

              const fillColor = event.type === 'decision'
                ? (hoveredEvent === event.id ? participantColors.decisionHover : participantColors.decision)
                : (hoveredEvent === event.id ? participantColors.consequenceHover : participantColors.consequence)

              const yPosition = event.lane * LANE_HEIGHT + (LANE_HEIGHT - NODE_HEIGHT) / 2

              return (
                <AnimatedNode
                  key={event.id}
                  event={event}
                  allEvents={demoState.timelineEvents}
                  isHovered={hoveredEvent === event.id}
                  fillColor={fillColor}
                  yPosition={yPosition}
                  isCollapsed={false}
                  onMouseEnter={() => setHoveredEvent(event.id)}
                  onMouseLeave={() => setHoveredEvent(null)}
                />
              )
              })}
            </svg>
          </div>
        </div>

        {/* Event log panel */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: eventLogCollapsed ? '40px' : '200px',
          background: '#2d2d2d',
          borderTop: '2px solid #0d47a1',
          transition: 'height 0.3s ease',
        }}>
          <div
            onClick={() => setEventLogCollapsed(!eventLogCollapsed)}
            style={{
              height: '40px',
              display: 'flex',
              alignItems: 'center',
              padding: '0 1rem',
              cursor: 'pointer',
              background: '#0d47a1',
              color: 'white',
              fontWeight: 'bold',
            }}
          >
            <span>Event Log ({demoState.eventLog.length} entries)</span>
            <span style={{ marginLeft: 'auto' }}>
              {eventLogCollapsed ? '▲' : '▼'}
            </span>
          </div>

          {!eventLogCollapsed && (
            <div style={{
              height: '160px',
              overflowY: 'auto',
              padding: '0.5rem 1rem',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              color: '#ddd',
            }}>
              {demoState.eventLog.map((log, idx) => (
                <div key={idx} style={{ marginBottom: '0.25rem' }}>
                  {log}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default AppLogReplay
