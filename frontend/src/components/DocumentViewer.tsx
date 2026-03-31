import { useState, useCallback, useMemo, MouseEvent } from 'react';
import type { SensitiveEntity, CustomTerm } from '../types';

interface Props {
    textByPage: Record<string, string>;
    totalPages: number;
    currentPage: number;
    onPageChange: (page: number) => void;
    entities: SensitiveEntity[];
    selectedEntityIds: Set<number>;
    customTerms: CustomTerm[];
    onWordClick: (word: string, tipo: string) => void;
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
    const [popover, setPopover] = useState<{ word: string; x: number; y: number } | null>(null);
    const [selectedType, setSelectedType] = useState('OUTRO');
    const [customType, setCustomType] = useState('');
    const pages = totalPages || 1;

    const pageText = textByPage[String(currentPage)] || '';

    const ENTITY_TYPES = [
        { value: 'CPF', label: 'CPF' },
        { value: 'CNPJ', label: 'CNPJ' },
        { value: 'PESSOA', label: 'Pessoa' },
        { value: 'ORGANIZACAO', label: 'Organização' },
        { value: 'DOCUMENTO', label: 'Documento' },
        { value: 'DINHEIRO', label: 'Dinheiro' },
        { value: 'EMAIL', label: 'E-mail' },
        { value: 'TELEFONE', label: 'Telefone' },
        { value: 'ENDERECO', label: 'Endereço' },
        { value: 'PROC_CNJ', label: 'Proc. CNJ' },
        { value: 'OUTRO', label: 'Outro' },
    ];

    const highlightedValues = useMemo(() => {
        const set = new Set<string>();
        entities.forEach((entity, idx) => {
            if (entity.pagina === currentPage && selectedEntityIds.has(idx)) {
                set.add(entity.valor.toLowerCase());
            }
        });
        return set;
    }, [entities, currentPage, selectedEntityIds]);

    const customTermsSet = useMemo(() => new Set(customTerms.map((t) => t.termo.toLowerCase())), [customTerms]);
    const customTermsMap = useMemo(() => {
        const map = new Map<string, string>();
        customTerms.forEach((t) => map.set(t.termo.toLowerCase(), t.tipo));
        return map;
    }, [customTerms]);

    const entityTypeMap = useMemo(() => {
        const map = new Map<string, string>();
        entities.forEach((entity, idx) => {
            if (selectedEntityIds.has(idx)) {
                map.set(entity.valor.toLowerCase(), entity.tipo);
            }
        });
        return map;
    }, [entities, selectedEntityIds]);

    const renderTextContent = useCallback(() => {
        if (!pageText) {
            return <p className="text-on-surface-variant italic">Texto não disponível para esta página.</p>;
        }

        const lines = pageText.split('\n');

        return lines.map((line, lineIdx) => {
            if (line.trim() === '') return <br key={lineIdx} />;

            const words = line.split(/(\s+)/);

            return (
                <div key={lineIdx} className="mb-2">
                    {words.map((word, wordIdx) => {
                        if (/^\s+$/.test(word)) return <span key={wordIdx}>{word}</span>;
                        if (!word) return null;

                        const wordLower = word.toLowerCase().replace(/[.,;:!?()\[\]{}""'']/g, '');

                        let isHighlighted = false;
                        let entityType = '';

                        for (const [entityValue, type] of entityTypeMap) {
                            if (entityValue.includes(wordLower) || wordLower.includes(entityValue)) {
                                isHighlighted = true;
                                entityType = type;
                                break;
                            }
                        }

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

                        let className = 'viewer-word text-[15px] cursor-pointer';
                        if (isHighlighted) {
                            className += ' highlighted';
                            className += ` type-${entityType.toLowerCase()}`;
                        }
                        if (isCustom) {
                            className += ' custom-selected';
                            const customT = customTermsMap.get(wordLower);
                            if (customT) {
                                className += ` type-${customT.toLowerCase()}`;
                                entityType = customT;
                            }
                        }

                        return (
                            <span
                                key={wordIdx}
                                className={className}
                                onClick={(e: MouseEvent) => {
                                    if (wordLower.length > 1) {
                                        setPopover({
                                            word: word.replace(/[.,;:!?()\[\]{}""'']/g, ''),
                                            x: e.clientX,
                                            y: e.clientY
                                        });
                                        setSelectedType(isHighlighted ? entityType : (isCustom ? (customTermsMap.get(wordLower) || 'OUTRO') : 'OUTRO'));
                                        setCustomType('');
                                    }
                                }}
                                title={isHighlighted || isCustom ? `🔒 ${entityType}: será anonimizado` : 'Clique para classificar e anonimizar'}
                            >
                                {word}
                            </span>
                        );
                    })}
                </div>
            );
        });
    }, [pageText, highlightedValues, customTermsSet, entityTypeMap, customTermsMap, onWordClick]);

    return (
        <div className="w-full">
            <div className="document-text-content document-page-margin text-justify">
                {renderTextContent()}

                {currentPage < pages && (
                    <div
                        className="document-page-break cursor-pointer"
                        style={{ opacity: 0.7 }}
                        onClick={() => onPageChange(currentPage + 1)}
                    >
                        <span>Página {currentPage + 1}</span>
                    </div>
                )}
                {currentPage > 1 && (
                    <div
                        className="document-page-break cursor-pointer"
                        style={{ opacity: 0.7 }}
                        onClick={() => onPageChange(currentPage - 1)}
                    >
                        <span>Página {currentPage - 1}</span>
                    </div>
                )}
            </div>

            {popover && (
                <>
                    <div className="viewer-popover-overlay" onClick={() => setPopover(null)} />
                    <div className="viewer-popover" style={{ position: 'fixed', left: Math.min(popover.x, window.innerWidth - 300), top: Math.min(popover.y + 10, window.innerHeight - 320) }}>
                        <div className="viewer-popover-header">
                            <h4 className="m-0 font-bold">Classificar Termo</h4>
                            <button className="viewer-popover-close" onClick={() => setPopover(null)}>×</button>
                        </div>
                        <div className="viewer-popover-content">
                            <span>Termo selecionado: </span>
                            <span className="viewer-popover-word">{popover.word}</span>
                        </div>
                        <div className="classification-chips">
                            {ENTITY_TYPES.map(type => (
                                <button
                                    key={type.value}
                                    className={`classification-chip chip-${type.value.toLowerCase()} ${selectedType === type.value ? 'selected' : ''}`}
                                    onClick={() => setSelectedType(type.value)}
                                >
                                    {type.label}
                                </button>
                            ))}
                            <button
                                className={`classification-chip chip-outro ${selectedType === 'CUSTOM' ? 'selected' : ''}`}
                                onClick={() => setSelectedType('CUSTOM')}
                                style={{ borderStyle: 'dashed' }}
                            >
                                + Novo tipo
                            </button>
                        </div>
                        {selectedType === 'CUSTOM' && (
                            <input className="viewer-popover-input" type="text" placeholder="Nome do tipo personalizado" value={customType} onChange={e => setCustomType(e.target.value)} autoFocus />
                        )}
                        <button 
                            className="btn btn-primary w-full" 
                            style={{ padding: '0.5rem', fontSize: '0.8rem', marginTop: '0.25rem' }}
                            onClick={() => {
                                const finalType = selectedType === 'CUSTOM' ? (customType || 'OUTRO') : selectedType;
                                onWordClick(popover.word, finalType);
                                setPopover(null);
                            }}
                        >
                            <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>check</span>
                            Confirmar Classificação
                        </button>
                    </div>
                </>
            )}
        </div>
    );
}

export default DocumentViewer;
