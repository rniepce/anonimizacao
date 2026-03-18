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
                                    if (!isHighlighted && !isCustom && wordLower.length > 1) {
                                        setPopover({
                                            word: word.replace(/[.,;:!?()\[\]{}""'']/g, ''),
                                            x: e.clientX,
                                            y: e.clientY
                                        });
                                        setSelectedType('OUTRO');
                                        setCustomType('');
                                    }
                                }}
                                title={isHighlighted || isCustom ? `🔒 ${entityType}: será anonimizado` : 'Clique para adicionar como termo de anonimização'}
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
            <div className="space-y-4 text-on-surface leading-relaxed font-body text-justify">
                {renderTextContent()}
                
                {currentPage < pages && (
                    <div 
                        className="py-12 mt-8 text-center text-on-surface-variant font-medium text-sm italic opacity-60 cursor-pointer hover:opacity-100 transition-opacity"
                        onClick={() => onPageChange(currentPage + 1)}
                    >
                        — Continuação do documento na Página {currentPage + 1} —
                    </div>
                )}
                {currentPage > 1 && (
                    <div 
                        className="py-4 text-center text-on-surface-variant font-medium text-sm italic opacity-60 cursor-pointer hover:opacity-100 transition-opacity"
                        onClick={() => onPageChange(currentPage - 1)}
                    >
                        — Voltar para a Página {currentPage - 1} —
                    </div>
                )}
            </div>

            {popover && (
                <div className="viewer-popover" style={{ position: 'fixed', left: Math.min(popover.x, window.innerWidth - 260), top: popover.y + 10 }}>
                    <div className="viewer-popover-header">
                        <h4 className="m-0 font-bold">Classificar</h4>
                        <button className="viewer-popover-close" onClick={() => setPopover(null)}>×</button>
                    </div>
                    <div className="viewer-popover-content">
                        <span>Termo: </span>
                        <span className="viewer-popover-word">{popover.word}</span>
                    </div>
                    <select className="viewer-popover-select" value={selectedType} onChange={e => setSelectedType(e.target.value)}>
                        <option value="CPF">CPF</option>
                        <option value="CNPJ">CNPJ</option>
                        <option value="PESSOA">Pessoa</option>
                        <option value="ORGANIZACAO">Organização</option>
                        <option value="DOCUMENTO">Documento</option>
                        <option value="DINHEIRO">Dinheiro</option>
                        <option value="OUTRO">Outro</option>
                        <option value="CUSTOM">Criar novo...</option>
                    </select>
                    {selectedType === 'CUSTOM' && (
                        <input className="viewer-popover-input" type="text" placeholder="Nome do tipo" value={customType} onChange={e => setCustomType(e.target.value)} autoFocus />
                    )}
                    <button 
                        className="btn btn-primary w-full mt-2" 
                        style={{ padding: '0.4rem', fontSize: '0.8rem' }}
                        onClick={() => {
                            const finalType = selectedType === 'CUSTOM' ? (customType || 'OUTRO') : selectedType;
                            onWordClick(popover.word, finalType);
                            setPopover(null);
                        }}
                    >
                        Confirmar
                    </button>
                </div>
            )}
        </div>
    );
}

export default DocumentViewer;
