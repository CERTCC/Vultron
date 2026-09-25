// Swimlane background component for actor-based workflow visualization

interface SwimlanesProps {
  lanes: Array<{
    id: string;
    label: string;
    color: string;
    y: number;
    height: number;
  }>;
}

export function Swimlanes({ lanes }: SwimlanesProps) {
  return (
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, pointerEvents: 'none' }}>
      {lanes.map((lane) => (
        <div
          key={lane.id}
          style={{
            position: 'absolute',
            top: lane.y,
            left: 0,
            right: 0,
            height: lane.height,
            backgroundColor: lane.color,
            borderBottom: '2px solid #ddd',
            display: 'flex',
            alignItems: 'center',
            paddingLeft: '1rem',
          }}
        >
          <div
            style={{
              position: 'sticky',
              left: '1rem',
              fontWeight: 'bold',
              fontSize: '1.2rem',
              color: '#333',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              pointerEvents: 'auto',
            }}
          >
            {lane.label}
          </div>
        </div>
      ))}
    </div>
  );
}
