/**
 * Utilities for parsing JSONL case log files
 */

export interface CaseLogEntry {
  id: string
  type: string
  published: string
  updated: string
  caseId: string
  logIndex: number
  disposition: string
  logObjectId: string
  eventType: string
  payloadSnapshot: any
  prevLogHash: string
  entryHash: string
  receivedAt: string
}

export interface ParticipantStatus {
  id: string
  type: string
  name: string
  rmState?: string
  vfdState?: string
  caseEngagement?: boolean
  embargoAdherence?: boolean
  caseStatus?: {
    emState: string
    pxaState: string
  }
}

/**
 * Parse a JSONL file content into an array of CaseLogEntry objects
 */
export function parseJsonl(content: string): CaseLogEntry[] {
  const lines = content.trim().split('\n')
  const entries: CaseLogEntry[] = []

  for (const line of lines) {
    if (line.trim()) {
      try {
        const entry = JSON.parse(line)
        entries.push(entry)
      } catch (error) {
        console.error('Failed to parse JSONL line:', error, line)
      }
    }
  }

  return entries
}

/**
 * Extract actor identifier from actor URL
 * e.g., "http://vendor:7999/api/v2/actors/05b4a53d-d973-4296-b186-31052a478587" -> "vendor"
 * e.g., "http://finder:7999/api/v2/actors/c61bb87c-e5e4-4ec9-a03f-e5484656497f" -> "finder"
 */
export function extractActorType(actorUrl: string): string {
  if (!actorUrl) return 'unknown'

  if (actorUrl.includes('case-actor')) return 'caseactor'
  if (actorUrl.includes('//vendor:')) return 'vendor-1'
  if (actorUrl.includes('//finder:')) return 'finder'

  return 'unknown'
}

/**
 * Extract participant status from a log entry payload
 */
export function extractParticipantStatus(payload: any): ParticipantStatus | null {
  if (!payload || !payload.object) return null

  const obj = payload.object
  if (obj.type === 'ParticipantStatus') {
    return {
      id: obj.id,
      type: obj.type,
      name: obj.name,
      rmState: obj.rmState,
      vfdState: obj.vfdState,
      caseEngagement: obj.caseEngagement,
      embargoAdherence: obj.embargoAdherence,
      caseStatus: obj.caseStatus,
    }
  }

  return null
}

/**
 * Load JSONL file from URL or file system
 */
export async function loadJsonlFile(path: string): Promise<CaseLogEntry[]> {
  try {
    const response = await fetch(path)
    if (!response.ok) {
      throw new Error(`Failed to load file: ${response.statusText}`)
    }
    const content = await response.text()
    return parseJsonl(content)
  } catch (error) {
    console.error('Error loading JSONL file:', error)
    throw error
  }
}

/**
 * Merge and sort log entries from multiple participants by timestamp
 */
export function mergeLogEntries(entries: CaseLogEntry[]): CaseLogEntry[] {
  return entries.sort((a, b) => {
    const timeA = new Date(a.receivedAt).getTime()
    const timeB = new Date(b.receivedAt).getTime()
    return timeA - timeB
  })
}
