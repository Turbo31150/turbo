import React from 'react';

interface AgentBadgeProps {
  agent: string;
  small?: boolean;
}

const AGENT_COLORS: Record<string, string> = {
  'ia-deep': '#c084fc',     // purple
  'ia-fast': '#f97316',     // orange
  'ia-check': '#10b981',    // green
  'ia-trading': '#eab308',  // yellow
  'ia-system': '#6b7280',   // gray
  'ia-bridge': '#f97316',   // orange
  'ia-consensus': '#ec4899', // pink
};

function getAgentColor(agent: string): string {
  return AGENT_COLORS[agent] || '#6b7280';
}

export default function AgentBadge({ agent, small = false }: AgentBadgeProps) {
  const color = getAgentColor(agent);

  const style: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    padding: small ? '1px 6px' : '2px 10px',
    borderRadius: 12,
    fontSize: small ? 9 : 11,
    fontWeight: 700,
    fontFamily: 'Consolas, "Courier New", monospace',
    color: color,
    backgroundColor: `${color}22`,
    border: `1px solid ${color}44`,
    letterSpacing: .5,
    textTransform: 'uppercase',
    whiteSpace: 'nowrap',
  };

  return <span style={style}>{agent}</span>;
}

export { AGENT_COLORS, getAgentColor };
