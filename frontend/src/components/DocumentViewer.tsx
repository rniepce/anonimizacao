import { useState, useCallback, useMemo } from 'react';
import type { SensitiveEntity } from '../types';

interface Props {
    textByPage: Record<string, string>;
    totalPages: number;
    currentPage: number;
    onPageChange: (page: number) => void;
    entities: SensitiveEntity[];
    selectedEntityIds: Set<number>;
    customTerms: string[];
    onWordClick: (word: string) => void;
}

function DocumentViewer({
    textByPage,
    totalPages,
    currentPage,
    onPageChange,
    entities,
    selectedEntityIds,
    customTerms,
    onWordClick,
}: Props) {
    const [zoom, setZoom] = useState(100);
    const pages = totalPages || 1;

    const handlePrevPage = useCallback(() => {
        onPageChange(Math.max(1, currentPage - 1));
    }, [currentPage, onPageChange]);

    const handleNextPage = useCallback(() => {
        onPageChange(Math.min(pages, currentPage + 1));
    }, [pages, currentPage, onPageChange]);

    const handleZoomIn = () => setZoom((z) => Math.min(z + 25, 200));
    const handleZoomOut = () => setZoom((z) => Math.max(z - 25, 75));
    const handleZoomReset = () => setZoom(100);

    // Get page text
    const pageText = textByPage[String(currentPage)] || '';

    // Build a set of entity values on this page that are currently selected
    const highlightedValues = useMemo(() => {
        const set = new Set<string>();
        entities.forEach((entity, idx) => {
            if (entity.pagina === currentPage && selectedEntityIds.has(idx)) {
                set.add(entity.valor.toLowerCase());
            }
        });
        return set;
    }, [entities, currentPage, selectedEntityIds]);

    // Build set of custom terms (lowercased)
    const customTermsSet = useMemo(() => {
        return new Set(customTerms.map((t) => t.toLowerCase()));
    }, [customTerms]);

    // Build entity type lookup for color-coding
    const entityTypeMap = useMemo(() => {
        const map = new Map<string, string>();
        entities.forEach((entity, idx) => {
            if (selectedEntityIds.has(idx)) {
                map.set(entity.valor.toLowerCase(), entity.tipo);
            }
        });
        return map;
    }, [entities, selectedEntityIds]);

    // Render text with highlights
    const renderTextContent = useCallback(() => {
        if (!pageText) {
            return (
                <div className="viewer-empty">
                    <span className="viewer-empty-icon">📄</span>
                    <p>Texto não disponível para esta página.</p>
                </div>
            );
        }

        // Split text into words while preserving whitespace structure
        const lines = pageText.split('\n');

        return lines.map((line, lineIdx) => {
            if (line.trim() === '') {
                return <br key={lineIdx} />;
            }

            // Split line into words, preserving spaces
            const words = line.split(/(\s+)/);

            return (
                <div key={lineIdx} className="viewer-text-line">
                    {words.map((word, wordIdx) => {
                        // Whitespace — keep as-is
                        if (/^\s+$/.test(word)) {
                            return <span key={wordIdx}>{word}</span>;
                        }
                        if (!word) return null;

                        const wordLower = word.toLowerCase().replace(/[.,;:!?()\[\]{}""'']/g, '');

                        // Check if this word is part of an entity highlight
                        let isHighlighted = false;
                        let entityType = '';
                        for (const [entityValue, type] of entityTypeMap) {
                            if (entityValue.includes(wordLower) || wordLower.includes(entityValue)) {
                                isHighlighted = true;
                                entityType = type;
                                break;
                            }
                        }

                        // Check against full entity values more robustly
                        if (!isHighlighted) {
                            for (const val of highlightedValues) {
                                if (val.includes(wordLower) && wordLower.length > 2) {
                                    isHighlighted = true;
                                    entityType = entityTypeMap.get(val) || '';
                                    break;
                                }
                            }
                        }

                        const isCustom = customTermsSet.has(wordLower);

                        let className = 'viewer-word';
                        if (isHighlighted) {
                            className += ' highlighted';
                            className += ` type-${entityType.toLowerCase()}`;
                        }
                        if (isCustom) {
                            className += ' custom-selected';
                        }

                        return (
                            <span
                                key={wordIdx}
                                className={className}
                                onClick={() => {
                                    if (!isHighlighted && !isCustom && wordLower.length > 1) {
                                        onWordClick(word.replace(/[.,;:!?()\[\]{}""'']/g, ''));
                                    }
                                }}
                                title={
                                    isHighlighted
                                        ? `🔒 ${entityType}: será anonimizado`
                                        : isCustom
                                        ? '✅ Termo customizado selecionado'
                                        : 'Clique para adicionar como termo de anonimização'
                                }
                            >
                                {word}
                            </span>
                        );
                    })}
                </div>
            );
        });
    }, [pageText, highlightedValues, customTermsSet, entityTypeMap, onWordClick]);

    if (Object.keys(textByPage).length === 0) {
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
        <div className="document-viewer" role="region" aria-label="Visualizador de documento">
            <div className="viewer-toolbar">
                <div className="viewer-toolbar-left">
                    <button
                        className="viewer-btn"
                        onClick={handlePrevPage}
                        disabled={currentPage <= 1}
                        title="Página anterior"
                        aria-label="Página anterior"
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
                        aria-label="Próxima página"
                    >
                        ▶
                    </button>
                </div>
                <div className="viewer-toolbar-center">
                    <span className="viewer-hint">💡 Clique em uma palavra para anonimizar</span>
                </div>
                <div className="viewer-toolbar-right">
                    <button
                        className="viewer-btn"
                        onClick={handleZoomOut}
                        disabled={zoom <= 75}
                        title="Diminuir zoom"
                        aria-label="Diminuir zoom"
                    >
                        −
                    </button>
                    <button
                        className="viewer-btn viewer-zoom-label"
                        onClick={handleZoomReset}
                        title="Resetar zoom"
                        aria-label={`Zoom atual ${zoom}%, clique para resetar`}
                    >
                        {zoom}%
                    </button>
                    <button
                        className="viewer-btn"
                        onClick={handleZoomIn}
                        disabled={zoom >= 200}
                        title="Aumentar zoom"
                        aria-label="Aumentar zoom"
                    >
                        +
                    </button>
                </div>
            </div>
            <div className="viewer-content" role="document" aria-label={`Conteúdo da página ${currentPage}`}>
                <div
                    className="viewer-text-content"
                    style={{ fontSize: `${zoom}%` }}
                >
                    {renderTextContent()}
                </div>
            </div>
        </div>
    );
}

export default DocumentViewer;
