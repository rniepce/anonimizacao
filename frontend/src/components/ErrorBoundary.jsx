import { Component } from 'react';

class ErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error('ErrorBoundary caught:', error, errorInfo);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
            return (
                <section className="glass-card" style={{ padding: '2rem', textAlign: 'center', margin: '2rem auto', maxWidth: '600px' }}>
                    <h2>⚠️ Ocorreu um erro</h2>
                    <p style={{ color: 'var(--color-text-muted)', margin: '1rem 0' }}>
                        {this.state.error?.message || 'Erro inesperado na aplicação'}
                    </p>
                    <button className="btn btn-primary" onClick={this.handleReset}>
                        🔄 Tentar novamente
                    </button>
                </section>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
