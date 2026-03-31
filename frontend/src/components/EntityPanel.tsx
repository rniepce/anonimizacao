import { useState, useMemo, useCallback, KeyboardEvent } from 'react';
import { motion } from 'framer-motion';
import type { SensitiveEntity, CustomTerm } from '../types';

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

function getEntityBorderClass(tipo: string): string {
    const t = tipo.toLowerCase();
    if (t === 'cpf' || t === 'cnpj') return 'entity-card-border-cpf';
    if (t === 'pessoa') return 'entity-card-border-pessoa';
    if (t === 'dinheiro') return 'entity-card-border-dinheiro';
    if (t === 'documento' || t === 'rg' || t === 'oab') return 'entity-card-border-documento';
    if (t === 'email') return 'entity-card-border-email';
    if (t === 'organizacao') return 'entity-card-border-organizacao';
    if (t === 'telefone') return 'entity-card-border-telefone';
    if (t === 'endereco' || t === 'cep') return 'entity-card-border-endereco';
    if (t === 'proc_cnj') return 'entity-card-border-proc_cnj';
    return 'entity-card-border-outro';
}

const cardVariants = {
    hidden: { opacity: 0, x: 12 },
    visible: { opacity: 1, x: 0, transition: { duration: 0.2, ease: [0.4, 0, 0.2, 1] as const } },
};

const listVariants = {
    visible: { transition: { staggerChildren: 0.04 } },
};

