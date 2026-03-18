import { useCallback } from 'react';
import type { Metadata } from '../types';

interface Props {
    metadata: Metadata;
    onChange: React.Dispatch<React.SetStateAction<Metadata>>;
    onSubmit: () => void;
    isProcessing: boolean;
}

function MetadataForm({ metadata, onChange, onSubmit, isProcessing }: Props) {
    const handleChange = useCallback(
        (field: keyof Metadata) =>
            (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
                onChange((prev) => ({ ...prev, [field]: e.target.value }));
            },
        [onChange]
    );

    return (
        <div className="bg-surface-container-lowest rounded-xl p-8 shadow-[0_12px_40px_rgba(25,28,29,0.06)] mt-6">
            <h3 className="text-lg font-bold font-headline mb-6 flex items-center gap-2 text-on-surface">
                <span className="material-symbols-outlined text-primary">analytics</span>
                Configurações de Processamento
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem 2rem' }}>
                <div className="flex flex-col gap-1.5 space-y-1.5">
                    <label className="text-[11px] font-bold text-on-surface-variant uppercase tracking-widest ml-1" htmlFor="classeProcessual">Classe Processual</label>
                    <div className="relative group flex items-center w-full">
                        <input
                            type="text"
                            id="classeProcessual"
                            className="w-full bg-[#e7e8e9] border border-transparent rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-b-2 focus:border-b-[#003f87] transition-all text-on-surface"
                            placeholder="Ex: Ação Civil Pública"
                            value={metadata.classeProcessual}
                            onChange={handleChange('classeProcessual')}
                        />
                    </div>
                </div>

                <div className="flex flex-col gap-1.5 space-y-1.5">
                    <label className="text-[11px] font-bold text-on-surface-variant uppercase tracking-widest ml-1" htmlFor="vara">Vara</label>
                    <div className="relative group flex items-center w-full">
                        <input
                            type="text"
                            id="vara"
                            className="w-full bg-[#e7e8e9] border border-transparent rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-b-2 focus:border-b-[#003f87] transition-all text-on-surface"
                            placeholder="Ex: 1ª Vara Cível"
                            value={metadata.vara}
                            onChange={handleChange('vara')}
                        />
                    </div>
                </div>

                <div className="flex flex-col gap-1.5 space-y-1.5">
                    <label className="text-[11px] font-bold text-on-surface-variant uppercase tracking-widest ml-1" htmlFor="comarca">Comarca</label>
                    <div className="relative group flex items-center w-full">
                        <input
                            type="text"
                            id="comarca"
                            className="w-full bg-[#e7e8e9] border border-transparent rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-b-2 focus:border-b-[#003f87] transition-all text-on-surface"
                            placeholder="Ex: Belo Horizonte"
                            value={metadata.comarca}
                            onChange={handleChange('comarca')}
                        />
                    </div>
                </div>

                <div className="flex flex-col gap-1.5 space-y-1.5">
                    <label className="text-[11px] font-bold text-on-surface-variant uppercase tracking-widest ml-1" htmlFor="nerMode">Motor de Detecção</label>
                    <div className="relative group flex items-center w-full">
                        <select
                            id="nerMode"
                            className="w-full bg-[#e7e8e9] border border-transparent rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-b-2 focus:border-b-[#003f87] transition-all text-on-surface appearance-none cursor-pointer"
                            value={metadata.nerMode}
                            onChange={handleChange('nerMode')}
                        >
                            <option value="legacy">Padrão (SpaCy + Regex)</option>
                            <option value="standard">Avançado (GLiNER-PII - Lento)</option>
                            <option value="deep">Profundo (GLiNER Deep - Lento)</option>
                            <option value="llm">🤖 LLM (Qwen 3.5 - Mais Lento)</option>
                        </select>
                        <span className="material-symbols-outlined absolute right-3 pointer-events-none text-on-surface-variant">expand_more</span>
                    </div>
                </div>
            </div>

            <div className="mt-10 pt-8 flex items-center justify-between border-t border-[#edeeef]" style={{ marginTop: '2.5rem', paddingTop: '2rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid #edeeef' }}>
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 anonymization-mask rounded-lg flex items-center justify-center" style={{ width: '2.5rem', height: '2.5rem' }}>
                        <span className="material-symbols-outlined text-tertiary">security</span>
                    </div>
                    <div>
                        <p className="text-xs font-bold text-on-surface m-0 mb-1">Sigilo de Dados</p>
                        <p className="text-[10px] text-on-surface-variant m-0" style={{ fontSize: '10px' }}>Em conformidade com a LGPD e Res. 615.</p>
                    </div>
                </div>
                <button 
                    className="btn btn-primary px-10 py-4 text-base" 
                    style={{ padding: '1rem 2.5rem', fontSize: '1rem', boxShadow: '0 8px 24px rgba(0,63,135,0.25)' }}
                    onClick={onSubmit} 
                    disabled={isProcessing}
                >
                    {isProcessing ? 'Processando...' : 'Analisar e Revisar'}
                    {!isProcessing && <span className="material-symbols-outlined ml-2">arrow_forward</span>}
                </button>
            </div>
        </div>
    );
}

export default MetadataForm;
