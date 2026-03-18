import { useState, useMemo, useCallback, KeyboardEvent } from 'react';
import type { SensitiveEntity, CustomTerm } from '../types';

// ─── Constants ───────────────────────────────────────────────

const TYPE_LABELS: Record<string, string> = {
    CPF: '🆔 CPF',
    CNPJ: '🏢 CNPJ',
    PROC_CNJ: '⚖️ Processo CNJ',
    OAB: '🔢 OAB',
    EMAIL: '📧 E-mail',
    TELEFONE: '📞 Telefone',
    CEP: '📍 CEP',
    RG: '🪪 RG',
    PESSOA: '👤 Pessoa',
    ENDERECO: '📍 Endereço',
    ORGANIZACAO: '🏛️ Organização',
    DATA_NASCIMENTO: '📅 Nascimento',
    CTPS: '📋 CTPS',
    PIS_PASEP: '📋 PIS/PASEP',
    TITULO_ELEITOR: '🗳️ Título Eleitor',
    CNH: '🚗 CNH',
    CONTA_BANCARIA: '🏦 Conta',
    AGENCIA: '🏦 Agência',
    ROSTO: '😶 Rosto',
    ASSINATURA: '✍️ Assinatura',
    OUTRO: '❓ Outro',
};

// ─── Types ───────────────────────────────────────────────────

interface IndexedEntity extends SensitiveEntity {
    _index: number;
}

interface Props {
    entities: SensitiveEntity[];
    selectedIds: Set<number>;
    onToggleEntity: (index: number) => void;
    onSetEntitiesSelection: (indices: number[], selected: boolean) => void;
    onSelectAll: () => void;
    onDeselectAll: () => void;
    customTerms: CustomTerm[];
    onAddCustomTerm: (term: string, tipo?: string) => void;
    onRemoveCustomTerm: (index: number) => void;
    onConfirmAnonymize: () => void;
    isAnonymizing: boolean;
    totalPages: number;
    processingTimeMs: number;
    onEntityClick: (page: number) => void;
}

// ─── Component ───────────────────────────────────────────────

