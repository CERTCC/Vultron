/**
 * Constants and configuration for the Vultron demo
 */

export const LANE_HEIGHT = 400
export const ACTOR_PANEL_WIDTH = 300

// Node dimensions
export const NODE_WIDTH = 210
export const NODE_WIDTH_HOVER = 225
export const NODE_HEIGHT = 100
export const NODE_HEIGHT_HOVER = 110

// Maximum number of vendors supported in multi-vendor demo
export const MAX_VENDORS = 5

// Color palette for vendors (5 distinct, accessible colors)
const VENDOR_COLOR_PALETTE = [
  '#f3e5f5',  // Light purple (vendor 1)
  '#e1f5e1',  // Light green (vendor 2)
  '#fff9c4',  // Light yellow (vendor 3)
  '#ffccbc',  // Light orange (vendor 4)
  '#e1bee7',  // Light lavender (vendor 5)
]

// Base colors for non-vendor participants
const BASE_PARTICIPANT_COLORS = {
  finder: '#e3f2fd',      // Light blue
  caseactor: '#fff3e0',   // Light orange
}

// Generate participant colors dynamically
export const PARTICIPANT_COLORS = {
  ...BASE_PARTICIPANT_COLORS,
  // Legacy keys for backward compatibility
  vendor1: VENDOR_COLOR_PALETTE[0],
  vendor2: VENDOR_COLOR_PALETTE[1],
}

// Function to get vendor color by index (1-based)
export function getVendorColor(vendorNumber: number): string {
  const index = vendorNumber - 1
  if (index >= 0 && index < VENDOR_COLOR_PALETTE.length) {
    return VENDOR_COLOR_PALETTE[index]
  }
  // Fallback to cycling through palette
  return VENDOR_COLOR_PALETTE[index % VENDOR_COLOR_PALETTE.length]
}

// Node colors for timeline events - darker versions of swimlane colors
const VENDOR_NODE_COLORS = [
  {
    decision: '#7B1FA2',        // Dark purple
    decisionHover: '#6A1B9A',
    consequence: '#E1BEE7',     // Light purple
    consequenceHover: '#CE93D8'
  },
  {
    decision: '#388E3C',        // Dark green
    decisionHover: '#2E7D32',
    consequence: '#C8E6C9',     // Light green
    consequenceHover: '#A5D6A7'
  },
  {
    decision: '#F9A825',        // Dark yellow
    decisionHover: '#F57F17',
    consequence: '#FFF9C4',     // Light yellow
    consequenceHover: '#FFF59D'
  },
  {
    decision: '#F4511E',        // Dark orange
    decisionHover: '#E64A19',
    consequence: '#FFCCBC',     // Light orange
    consequenceHover: '#FFAB91'
  },
  {
    decision: '#8E24AA',        // Dark lavender
    decisionHover: '#7B1FA2',
    consequence: '#E1BEE7',     // Light lavender
    consequenceHover: '#CE93D8'
  },
]

const BASE_NODE_COLORS = {
  finder: {
    decision: '#1976D2',        // Dark blue for decisions
    decisionHover: '#1565C0',   // Darker blue on hover
    consequence: '#BBDEFB',     // Light blue for consequences
    consequenceHover: '#90CAF9' // Slightly darker on hover
  },
  caseactor: {
    decision: '#F57C00',        // Dark orange for decisions
    decisionHover: '#E65100',   // Darker orange on hover
    consequence: '#FFE0B2',     // Light orange for consequences
    consequenceHover: '#FFCC80' // Slightly darker on hover
  }
}

export const NODE_COLORS = {
  ...BASE_NODE_COLORS,
  // Legacy keys for backward compatibility
  vendor1: VENDOR_NODE_COLORS[0],
  vendor2: VENDOR_NODE_COLORS[1],
}

// Function to get vendor node colors by index (1-based)
export function getVendorNodeColors(vendorNumber: number): {
  decision: string
  decisionHover: string
  consequence: string
  consequenceHover: string
} {
  const index = vendorNumber - 1
  if (index >= 0 && index < VENDOR_NODE_COLORS.length) {
    return VENDOR_NODE_COLORS[index]
  }
  // Fallback to cycling through palette
  return VENDOR_NODE_COLORS[index % VENDOR_NODE_COLORS.length]
}

export const PARTICIPANT_ROLES = {
  finder: 'FINDER, REPORTER',
  vendor: 'VENDOR, CASE_OWNER',
  vendor2: 'VENDOR',
  caseactor: 'COORDINATOR, CASE_MANAGER (virtual)',
}

export const INITIAL_X_POSITION = 130
export const X_INCREMENT = 300
