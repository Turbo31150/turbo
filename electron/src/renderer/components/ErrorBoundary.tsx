import React from 'react';

interface Props { children: React.ReactNode; }
interface State { hasError: boolean; error: string; }

export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, error: '' };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          height: '100%', padding: 40, fontFamily: 'Consolas, monospace', color: '#ef4444',
        }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>!</div>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 8 }}>Erreur de rendu</div>
          <div style={{ fontSize: 11, color: '#6b7280', maxWidth: 400, textAlign: 'center', marginBottom: 16 }}>
            {this.state.error}
          </div>
          <button onClick={() => this.setState({ hasError: false, error: '' })} style={{
            padding: '6px 16px', borderRadius: 6, border: '1px solid rgba(249,115,22,.3)',
            backgroundColor: 'rgba(249,115,22,.08)', color: '#f97316', fontSize: 11,
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
