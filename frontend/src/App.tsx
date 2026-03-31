import { useState, useCallback, useEffect } from 'react';
import type { Metadata, PreviewData, AnonymizationMeta, ProgressInfo, CustomTerm } from './types';
import ErrorBoundary from './components/ErrorBoundary';
import Header from './components/Header';
import UploadSection from './components/UploadSection';
import MetadataForm from './components/MetadataForm';
import ProgressSection from './components/ProgressSection';
import DocumentViewer from './components/DocumentViewer';
import EntityPanel from './components/EntityPanel';
import DocumentSidebar from './components/DocumentSidebar';
import Footer from './components/Footer';
import { analyzePreview, anonymizeSelective } from './services/api';
import { Toaster, toast } from 'react-hot-toast';
import { motion, AnimatePresence } from 'framer-motion';

// ─── View type ───────────────────────────────────────────────

type AppView = 'upload' | 'progress' | 'review' | 'anonymizing' | 'download';

// ─── Component ───────────────────────────────────────────────

function App() {
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [metadata, setMetadata] = useState<Metadata>({
        classeProcessual: '',
        vara: '',
        comarca: '',
        nerMode: 'legacy',
    });

    // UI state
    const [view, setView] = useState<AppView>('upload');
    const [progressInfo, setProgressInfo] = useState<ProgressInfo>({ title: '', status: '', progress: 0 });

    // Review state
    const [previewData, setPreviewData] = useState<PreviewData | null>(null);
    const [selectedEntityIds, setSelectedEntityIds] = useState<Set<number>>(new Set());
    const [customTerms, setCustomTerms] = useState<CustomTerm[]>([]);
    const [viewerPage, setViewerPage] = useState(1);

    // Download state
    const [anonymizedBlob, setAnonymizedBlob] = useState<Blob | null>(null);
    const [anonymizationMeta, setAnonymizationMeta] = useState<AnonymizationMeta | null>(null);
    const [isAnonymizing, setIsAnonymizing] = useState(false);

    const handleFileSelect = useCallback((file: File) => {
        const validExts = ['.pdf', '.docx'];
        const ext = '.' + file.name.split('.').pop()?.toLowerCase();
        if (!validExts.includes(ext)) {
            toast.error('Por favor, selecione um arquivo PDF ou DOCX.');
            return;
        }
        setSelectedFile(file);
        setPreviewData(null);
        setAnonymizedBlob(null);
        setAnonymizationMeta(null);
        setCustomTerms([]);
    }, []);

    const handleRemoveFile = useCallback(() => {
        setSelectedFile(null);
        setPreviewData(null);
        setAnonymizedBlob(null);
        setAnonymizationMeta(null);
        setCustomTerms([]);
        setView('upload');
    }, []);

    const simulateProgress = useCallback(() => {
        const stages = [
            { progress: 10, status: 'Iniciando processamento...' },
            { progress: 25, status: 'Extraindo texto do documento...' },
            { progress: 40, status: 'Identificando padrões com Regex...' },
            { progress: 55, status: 'Analisando entidades com NLP...' },
            { progress: 70, status: 'Carregando modelos de IA...' },
            { progress: 80, status: 'Gerando preview com destaques...' },
            { progress: 90, status: 'Finalizando análise...' },
        ];

        let i = 0;
        const interval = setInterval(() => {
            if (i < stages.length) {
                const stage = stages[i];
                i++;
                setProgressInfo({
                    title: 'Analisando...',
                    progress: stage.progress,
                    status: stage.status,
                });
            } else {
                setProgressInfo((prev) => ({
                    title: prev?.title || 'Processando...',
                    progress: (prev?.progress || 90) === 95 ? 90 : 95,
                    status: 'Aguardando servidor... Processamento em andamento',
                }));
            }
        }, 1500);

        return () => clearInterval(interval);
    }, []);

    // Step 1: Analyze and show review
    const handleAnalyze = useCallback(async () => {
        if (!selectedFile) return;

        setView('progress');
        setProgressInfo({
            title: 'Analisando documento...',
            status: 'Extraindo texto e identificando dados sensíveis',
            progress: 0,
        });

        const stopSim = simulateProgress();

        try {
            const data = await analyzePreview(selectedFile, metadata);
            stopSim();

            setPreviewData(data);
            // Select all entities by default
            const allIds = new Set(data.dados_sensiveis.map((_: unknown, i: number) => i));
            setSelectedEntityIds(allIds);
            setCustomTerms([]);
            setAnonymizedBlob(null);
            setAnonymizationMeta(null);
            setView('review');
        } catch (error) {
            stopSim();
            console.error('Analyze error:', error);
            setView('upload');
            toast.error('Erro ao analisar documento: ' + ((error as Error)?.message || 'Erro desconhecido'));
        }
    }, [selectedFile, metadata, simulateProgress]);

    // Step 2: Confirm and anonymize
    const handleConfirmAnonymize = useCallback(async () => {
        if (!previewData) return;

        setIsAnonymizing(true);

        try {
            // Build the confirmed entities list
            const confirmedEntities = previewData.dados_sensiveis
                .filter((_: unknown, i: number) => selectedEntityIds.has(i))
                .map((entity) => ({
                    tipo: entity.tipo,
                    valor: entity.valor,
                    pagina: entity.pagina,
                    posicao: entity.posicao,
                }));

            const { blob, meta } = await anonymizeSelective(
                previewData.job_id,
                confirmedEntities,
                customTerms
            );

            setAnonymizedBlob(blob);
            setAnonymizationMeta(meta);
            setView('download');
        } catch (error) {
            console.error('Anonymize error:', error);
            toast.error('Erro ao anonimizar documento: ' + ((error as Error)?.message || 'Erro desconhecido'));
        } finally {
            setIsAnonymizing(false);
        }
    }, [previewData, selectedEntityIds, customTerms]);

    // Toggle entity selection
    const handleToggleEntity = useCallback((index: number) => {
        setSelectedEntityIds((prev) => {
            const next = new Set(prev);
            if (next.has(index)) {
                next.delete(index);
            } else {
                next.add(index);
            }
            return next;
        });
    }, []);

    const handleSetEntitiesSelection = useCallback((indices: number[], selected: boolean) => {
        setSelectedEntityIds((prev) => {
            const next = new Set(prev);
            indices.forEach(idx => {
                if (selected) next.add(idx);
                else next.delete(idx);
            });
            return next;
        });
    }, []);

    const handleSelectAll = useCallback(() => {
        if (!previewData) return;
        const allIds = new Set(previewData.dados_sensiveis.map((_: unknown, i: number) => i));
        setSelectedEntityIds(allIds);
    }, [previewData]);

    const handleDeselectAll = useCallback(() => {
        setSelectedEntityIds(new Set());
    }, []);

    const handleAddCustomTerm = useCallback((term: string, tipo: string = 'OUTRO') => {
        setCustomTerms((prev) => {
            if (prev.some(t => t.termo.toLowerCase() === term.toLowerCase())) return prev;
            return [...prev, { termo: term, tipo }];
        });
    }, []);

    const handleRemoveCustomTerm = useCallback((idx: number) => {
        setCustomTerms((prev) => prev.filter((_: CustomTerm, i: number) => i !== idx));
    }, []);

    const handleDownload = useCallback(() => {
        if (!anonymizedBlob || !selectedFile) {
            toast.error('Nenhum arquivo disponível para download');
            return;
        }

        const url = URL.createObjectURL(anonymizedBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = selectedFile.name.replace(/\.[^/.]+$/, '') + '_anonimizado.pdf';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, [anonymizedBlob, selectedFile]);

    const handleBackToReview = useCallback(() => {
        setAnonymizedBlob(null);
        setAnonymizationMeta(null);
        setView('review');
    }, []);

    const handleNewFile = useCallback(() => {
        setSelectedFile(null);
        setPreviewData(null);
        setAnonymizedBlob(null);
        setAnonymizationMeta(null);
        setCustomTerms([]);
        setSelectedEntityIds(new Set());
        setView('upload');
    }, []);

    const isProcessing = view === 'progress';

    // Mobile sidebar
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);

    // Dark mode
    const [isDarkMode, setIsDarkMode] = useState(() =>
        window.matchMedia('(prefers-color-scheme: dark)').matches
    );
    useEffect(() => {
        document.documentElement.setAttribute('data-theme', isDarkMode ? 'dark' : 'light');
    }, [isDarkMode]);
    const toggleDarkMode = useCallback(() => setIsDarkMode(d => !d), []);

    return (
        <div className="app-container">
            <Header isDarkMode={isDarkMode} onToggleDark={toggleDarkMode} />

            <div className="main-content flex">
                {/* Left Sidebar: Generic Nav OR Document Pages if reviewing */}
                {previewData ? (
                    <DocumentSidebar
                        totalPages={previewData.total_paginas}
                        currentPage={viewerPage}
                        onPageChange={setViewerPage}
                    />
                ) : (
                    <aside className={`main-nav-sidebar${isSidebarOpen ? ' open' : ''}`}>
                        {/* Mobile close button */}
                        <button
                            className="material-symbols-outlined bg-transparent border-none cursor-pointer mb-4"
                            style={{ color: 'var(--color-sidebar-text-dim)', fontSize: '22px', display: 'none', alignSelf: 'flex-end' }}
                            onClick={() => setIsSidebarOpen(false)}
                        >
                            close
                        </button>
                        <div className="nav-brand">
                            <span className="brand-title">
                                <span className="brand-tjmg">TJMG</span>{' '}
                                <span className="brand-anon">Anon</span>
                            </span>
                            <span className="brand-subtitle">Anonimizador</span>
                        </div>
                        <button className="btn btn-primary w-full nav-new-btn" onClick={handleNewFile}>
                            <span className="material-symbols-outlined">add</span> Novo Arquivo
                        </button>
                        <nav className="nav-links">
                            <a href="#" className="nav-link active"><span className="material-symbols-outlined">description</span> Documentos</a>
                            <a href="#" className="nav-link"><span className="material-symbols-outlined">auto_stories</span> Páginas</a>
                            <a href="#" className="nav-link"><span className="material-symbols-outlined">fingerprint</span> Entidades</a>
                            <a href="#" className="nav-link"><span className="material-symbols-outlined">history</span> Histórico</a>
                        </nav>
                        <div className="mt-auto pt-4">
                            <a href="#" className="nav-link"><span className="material-symbols-outlined">contact_support</span> Suporte</a>
                        </div>
                    </aside>
                )}

                {/* Center Column: Upload, Progress, or Viewer */}
                <section className="center-workspace">
                    <AnimatePresence mode="wait">
                        {!previewData && !isProcessing && (
                            <motion.div
                                key="upload"
                                className="upload-view-container w-full max-w-4xl"
                                initial={{ opacity: 0, y: 16 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -8 }}
                                transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
                            >
                                <header className="upload-header mb-10 text-left">
                                    <h2 className="text-3xl font-extrabold font-headline tracking-tight text-on-surface mb-2">Upload de Documento</h2>
                                    <p className="text-on-surface-variant font-medium">Prepare seus arquivos para o processo de anonimização automatizada.</p>
                                </header>

                                <UploadSection
                                    onFileSelect={handleFileSelect}
                                    selectedFile={selectedFile}
                                    onRemoveFile={handleRemoveFile}
                                />

                                {selectedFile && (
                                    <div className="mt-6">
                                        <MetadataForm
                                            metadata={metadata}
                                            onChange={setMetadata}
                                            onSubmit={handleAnalyze}
                                            isProcessing={isProcessing}
                                        />
                                    </div>
                                )}
                            </motion.div>
                        )}

                        {isProcessing && (
                            <motion.div
                                key="progress"
                                className="progress-view-container w-full max-w-4xl"
                                initial={{ opacity: 0, scale: 0.97 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.97 }}
                                transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
                            >
                                <ProgressSection info={progressInfo} />
                            </motion.div>
                        )}

                        {previewData && (
                            <motion.div
                                key="review"
                                className="viewer-container w-full max-w-4xl rounded-lg p-16 relative document-paper"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
                            >
                                {/* Document Header */}
                                <div className="mb-12 pb-8" style={{ borderBottom: '1px solid var(--color-outline-variant)' }}>
                                    <div className="flex justify-between items-start">
                                        <div>
                                            <span className="text-xs font-bold font-label uppercase tracking-widest text-primary mb-2 block">Processo Digital</span>
                                            <h2 className="text-2xl font-extrabold font-headline tracking-tight text-on-surface">{selectedFile?.name || 'Documento Anonimizado'}</h2>
                                        </div>
                                        <div className="review-pending-badge">
                                            REVISÃO PENDENTE
                                        </div>
                                    </div>
                                </div>

                                <DocumentViewer
                                    textByPage={previewData.texto_por_pagina}
                                    totalPages={previewData.total_paginas}
                                    currentPage={viewerPage}
                                    onPageChange={setViewerPage}
                                    entities={previewData.dados_sensiveis}
                                    selectedEntityIds={selectedEntityIds}
                                    customTerms={customTerms}
                                    onWordClick={handleAddCustomTerm}
                                />

                                {/* Action FAB */}
                                <motion.button
                                    initial={{ scale: 0, opacity: 0 }}
                                    animate={{ scale: 1, opacity: 1 }}
                                    whileHover={{ scale: 1.05, boxShadow: '0 16px 48px rgba(0,53,128,0.4)' }}
                                    whileTap={{ scale: 0.95 }}
                                    transition={{ type: 'spring', stiffness: 300, damping: 20 }}
                                    className="fixed bottom-10 right-[350px] text-white p-4 rounded-full flex items-center gap-3"
                                    style={{ background: 'linear-gradient(135deg, var(--color-primary), var(--color-primary-container))', boxShadow: 'var(--shadow-floating)' }}
                                    onClick={handleDownload}
                                    disabled={isAnonymizing}
                                >
                                    <span className="material-symbols-outlined">verified_user</span>
                                    <span className="font-bold text-sm pr-2">Aprovar Tudo</span>
                                </motion.button>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </section>

                {/* Right Sidebar: Entity Panel (Only when reviewing) */}
                <AnimatePresence>
                    {previewData && (
                        <motion.div
                            initial={{ x: 320, opacity: 0 }}
                            animate={{ x: 0, opacity: 1 }}
                            exit={{ x: 320, opacity: 0 }}
                            transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
                        >
                            <EntityPanel
                                entities={previewData.dados_sensiveis}
                                selectedIds={selectedEntityIds}
                                onToggleEntity={handleToggleEntity}
                                onSelectAll={handleSelectAll}
                                onDeselectAll={handleDeselectAll}
                                customTerms={customTerms}
                                onAddCustomTerm={handleAddCustomTerm}
                                onRemoveCustomTerm={handleRemoveCustomTerm}
                                onConfirmAnonymize={handleConfirmAnonymize}
                                isAnonymizing={isAnonymizing}
                                totalPages={previewData.total_paginas}
                                processingTimeMs={previewData.tempo_processamento_ms}
                                onSetEntitiesSelection={handleSetEntitiesSelection}
                                onEntityClick={setViewerPage}
                            />
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
            
            {/* Background Decorative Elements */}
            <div className="fixed top-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full pointer-events-none" style={{ background: 'var(--color-primary)', opacity: 0.04, filter: 'blur(120px)', zIndex: -10 }} />
            <div className="fixed bottom-[-10%] left-[-10%] w-[30%] h-[30%] rounded-full pointer-events-none" style={{ background: 'var(--color-accent)', opacity: 0.06, filter: 'blur(100px)', zIndex: -10 }} />
        </div>
    );
}

function AppWrapper() {
    return (
        <ErrorBoundary>
            <Toaster position="bottom-center" toastOptions={{
                className: '',
                style: {
                    background: '#252542',
                    color: '#f8fafc',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                },
            }} />
            <App />
        </ErrorBoundary>
    );
}

export default AppWrapper;
