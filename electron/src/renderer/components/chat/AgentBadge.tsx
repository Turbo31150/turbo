import React from 'react';
import { COLORS, FONT } from '../../lib/theme';

interface AgentBadgeProps {
  agent: string;
  small?: boolean;
}

const AGENT_COLORS: Record<string, string> = {
  'ia-deep': COLORS.purple,
  'ia-fast': COLORS.orange,
  'ia-check': COLORS.green,
  'ia-trading': COLORS.yellow,
  'ia-system': COLORS.textDim,
  'ia-bridge': COLORS.orange,
  'ia-consensus': COLORS.pink,
};

function getAgentColor(agent: string): string {
  return AGENT_COLORS[agent] || COLORS.textDim;
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
    fontFamily: FONT,
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
