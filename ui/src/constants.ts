/**
 * Constants and configuration for the Vultron demo
 */

export const LANE_HEIGHT = 295
export const ACTOR_PANEL_WIDTH = 300

export const PARTICIPANT_COLORS = {
  finder: '#e3f2fd',      // Light blue
  vendor1: '#f3e5f5',     // Light purple
  vendor2: '#e1f5e1',     // Light green
  caseactor: '#fff3e0',   // Light orange
}

// Node colors for timeline events - darker versions of swimlane colors
export const NODE_COLORS = {
  finder: {
    decision: '#1976D2',        // Dark blue for decisions
    decisionHover: '#1565C0',   // Darker blue on hover
    consequence: '#BBDEFB',     // Light blue for consequences
    consequenceHover: '#90CAF9' // Slightly darker on hover
  },
  vendor1: {
    decision: '#7B1FA2',        // Dark purple for decisions
    decisionHover: '#6A1B9A',   // Darker purple on hover
    consequence: '#E1BEE7',     // Light purple for consequences
    consequenceHover: '#CE93D8' // Slightly darker on hover
  },
  vendor2: {
    decision: '#388E3C',        // Dark green for decisions
    decisionHover: '#2E7D32',   // Darker green on hover
    consequence: '#C8E6C9',     // Light green for consequences
    consequenceHover: '#A5D6A7' // Slightly darker on hover
  },
  caseactor: {
    decision: '#F57C00',        // Dark orange for decisions
    decisionHover: '#E65100',   // Darker orange on hover
    consequence: '#FFE0B2',     // Light orange for consequences
    consequenceHover: '#FFCC80' // Slightly darker on hover
  }
}

export const PARTICIPANT_ROLES = {
  finder: 'FINDER, REPORTER',
  vendor: 'VENDOR, CASE_OWNER',
  vendor2: 'VENDOR',
  caseactor: 'COORDINATOR, CASE_MANAGER (virtual)',
}

export const INITIAL_X_POSITION = 100
export const X_INCREMENT = 250