function EntityPanel({
    entities,
    selectedIds,
    onToggleEntity,
    onSelectAll,
    onDeselectAll,
    customTerms,
    onAddCustomTerm,
    onRemoveCustomTerm,
    onConfirmAnonymize,
    isAnonymizing,
    totalPages,
    processingTimeMs,
    onSetEntitiesSelection,
    onEntityClick,
}: Props) {
    const [filter, setFilter] = useState('');
    const [newTerm, setNewTerm] = useState('');
    const [newTermType, setNewTermType] = useState('OUTRO');
    const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set());

    // Group entities by type
    const grouped = useMemo(() => {
        const groups: Record<string, IndexedEntity[]> = {};
        entities.forEach((entity, index) => {
            const tipo = entity.tipo;
            if (!groups[tipo]) groups[tipo] = [];
            groups[tipo].push({ ...entity, _index: index });
        });
        return groups;
    }, [entities]);

    // Filtered entities
    const filteredGrouped = useMemo(() => {
        if (!filter.trim()) return grouped;
        const q = filter.toLowerCase();
        const result: Record<string, IndexedEntity[]> = {};
        for (const [tipo, items] of Object.entries(grouped)) {
            const filtered = items.filter(
                (item) =>
                    item.valor.toLowerCase().includes(q) ||
                    tipo.toLowerCase().includes(q)
            );
            if (filtered.length > 0) result[tipo] = filtered;
        }
        return result;
    }, [grouped, filter]);

    const selectedCount = selectedIds.size;
    const totalCount = entities.length;

    const toggleType = useCallback((tipo: string) => {
        setExpandedTypes((prev) => {
            const next = new Set(prev);
            if (next.has(tipo)) {
                next.delete(tipo);
            } else {
                next.add(tipo);
            }
            return next;
        });
    }, []);

    const handleAddTerm = useCallback(() => {
        const trimmed = newTerm.trim();
        if (trimmed && !customTerms.some(t => t.termo.toLowerCase() === trimmed.toLowerCase())) {
            onAddCustomTerm(trimmed, newTermType);
            setNewTerm('');
        }
    }, [newTerm, newTermType, customTerms, onAddCustomTerm]);

    const handleKeyDown = useCallback(
        (e: KeyboardEvent) => {
            if (e.key === 'Enter') {
                handleAddTerm();
            }
        },
        [handleAddTerm]
    );

    return (
        <div className="entity-panel">
            {/* Header with stats */}
            <div className="entity-panel-header">
                <h3>🎯 Entidades Identificadas</h3>
                <div className="entity-stats">
                    <span className="entity-stat">
                        <strong>{selectedCount}</strong> / {totalCount} selecionadas
                    </span>
                    {totalPages > 0 && (
                        <span className="entity-stat-secondary">
                            📄 {totalPages} pág. • ⏱️ {processingTimeMs}ms
                        </span>
                    )}
                </div>
            </div>

            {/* Controls */}
            <div className="entity-controls">
                <input
                    type="text"
                    className="entity-filter"
                    placeholder="🔍 Filtrar entidades..."
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                />
                <div className="entity-bulk-actions">
                    <button
                        className="entity-bulk-btn"
                        onClick={onSelectAll}
                        title="Selecionar todas"
                    >
                        ☑ Todas
                    </button>
                    <button
                        className="entity-bulk-btn"
                        onClick={onDeselectAll}
                        title="Desselecionar todas"
                    >
                        ☐ Nenhuma
                    </button>
                </div>
            </div>

            {/* Entity list by type */}
            <div className="entity-list">
                {Object.entries(filteredGrouped).map(([tipo, items]) => {
                    const isExpanded = expandedTypes.has(tipo) || filter.trim().length > 0;
                    const typeSelectedCount = items.filter((i) => selectedIds.has(i._index)).length;
                    const typeLabel = TYPE_LABELS[tipo] || `❓ ${tipo}`;

                    return (
                        <div key={tipo} className="entity-type-group">
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                <button
                                    className="entity-type-header"
                                    onClick={() => toggleType(tipo)}
                                    title={`Expanda para ver os itens de ${typeLabel}`}
                                    style={{ flex: 1 }}
                                >
                                    <span className="entity-type-name">
                                        {typeLabel}
                                        <span className="entity-type-count">
                                            {typeSelectedCount}/{items.length}
                                        </span>
                                    </span>
                                    <span className={`entity-chevron ${isExpanded ? 'expanded' : ''}`}>
                                        ▸
                                    </span>
                                </button>
                                <div style={{ display: 'flex', gap: '4px', paddingRight: '8px' }}>
                                    <button 
                                        className="btn-remove" 
                                        style={{ minWidth: '24px', minHeight: '24px', padding: '0 4px', fontSize: '0.75rem', color: 'var(--color-success)' }}
                                        onClick={() => onSetEntitiesSelection(items.map((i) => i._index), true)}
                                        title="Selecionar todos deste tipo"
                                    >
                                        ✓
                                    </button>
                                    <button 
                                        className="btn-remove" 
                                        style={{ minWidth: '24px', minHeight: '24px', padding: '0 4px', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}
                                        onClick={() => onSetEntitiesSelection(items.map((i) => i._index), false)}
                                        title="Desmarcar todos deste tipo"
                                    >
                                        ✕
                                    </button>
                                </div>
                            </div>

                            {isExpanded && (
                                <div className="entity-type-items">
                                    {items.map((item) => {
                                        const isSelected = selectedIds.has(item._index);
                                        return (
                                            <div
                                                key={item._index}
                                                className={`entity-item ${isSelected ? 'selected' : 'deselected'}`}
                                            >
                                                <input
                                                    type="checkbox"
                                                    checked={isSelected}
                                                    onChange={() => onToggleEntity(item._index)}
                                                    className="entity-checkbox"
                                                    title="Incluir/excluir da anonimização"
                                                />
                                                <span 
                                                    className="entity-valor" 
                                                    title={`Clique para ir à página ${item.pagina}`}
                                                    onClick={() => onEntityClick(item.pagina)}
                                                    style={{ cursor: 'pointer', flex: 1 }}
                                                >
                                                    {item.valor}
                                                </span>
                                                <span 
                                                    className="entity-page"
                                                    title={`Clique para ir à página ${item.pagina}`}
                                                    onClick={() => onEntityClick(item.pagina)}
                                                    style={{ cursor: 'pointer', paddingLeft: '8px' }}
                                                >
                                                    p.{item.pagina}
                                                </span>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    );
                })}

                {Object.keys(filteredGrouped).length === 0 && (
                    <div className="entity-empty">
                        {filter ? 'Nenhuma entidade encontrada para esse filtro.' : 'Nenhuma entidade identificada.'}
                    </div>
                )}
            </div>

            {/* Custom terms section */}
            <div className="custom-terms-section">
                <h4>➕ Termos Customizados</h4>
                <p className="custom-terms-desc">
                    Adicione palavras ou expressões que deseja anonimizar além das detectadas automaticamente.
                </p>
                <div className="custom-term-input-row">
                    <input
                        type="text"
                        className="custom-term-input"
                        placeholder="Digite um termo..."
                        value={newTerm}
                        onChange={(e) => setNewTerm(e.target.value)}
                        onKeyDown={handleKeyDown}
                    />
                    <select 
                        className="custom-term-input" 
                        style={{ width: '110px', flex: 'none' }}
                        value={newTermType}
                        onChange={e => setNewTermType(e.target.value)}
                    >
                        <option value="CPF">CPF</option>
                        <option value="CNPJ">CNPJ</option>
                        <option value="PESSOA">Pessoa</option>
                        <option value="ORGANIZACAO">Organização</option>
                        <option value="DOCUMENTO">Documento</option>
                        <option value="DINHEIRO">Dinheiro</option>
                        <option value="OUTRO">Outro</option>
                    </select>
                    <button
                        className="custom-term-add-btn"
                        onClick={handleAddTerm}
                        disabled={!newTerm.trim()}
                    >
                        +
                    </button>
                </div>

                {customTerms.length > 0 && (
                    <div className="custom-terms-list">
                        {customTerms.map((term, idx) => (
                            <span key={idx} className="custom-term-tag">
                                {term.termo} <small style={{opacity: 0.7, marginLeft: '4px'}}>({term.tipo})</small>
                                <button
                                    className="custom-term-remove"
                                    onClick={() => onRemoveCustomTerm(idx)}
                                    title="Remover"
                                >
                                    ×
                                </button>
                            </span>
                        ))}
                    </div>
                )}
            </div>

            {/* Confirm button */}
            <div className="entity-panel-footer">
                <button
                    className="btn btn-primary btn-confirm-anonymize"
                    onClick={onConfirmAnonymize}
                    disabled={isAnonymizing || (selectedCount === 0 && customTerms.length === 0)}
                >
                    {isAnonymizing ? (
                        <>
                            <span className="spinner-small" /> Anonimizando...
                        </>
                    ) : (
                        <>
                            <span className="btn-icon-text">🔒</span>
                            Confirmar e Anonimizar ({selectedCount + customTerms.length} itens)
                        </>
                    )}
                </button>
            </div>
        </div>
    );
}

export default EntityPanel;
