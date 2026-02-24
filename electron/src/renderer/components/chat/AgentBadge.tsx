import React from 'react';

interface AgentBadgeProps {
  agent: string;
  small?: boolean;
}

const AGENT_COLORS: Record<string, string> = {
  'ia-deep': '#a855f7',     // purple
  'ia-fast': '#00d4ff',     // cyan
  'ia-check': '#00ff88',    // green
  'ia-trading': '#ffaa00',  // yellow
  'ia-system': '#8899aa',   // gray
  'ia-bridge': '#ff8844',   // orange
  'ia-consensus': '#ff66aa', // pink
};

function getAgentColor(agent: string): string {
  return AGENT_COLORS[agent] || '#4a6a8a';
}

export default function AgentBadge({ agent, small = false }: AgentBadgeProps) {
  const color = getAgentColor(agent);

  const style: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    padding: small ? '1px 6px' : '2px 10px',
    borderRadius: 12,
    fontSize: small ? 9 : 11,
    fontWeight: 'bold',
    fontFamily: 'Consolas, Courier New, monospace',
    color: color,
    backgroundColor: `${color}22`,
    border: `1px solid ${color}44`,
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    whiteSpace: 'nowrap',
  };

  return <span style={style}>{agent}</span>;
}

export { AGENT_COLORS, getAgentColor };