function EntityPanel({
    entities,
    selectedIds,
    onToggleEntity,
    onSetEntitiesSelection,
    onSelectAll,
    onDeselectAll,
    customTerms,
    onAddCustomTerm,
    onRemoveCustomTerm,
    onConfirmAnonymize,
    isAnonymizing,
    totalPages,
    processingTimeMs,
    onEntityClick,
}: Props) {
    const [newTerm, setNewTerm] = useState('');
    const [newTermType, setNewTermType] = useState('OUTRO');
    const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set(['PESSOA', 'Documentos', 'Processo CNJ']));

    const grouped = useMemo(() => {
        const groups: Record<string, IndexedEntity[]> = {
            'Processo CNJ': [],
            'Pessoas': [],
            'Documentos': [],
            'Contato': [],
            'Outros': []
        };

        entities.forEach((entity, index) => {
            const e = { ...entity, _index: index };
            if (entity.tipo === 'PROC_CNJ') groups['Processo CNJ'].push(e);
            else if (entity.tipo === 'PESSOA') groups['Pessoas'].push(e);
            else if (['CPF', 'CNPJ', 'RG', 'OAB'].includes(entity.tipo)) groups['Documentos'].push(e);
            else if (['EMAIL', 'TELEFONE', 'ENDERECO', 'CEP'].includes(entity.tipo)) groups['Contato'].push(e);
            else groups['Outros'].push(e);
        });

        Object.keys(groups).forEach(key => {
            if (groups[key].length === 0) delete groups[key];
        });

        return groups;
    }, [entities]);

    const toggleType = useCallback((tipo: string) => {
        setExpandedTypes((prev) => {
            const next = new Set(prev);
            if (next.has(tipo)) next.delete(tipo);
            else next.add(tipo);
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
            if (e.key === 'Enter') handleAddTerm();
        },
        [handleAddTerm]
    );

    const formatEntityValor = (valor: string) => {
        if (valor.length > 25) return valor.substring(0, 22) + '...';
        return valor;
    };

    return (
        <aside
            className="entity-panel-aside w-[320px] h-full flex flex-col p-6 overflow-y-auto shrink-0 relative"
            style={{
                background: 'var(--color-surface-container-lowest)',
                borderLeft: '1px solid var(--color-surface-container-high)',
            }}
        >
            <h3 className="font-extrabold text-lg mb-4 flex items-center gap-2 m-0" style={{ color: 'var(--color-on-surface)' }}>
                <span className="material-symbols-outlined text-primary">visibility</span>
                Entidades
            </h3>

            <div className="flex gap-2 mb-6">
                <button
                    className="flex-1 text-xs font-bold py-1.5 rounded-md transition-colors cursor-pointer btn btn-secondary"
                    onClick={onSelectAll}
                >
                    <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>check_circle</span>
                    Selecionar Tudo
                </button>
                <button
                    className="flex-1 text-xs font-bold py-1.5 rounded-md transition-colors cursor-pointer"
                    style={{ background: 'transparent', border: 'none', color: 'var(--color-error)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}
                    onClick={onDeselectAll}
                >
                    <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>cancel</span>
                    Limpar
                </button>
            </div>

            <div className="space-y-4 flex-1 pb-24">
                {Object.entries(grouped).map(([groupName, items]) => {
                    const isExpanded = expandedTypes.has(groupName);

                    return (
                        <div key={groupName} className="group mb-4">
                            <div
                                className="flex justify-between items-center mb-2 cursor-pointer select-none"
                                onClick={() => toggleType(groupName)}
                            >
                                <span
                                    className="text-xs font-bold uppercase tracking-wider entity-group-header"
                                    style={{ color: 'var(--color-on-surface-variant)' }}
                                >
                                    {groupName} ({items.length})
                                </span>
                                <span
                                    className="material-symbols-outlined text-sm transition-transform"
                                    style={{
                                        color: 'var(--color-on-surface-variant)',
                                        fontSize: '18px',
                                        transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                                        transition: 'transform 0.2s ease',
                                    }}
                                >
                                    expand_more
                                </span>
                            </div>

                            {isExpanded && (
                                <motion.div
                                    className="flex flex-col gap-2"
                                    initial="hidden"
                                    animate="visible"
                                    variants={listVariants}
                                >
                                    {items.map(item => {
                                        const isSelected = selectedIds.has(item._index);
                                        return (
                                            <motion.div
                                                key={item._index}
                                                variants={cardVariants}
                                                className={`p-3 rounded-lg border flex flex-col gap-1 ${getEntityBorderClass(item.tipo)} ${!isSelected ? 'opacity-60' : ''}`}
                                                style={{
                                                    background: 'var(--color-surface-container-lowest)',
                                                    borderTopColor: 'var(--color-surface-container-high)',
                                                    borderRightColor: 'var(--color-surface-container-high)',
                                                    borderBottomColor: 'var(--color-surface-container-high)',
                                                    transition: 'opacity 0.15s ease, box-shadow 0.15s ease',
                                                }}
                                            >
                                                <div className="flex justify-between items-center">
                                                    <span
                                                        className="text-[10px] font-bold tracking-tighter uppercase cursor-pointer"
                                                        style={{ color: 'var(--color-primary)' }}
                                                        onClick={() => onEntityClick(item.pagina)}
                                                        title="Ir para página"
                                                    >
                                                        {item.tipo}
                                                    </span>
                                                    <button
                                                        className="material-symbols-outlined bg-transparent border-none cursor-pointer transition-transform"
                                                        style={{
                                                            fontSize: '18px',
                                                            color: isSelected ? 'var(--color-primary)' : 'var(--color-error)',
                                                        }}
                                                        onMouseEnter={e => (e.currentTarget.style.transform = 'scale(1.15)')}
                                                        onMouseLeave={e => (e.currentTarget.style.transform = 'scale(1)')}
                                                        onClick={() => onToggleEntity(item._index)}
                                                        title={isSelected ? "Manter anonimizado" : "Ignorar (não será anonimizado)"}
                                                    >
                                                        {isSelected ? 'check_circle' : 'cancel'}
                                                    </button>
                                                </div>
                                                <span
                                                    className="text-sm font-medium truncate"
                                                    style={{ color: 'var(--color-on-surface)' }}
                                                    title={item.valor}
                                                >
                                                    {formatEntityValor(item.valor)}
                                                </span>
                                            </motion.div>
                                        );
                                    })}
                                </motion.div>
                            )}
                        </div>
                    );
                })}

                {/* Custom Terms */}
                <div className="group mb-4 mt-6">
                    <div className="flex justify-between items-center mb-2">
                        <span
                            className="text-xs font-bold uppercase tracking-wider entity-group-header"
                            style={{ color: 'var(--color-on-surface-variant)' }}
                        >
                            Termos Adicionais ({customTerms.length})
                        </span>
                    </div>

                    <div className="flex gap-2 mb-3">
                        <input
                            type="text"
                            className="flex-1 rounded-md px-2 py-1 text-xs outline-none"
                            style={{
                                background: 'var(--color-surface-container-lowest)',
                                border: '1.5px solid var(--color-outline-variant)',
                                color: 'var(--color-on-surface)',
                                fontFamily: 'var(--font-body)',
                            }}
                            placeholder="Adicionar..."
                            value={newTerm}
                            onChange={(e) => setNewTerm(e.target.value)}
                            onKeyDown={handleKeyDown}
                        />
                        <button
                            className="text-white border-none rounded-md px-3 text-xs font-bold cursor-pointer transition-colors"
                            style={{ background: 'var(--color-primary)' }}
                            onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-primary-container)')}
                            onMouseLeave={e => (e.currentTarget.style.background = 'var(--color-primary)')}
                            onClick={handleAddTerm}
                        >
                            +
                        </button>
                    </div>

                    {customTerms.length > 0 && (
                        <div className="space-y-2 flex flex-col gap-2">
                            {customTerms.map((term, idx) => (
                                <div
                                    key={idx}
                                    className="p-2 rounded-lg flex justify-between items-center"
                                    style={{
                                        background: 'var(--color-surface-container-lowest)',
                                        border: '1px solid var(--color-surface-container-high)',
                                    }}
                                >
                                    <div className="flex flex-col">
                                        <span className="text-[10px] font-bold uppercase" style={{ color: 'var(--color-primary)' }}>{term.tipo}</span>
                                        <span className="text-xs font-medium" style={{ color: 'var(--color-on-surface)' }}>{formatEntityValor(term.termo)}</span>
                                    </div>
                                    <button
                                        className="material-symbols-outlined bg-transparent border-none cursor-pointer transition-transform"
                                        style={{ fontSize: '16px', color: 'var(--color-error)' }}
                                        onMouseEnter={e => (e.currentTarget.style.transform = 'scale(1.15)')}
                                        onMouseLeave={e => (e.currentTarget.style.transform = 'scale(1)')}
                                        onClick={() => onRemoveCustomTerm(idx)}
                                        title="Remover termo"
                                    >
                                        delete
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Summary Box */}
            <div className="mt-8 pt-6 mb-4" style={{ borderTop: '1px solid var(--color-surface-container-high)' }}>
                <div className="anonymization-summary">
                    <h4 className="text-xs font-bold mb-3 flex items-center gap-1 m-0" style={{ color: 'var(--color-accent)' }}>
                        <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>info</span>
                        RESUMO DA ANONIMIZAÇÃO
                    </h4>
                    <div className="flex justify-between text-xs mb-1">
                        <span style={{ color: 'var(--color-on-surface-variant)' }}>Identificadas:</span>
                        <span className="font-bold anonymization-summary-count">{entities.length + customTerms.length}</span>
                    </div>
                    <div className="flex justify-between text-xs mb-3">
                        <span style={{ color: 'var(--color-on-surface-variant)' }}>Aprovadas:</span>
                        <span className="font-bold anonymization-summary-count">{selectedIds.size + customTerms.length}</span>
                    </div>
                </div>
            </div>

            {/* CTA */}
            <div
                className="mt-auto absolute bottom-0 left-0 right-0 p-6 pt-12"
                style={{
                    background: 'linear-gradient(to top, var(--color-surface-container-lowest) 60%, transparent)',
                }}
            >
                <button
                    className="w-full btn btn-primary py-3 rounded-xl shadow-lg flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={onConfirmAnonymize}
                    disabled={isAnonymizing || (selectedIds.size === 0 && customTerms.length === 0)}
                >
                    {isAnonymizing ? (
                        <>
                            <span className="spinner-small" style={{ borderTopColor: 'currentColor' }} /> Processando...
                        </>
                    ) : (
                        <>
                            <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>verified_user</span>
                            <span className="font-bold">Anonimizar ({selectedIds.size + customTerms.length})</span>
                        </>
                    )}
                </button>
            </div>
        </aside>
    );
}

export default EntityPanel;
