import { useState, useEffect, useCallback } from 'react';

function DocumentViewer({ previewUrl, totalPages }) {
    const [currentPage, setCurrentPage] = useState(1);
    const [zoom, setZoom] = useState(100);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);
    const [imgSrc, setImgSrc] = useState('');

    // Extract job_id from previewUrl like "/api/preview/abc-123"
    const jobId = previewUrl ? previewUrl.split('/').pop() : null;
    const pages = totalPages || 1;

    // Build image URL for current page
    useEffect(() => {
        if (!jobId) return;
        setLoading(true);
        setError(false);
        setImgSrc(`/api/preview/${jobId}/page/${currentPage}?t=${Date.now()}`);
    }, [jobId, currentPage]);

    const handlePrevPage = useCallback(() => {
        setCurrentPage((p) => Math.max(1, p - 1));
    }, []);

    const handleNextPage = useCallback(() => {
        setCurrentPage((p) => Math.min(pages, p + 1));
    }, [pages]);

    const handleZoomIn = () => setZoom((z) => Math.min(z + 25, 250));
    const handleZoomOut = () => setZoom((z) => Math.max(z - 25, 50));
    const handleZoomReset = () => setZoom(100);

    const handleImgLoad = () => {
        setLoading(false);
        setError(false);
    };

    const handleImgError = () => {
        setLoading(false);
        setError(true);
    };

    if (!previewUrl) {
        return (
            <div className="document-viewer">
                <div className="viewer-empty">
                    <span className="viewer-empty-icon">📄</span>
                    <p>Nenhum documento para visualizar</p>
                </div>
            </div>
        );
    }

    return (
        <div className="document-viewer">
            <div className="viewer-toolbar">
                <div className="viewer-toolbar-left">
                    {/* Page navigation */}
                    <button
                        className="viewer-btn"
                        onClick={handlePrevPage}
                        disabled={currentPage <= 1}
                        title="Página anterior"
                    >
                        ◀
                    </button>
                    <span className="viewer-page-info">
                        {currentPage} / {pages}
                    </span>
                    <button
                        className="viewer-btn"
                        onClick={handleNextPage}
                        disabled={currentPage >= pages}
                        title="Próxima página"
                    >
                        ▶
                    </button>
                </div>
                <div className="viewer-toolbar-right">
                    <button
                        className="viewer-btn"
                        onClick={handleZoomOut}
                        disabled={zoom <= 50}
                        title="Diminuir zoom"
                    >
                        −
                    </button>
                    <button
                        className="viewer-btn viewer-zoom-label"
                        onClick={handleZoomReset}
                        title="Resetar zoom"
                    >
                        {zoom}%
                    </button>
                    <button
                        className="viewer-btn"
                        onClick={handleZoomIn}
                        disabled={zoom >= 250}
                        title="Aumentar zoom"
                    >
                        +
                    </button>
                </div>
            </div>
            <div className="viewer-content">
                {loading && !error && (
                    <div className="viewer-loading">
                        <div className="spinner" />
                        <p>Carregando página {currentPage}...</p>
                    </div>
                )}

                {error && (
                    <div className="viewer-empty">
                        <span className="viewer-empty-icon">⚠️</span>
                        <p>Não foi possível carregar a página {currentPage}.</p>
                        <button
                            className="btn btn-secondary"
                            onClick={() => {
                                setError(false);
                                setLoading(true);
                                setImgSrc(`/api/preview/${jobId}/page/${currentPage}?t=${Date.now()}`);
                            }}
                        >
                            Tentar novamente
                        </button>
                        <a
                            href={previewUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="viewer-fallback-link"
                        >
                            Baixar PDF completo
                        </a>
                    </div>
                )}

                {imgSrc && !error && (
                    <div className="viewer-img-wrapper" style={{ textAlign: 'center' }}>
                        <img
                            src={imgSrc}
                            alt={`Página ${currentPage}`}
                            className="viewer-page-img"
                            style={{
                                width: `${zoom}%`,
                                maxWidth: 'none',
                            }}
                            onLoad={handleImgLoad}
                            onError={handleImgError}
                            draggable={false}
                        />
                    </div>
                )}
            </div>
        </div>
    );
}

export default DocumentViewer;
