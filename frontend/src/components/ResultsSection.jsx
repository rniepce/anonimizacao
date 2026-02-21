function maskValue(value) {
    if (!value) return '***';
    if (value.length <= 4) return '***';
    return value.substring(0, 3) + '***';
}

function truncateHash(hash) {
    if (!hash) return '---';
    return hash.substring(0, 16) + '...';
}

function ResultsSection({ analysisResults, anonymizationResults, onDownload, hasBlob }) {
    const jobId = analysisResults?.job_id || anonymizationResults?.jobId || '---';
    const pages = analysisResults?.total_paginas || 0;
    const identified = analysisResults?.total_identificados || 0;
    const redacted = anonymizationResults?.totalRedactions ?? '-';
    const time = analysisResults?.tempo_processamento_ms || anonymizationResults?.processingTimeMs || 0;
    const sensitiveData = analysisResults?.dados_sensiveis || [];

    return (
        <section className="results-section glass-card">
            <div className="section-header">
                <h2>📊 Resultados da Análise</h2>
                <span className="job-id">Job: {jobId}</span>
            </div>

            {/* Stats Cards */}
            <div className="stats-grid">
                <div className="stat-card">
                    <div className="stat-icon">📄</div>
                    <div className="stat-value">{pages}</div>
                    <div className="stat-label">Páginas</div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon">🎯</div>
                    <div className="stat-value">{identified}</div>
                    <div className="stat-label">Identificados</div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon">🔒</div>
                    <div className="stat-value">{redacted}</div>
                    <div className="stat-label">Anonimizados</div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon">⏱️</div>
                    <div className="stat-value">{time}ms</div>
                    <div className="stat-label">Tempo</div>
                </div>
            </div>

            {/* Sensitive Data Table */}
            {sensitiveData.length > 0 && (
                <div className="data-list">
                    <h4>Dados Sensíveis Identificados</h4>
                    <div className="data-table-wrapper">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Tipo</th>
                                    <th>Valor (Mascarado)</th>
                                    <th>Página</th>
                                    <th>Confiança</th>
                                </tr>
                            </thead>
                            <tbody>
                                {sensitiveData.map((item, index) => {
                                    const typeClass = item.tipo.toLowerCase().replace('_', '');
                                    return (
                                        <tr key={index}>
                                            <td>
                                                <span className={`type-badge ${typeClass}`}>{item.tipo}</span>
                                            </td>
                                            <td>{maskValue(item.valor)}</td>
                                            <td>{item.pagina}</td>
                                            <td>
                                                <div className="confidence-bar">
                                                    <div
                                                        className="confidence-fill"
                                                        style={{ width: `${item.confianca * 100}%` }}
                                                    />
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {sensitiveData.length === 0 && analysisResults && (
                <div className="data-list">
                    <h4>Dados Sensíveis Identificados</h4>
                    <div className="data-table-wrapper">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Tipo</th>
                                    <th>Valor (Mascarado)</th>
                                    <th>Página</th>
                                    <th>Confiança</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td colSpan="4" style={{ textAlign: 'center', color: 'var(--color-text-muted)' }}>
                                        Nenhum dado sensível identificado
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Download Section */}
            {hasBlob && anonymizationResults && (
                <div className="download-section">
                    <button className="btn btn-success btn-large" onClick={onDownload}>
                        <span className="btn-icon-text">⬇️</span>
                        Baixar PDF Anonimizado
                    </button>
                    <div className="hash-info">
                        <div className="hash-item">
                            <span className="hash-label">Hash Original:</span>
                            <code title={anonymizationResults.hashOriginal}>
                                {truncateHash(anonymizationResults.hashOriginal)}
                            </code>
                        </div>
                        <div className="hash-item">
                            <span className="hash-label">Hash Anonimizado:</span>
                            <code title={anonymizationResults.hashAnonymized}>
                                {truncateHash(anonymizationResults.hashAnonymized)}
                            </code>
                        </div>
                    </div>
                </div>
            )}
        </section>
    );
}

export default ResultsSection;
