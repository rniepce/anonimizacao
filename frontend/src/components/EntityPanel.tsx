import { useState, useMemo, useCallback, KeyboardEvent } from 'react';
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
    const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set(['PESSOA', 'Documentos', 'Processo CNJ'])); // Default expanded

    // Group entities by simplified categories for the new UI format
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

        // Remove empty groups
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
        <aside className="w-[320px] bg-[#f3f4f5] border-l border-[#edeeef] h-full flex flex-col p-6 overflow-y-auto shrink-0 relative">
            <h3 className="text-on-surface font-extrabold text-lg mb-4 flex items-center gap-2 m-0">
                <span className="material-symbols-outlined text-primary">visibility</span>
                Entidades
            </h3>

            <div className="flex gap-2 mb-6">
                <button className="flex-1 bg-white border border-[#c2c6d4] text-xs font-bold py-1.5 rounded-md hover:bg-[#e7e8e9] transition-colors cursor-pointer" onClick={onSelectAll}>Selecionar Tudo</button>
                <button className="flex-1 bg-white border border-[#c2c6d4] text-xs font-bold py-1.5 rounded-md hover:bg-[#e7e8e9] transition-colors cursor-pointer" onClick={onDeselectAll}>Limpar</button>
            </div>

            <div className="space-y-4 flex-1 pb-24">
                {Object.entries(grouped).map(([groupName, items]) => {
                    const isExpanded = expandedTypes.has(groupName);
                    
                    return (
                        <div key={groupName} className="group mb-4">
                            <div 
                                className="flex justify-between items-center mb-2 cursor-pointer select-none"
                                onClick={() => toggleType(groupName)}
                                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                            >
                                <span className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">{groupName} ({items.length})</span>
                                <span className={`material-symbols-outlined text-sm text-on-surface-variant transition-transform ${isExpanded ? 'rotate-180' : ''}`}>expand_more</span>
                            </div>
                            
                            {isExpanded && (
                                <div className="space-y-2 flex flex-col gap-2">
                                    {items.map(item => {
                                        const isSelected = selectedIds.has(item._index);
                                        return (
                                            <div 
                                                key={item._index} 
                                                className={`bg-white p-3 rounded-lg border border-[#e1e3e4] hover:shadow-sm transition-all flex flex-col gap-1 ${!isSelected ? 'opacity-60' : ''}`}
                                            >
                                                <div className="flex justify-between items-center" style={{ display: 'flex', justifyContent: 'space-between' }}>
                                                    <span 
                                                        className="text-[10px] font-bold text-primary tracking-tighter uppercase cursor-pointer"
                                                        onClick={() => onEntityClick(item.pagina)}
                                                        title="Ir para página"
                                                    >
                                                        {item.tipo}
                                                    </span>
                                                    <button 
                                                        className={`material-symbols-outlined text-[18px] bg-transparent border-none cursor-pointer hover:scale-110 transition-transform ${isSelected ? 'text-primary' : 'text-error'}`}
                                                        onClick={() => onToggleEntity(item._index)}
                                                        title={isSelected ? "Manter anonimizado" : "Ignorar (não será anonimizado)"}
                                                    >
                                                        {isSelected ? 'check_circle' : 'cancel'}
                                                    </button>
                                                </div>
                                                <span 
                                                    className="text-sm font-medium text-on-surface truncate"
                                                    title={item.valor}
                                                >
                                                    {formatEntityValor(item.valor)}
                                                </span>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    );
                })}

                {/* Custom Terms section mimicking the Accordion Item style */}
                <div className="group mb-4 mt-6">
                    <div className="flex justify-between items-center mb-2">
                        <span className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Termos Adicionais ({customTerms.length})</span>
                    </div>
                    
                    <div className="flex gap-2 mb-3">
                        <input
                            type="text"
                            className="flex-1 bg-white border border-[#c2c6d4] rounded-md px-2 py-1 text-xs outline-none focus:border-primary"
                            placeholder="Adicionar..."
                            value={newTerm}
                            onChange={(e) => setNewTerm(e.target.value)}
                            onKeyDown={handleKeyDown}
                        />
                        <button className="bg-[#003f87] hover:bg-[#0056b3] text-white border-none rounded-md px-2 text-xs font-bold cursor-pointer transition-colors" onClick={handleAddTerm}>+</button>
                    </div>

                    {customTerms.length > 0 && (
                        <div className="space-y-2 flex flex-col gap-2">
                            {customTerms.map((term, idx) => (
                                <div key={idx} className="bg-white p-2 rounded-lg border border-[#e1e3e4] flex justify-between items-center">
                                    <div className="flex flex-col">
                                        <span className="text-[10px] font-bold text-primary uppercase">{term.tipo}</span>
                                        <span className="text-xs font-medium text-on-surface">{formatEntityValor(term.termo)}</span>
                                    </div>
                                    <button 
                                        className="material-symbols-outlined text-[16px] bg-transparent border-none cursor-pointer text-error hover:scale-110 transition-transform"
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

            <div className="mt-8 pt-6 border-t border-[#e1e3e4] mb-4">
                <div className="bg-[#003f87]/5 rounded-lg p-4 bg-opacity-5">
                    <h4 className="text-xs font-bold text-[#003f87] mb-3 flex items-center gap-1 m-0">
                        <span className="material-symbols-outlined text-sm">info</span>
                        RESUMO DA ANONIMIZAÇÃO
                    </h4>
                    <div className="flex justify-between text-xs mb-1" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <span className="text-on-surface-variant">Identificadas:</span>
                        <span className="font-bold">{entities.length + customTerms.length}</span>
                    </div>
                    <div className="flex justify-between text-xs mb-3" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                        <span className="text-on-surface-variant">Aprovadas:</span>
                        <span className="font-bold text-[#003f87]">{selectedIds.size + customTerms.length}</span>
                    </div>
                </div>
            </div>

            <div className="mt-auto absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-[#f3f4f5] via-[#f3f4f5] to-transparent pt-12">
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
                            <span className="material-symbols-outlined text-[20px]">verified_user</span>
                            <span className="font-bold">Anonimizar ({selectedIds.size + customTerms.length})</span>
                        </>
                    )}
                </button>
            </div>
        </aside>
    );
}

export default EntityPanel;
