import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertOctagon, RotateCcw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('SafarSetu Error Boundary caught an error:', error, errorInfo);
  }

  private handleReload = () => {
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.5rem',
            background: 'var(--bg-app, #f8fafc)',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          }}
        >
          <div
            style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '12px',
              padding: '2rem',
              maxWidth: '480px',
              width: '100%',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                background: '#fee2e2',
                color: '#dc2626',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 1rem',
              }}
            >
              <AlertOctagon size={24} />
            </div>

            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem', color: '#0f172a' }}>
              Something went wrong
            </h2>

            <p style={{ fontSize: '0.9rem', color: '#64748b', marginBottom: '1.25rem', lineHeight: '1.5' }}>
              SafarSetu encountered an unexpected issue while rendering. Your data is safe.
            </p>

            {this.state.error && (
              <div
                style={{
                  background: '#f1f5f9',
                  borderRadius: '6px',
                  padding: '0.75rem',
                  fontSize: '0.8rem',
                  color: '#475569',
                  fontFamily: 'monospace',
                  marginBottom: '1.25rem',
                  textAlign: 'left',
                  overflowX: 'auto',
                }}
              >
                {this.state.error.message || String(this.state.error)}
              </div>
            )}

            <button
              onClick={this.handleReload}
              style={{
                background: '#0f766e',
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                padding: '0.65rem 1.25rem',
                fontSize: '0.9rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <RotateCcw size={16} />
              <span>Reload SafarSetu</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
