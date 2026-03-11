import { useEffect, useRef, useState } from 'react';

function DocumentViewer({ previewUrl }) {
    const containerRef = useRef(null);
    const [zoom, setZoom] = useState(100);
    const [error, setError] = useState(false);

    const handleZoomIn = () => setZoom((z) => Math.min(z + 25, 200));
    const handleZoomOut = () => setZoom((z) => Math.max(z - 25, 50));
    const handleZoomReset = () => setZoom(100);

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
        <div className="document-viewer" ref={containerRef}>
            <div className="viewer-toolbar">
                <div className="viewer-toolbar-left">
                    <span className="viewer-title">📄 Visualização do Documento</span>
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
                        disabled={zoom >= 200}
                        title="Aumentar zoom"
                    >
                        +
                    </button>
                </div>
            </div>
            <div className="viewer-content">
                {error ? (
                    <div className="viewer-empty">
                        <span className="viewer-empty-icon">⚠️</span>
                        <p>Não foi possível carregar o preview do documento.</p>
                        <a
                            href={previewUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="viewer-fallback-link"
                        >
                            Abrir PDF em nova aba
                        </a>
                    </div>
                ) : (
                    <iframe
                        src={previewUrl}
                        title="Preview do Documento"
                        className="viewer-iframe"
                        style={{ transform: `scale(${zoom / 100})`, transformOrigin: 'top left', width: `${10000 / zoom}%`, height: `${10000 / zoom}%` }}
                        onError={() => setError(true)}
                    />
                )}
            </div>
        </div>
    );
}

export default DocumentViewer;
