import React from 'react';
import { COLORS, FONT } from '../lib/theme';

interface Props { children: React.ReactNode; }
interface State { hasError: boolean; error: string; }

export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, error: '' };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error: error.message };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary] Caught render error:', error);
    if (info.componentStack) {
      console.error('[ErrorBoundary] Component stack:', info.componentStack);
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          height: '100%', padding: 40, fontFamily: FONT, color: COLORS.red,
        }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>!</div>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 8 }}>Erreur de rendu</div>
          <div style={{ fontSize: 11, color: COLORS.textDim, maxWidth: 400, textAlign: 'center', marginBottom: 16 }}>
            {this.state.error}
          </div>
          <button onClick={() => this.setState({ hasError: false, error: '' })} style={{
            padding: '6px 16px', borderRadius: 6, border: `1px solid ${COLORS.orangeAlpha(0.3)}`,
            backgroundColor: COLORS.orangeAlpha(0.08), color: COLORS.orange, fontSize: 11,
            cursor: 'pointer', fontFamily: 'inherit', fontWeight: 600,
          }}>
            Recharger la page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
