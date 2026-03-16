import { useState, useCallback } from 'react';
import type { Metadata, PreviewData, AnonymizationMeta, ProgressInfo } from './types';
import ErrorBoundary from './components/ErrorBoundary';
import Header from './components/Header';
import UploadSection from './components/UploadSection';
import MetadataForm from './components/MetadataForm';
import ProgressSection from './components/ProgressSection';
import DocumentViewer from './components/DocumentViewer';
import EntityPanel from './components/EntityPanel';
import Footer from './components/Footer';
import { analyzePreview, anonymizeSelective } from './services/api';

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
    const [customTerms, setCustomTerms] = useState<string[]>([]);

    // Download state
    const [anonymizedBlob, setAnonymizedBlob] = useState<Blob | null>(null);
    const [anonymizationMeta, setAnonymizationMeta] = useState<AnonymizationMeta | null>(null);
    const [isAnonymizing, setIsAnonymizing] = useState(false);

    const handleFileSelect = useCallback((file: File) => {
        const validExts = ['.pdf', '.docx'];
        const ext = '.' + file.name.split('.').pop()?.toLowerCase();
        if (!validExts.includes(ext)) {
            alert('Por favor, selecione um arquivo PDF ou DOCX.');
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
            setTimeout(() => {
                alert('Erro ao analisar documento: ' + ((error as Error)?.message || 'Erro desconhecido'));
            }, 100);
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
            alert('Erro ao anonimizar documento: ' + ((error as Error)?.message || 'Erro desconhecido'));
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

    const handleSelectAll = useCallback(() => {
        if (!previewData) return;
        const allIds = new Set(previewData.dados_sensiveis.map((_: unknown, i: number) => i));
        setSelectedEntityIds(allIds);
    }, [previewData]);

    const handleDeselectAll = useCallback(() => {
        setSelectedEntityIds(new Set());
    }, []);

    const handleAddCustomTerm = useCallback((term: string) => {
        setCustomTerms((prev) => [...prev, term]);
    }, []);

    const handleRemoveCustomTerm = useCallback((idx: number) => {
        setCustomTerms((prev) => prev.filter((_: string, i: number) => i !== idx));
    }, []);

    const handleDownload = useCallback(() => {
        if (!anonymizedBlob || !selectedFile) {
            alert('Nenhum arquivo disponível para download');
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

    return (
        <div className="container">
            <Header />

            <main className="main">
                {/* Upload Section */}
                {view === 'upload' && (
                    <section className="upload-section glass-card">
                        <div className="section-header">
                            <h2>📤 Upload de Documento</h2>
                            <p>Envie seu PDF ou DOCX para análise e anonimização</p>
                        </div>

                        <UploadSection
                            selectedFile={selectedFile}
                            onFileSelect={handleFileSelect}
                            onRemoveFile={handleRemoveFile}
                        />

                        {selectedFile && (
                            <>
                                <MetadataForm metadata={metadata} onChange={setMetadata} />
                                <div className="action-buttons">
                                    <button className="btn btn-primary" onClick={handleAnalyze}>
                                        <span className="btn-icon-text">🔍</span>
                                        Analisar e Revisar
                                    </button>
                                </div>
                            </>
                        )}
                    </section>
                )}

                {/* Progress Section */}
                {view === 'progress' && (
                    <ProgressSection
                        title={progressInfo.title}
                        status={progressInfo.status}
                        progress={progressInfo.progress}
                    />
                )}

                {/* Review Section — Document Viewer + Entity Panel */}
                {view === 'review' && previewData && (
                    <section className="review-section">
                        <div className="review-header glass-card">
                            <div className="review-header-left">
                                <h2>📋 Revisão de Anonimização</h2>
                                <p>
                                    Revise os dados identificados, desmarque o que deseja manter visível
                                    e adicione termos customizados.
                                </p>
                            </div>
                            <button className="btn btn-secondary" onClick={handleNewFile}>
                                ← Novo Arquivo
                            </button>
                        </div>
                        <div className="review-layout">
                            <DocumentViewer previewUrl={previewData.preview_url} totalPages={previewData.total_paginas} />
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
                            />
                        </div>
                    </section>
                )}

                {/* Download Section */}
                {view === 'download' && anonymizedBlob && (
                    <section className="download-final-section glass-card">
                        <div className="section-header">
                            <h2>✅ Anonimização Concluída</h2>
                        </div>

                        <div className="download-stats">
                            <div className="stat-card">
                                <div className="stat-icon">🔒</div>
                                <div className="stat-value">{anonymizationMeta?.totalRedactions ?? 0}</div>
                                <div className="stat-label">Itens Anonimizados</div>
                            </div>
                            <div className="stat-card">
                                <div className="stat-icon">📄</div>
                                <div className="stat-value">{previewData?.total_paginas ?? 0}</div>
                                <div className="stat-label">Páginas</div>
                            </div>
                        </div>

                        {anonymizationMeta && (
                            <div className="hash-info">
                                <div className="hash-item">
                                    <span className="hash-label">Hash Original:</span>
                                    <code title={anonymizationMeta.hashOriginal ?? undefined}>
                                        {anonymizationMeta.hashOriginal
                                            ? anonymizationMeta.hashOriginal.substring(0, 16) + '...'
                                            : '---'}
                                    </code>
                                </div>
                                <div className="hash-item">
                                    <span className="hash-label">Hash Anonimizado:</span>
                                    <code title={anonymizationMeta.hashAnonymized ?? undefined}>
                                        {anonymizationMeta.hashAnonymized
                                            ? anonymizationMeta.hashAnonymized.substring(0, 16) + '...'
                                            : '---'}
                                    </code>
                                </div>
                            </div>
                        )}

                        <div className="download-actions">
                            <button className="btn btn-success btn-large" onClick={handleDownload}>
                                <span className="btn-icon-text">⬇️</span>
                                Baixar PDF Anonimizado
                            </button>
                        </div>

                        <div className="download-secondary-actions">
                            <button className="btn btn-secondary" onClick={handleBackToReview}>
                                ← Voltar para Revisão
                            </button>
                            <button className="btn btn-secondary" onClick={handleNewFile}>
                                📤 Novo Arquivo
                            </button>
                        </div>
                    </section>
                )}
            </main>

            <Footer />
        </div>
    );
}

function AppWrapper() {
    return (
        <ErrorBoundary>
            <App />
        </ErrorBoundary>
    );
}

export default AppWrapper;
