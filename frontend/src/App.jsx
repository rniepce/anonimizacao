import { useState, useCallback } from 'react';
import Header from './components/Header';
import UploadSection from './components/UploadSection';
import MetadataForm from './components/MetadataForm';
import ProgressSection from './components/ProgressSection';
import ResultsSection from './components/ResultsSection';
import Footer from './components/Footer';
import { analyzeDocument, anonymizeDocument } from './services/api';

function App() {
    const [selectedFile, setSelectedFile] = useState(null);
    const [metadata, setMetadata] = useState({
        classeProcessual: '',
        vara: '',
        comarca: '',
        nerMode: 'standard',
    });

    // UI state
    const [view, setView] = useState('upload'); // 'upload' | 'progress' | 'results'
    const [progressInfo, setProgressInfo] = useState({ title: '', status: '', progress: 0 });
    const [analysisResults, setAnalysisResults] = useState(null);
    const [anonymizationResults, setAnonymizationResults] = useState(null);
    const [anonymizedBlob, setAnonymizedBlob] = useState(null);

    const handleFileSelect = useCallback((file) => {
        const validExts = ['.pdf', '.docx'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!validExts.includes(ext)) {
            alert('Por favor, selecione um arquivo PDF ou DOCX.');
            return;
        }
        setSelectedFile(file);
        setAnalysisResults(null);
        setAnonymizationResults(null);
        setAnonymizedBlob(null);
    }, []);

    const handleRemoveFile = useCallback(() => {
        setSelectedFile(null);
        setAnalysisResults(null);
        setAnonymizationResults(null);
        setAnonymizedBlob(null);
        setView('upload');
    }, []);

    const simulateProgress = useCallback(() => {
        const stages = [
            { progress: 10, status: 'Iniciando processamento...' },
            { progress: 25, status: 'Extraindo texto do documento' },
            { progress: 45, status: 'Identificando padrões com Regex' },
            { progress: 65, status: 'Analisando entidades com NLP' },
            { progress: 80, status: 'Aplicando anonimização' },
            { progress: 95, status: 'Finalizando processamento' },
        ];

        let i = 0;
        const interval = setInterval(() => {
            if (i < stages.length) {
                setProgressInfo((prev) => ({
                    ...prev,
                    progress: stages[i].progress,
                    status: stages[i].status,
                }));
                i++;
            } else {
                clearInterval(interval);
            }
        }, 800);

        return () => clearInterval(interval);
    }, []);

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
            const data = await analyzeDocument(selectedFile, metadata);
            stopSim();
            setAnalysisResults(data);
            setAnonymizationResults(null);
            setAnonymizedBlob(null);
            setView('results');
        } catch (error) {
            stopSim();
            console.error('Error:', error);
            alert('Erro ao analisar documento: ' + error.message);
            setView('upload');
        }
    }, [selectedFile, metadata, simulateProgress]);

    const handleAnonymize = useCallback(async () => {
        if (!selectedFile) return;

        setView('progress');
        setProgressInfo({
            title: 'Anonimizando documento...',
            status: 'Aplicando tarjas sobre dados sensíveis',
            progress: 0,
        });

        const stopSim = simulateProgress();

        try {
            const { blob, meta } = await anonymizeDocument(selectedFile, metadata);
            stopSim();
            setAnonymizedBlob(blob);
            setAnonymizationResults(meta);
            setView('results');
        } catch (error) {
            stopSim();
            console.error('Error:', error);
            alert('Erro ao anonimizar documento: ' + error.message);
            setView('upload');
        }
    }, [selectedFile, metadata, simulateProgress]);

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

    return (
        <div className="container">
            <Header />

            <main className="main">
                {/* Upload Section — always visible when file not selected or viewing results */}
                {(view === 'upload' || view === 'results') && (
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
                                    <button className="btn btn-secondary" onClick={handleAnalyze}>
                                        <span className="btn-icon-text">🔍</span>
                                        Analisar
                                    </button>
                                    <button className="btn btn-primary" onClick={handleAnonymize}>
                                        <span className="btn-icon-text">🔒</span>
                                        Anonimizar
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

                {/* Results Section */}
                {view === 'results' && (analysisResults || anonymizationResults) && (
                    <ResultsSection
                        analysisResults={analysisResults}
                        anonymizationResults={anonymizationResults}
                        onDownload={handleDownload}
                        hasBlob={!!anonymizedBlob}
                    />
                )}
            </main>

            <Footer />
        </div>
    );
}

export default App;
