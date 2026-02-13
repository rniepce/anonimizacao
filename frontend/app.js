/**
 * TJMG Anonymizer - Frontend Application
 */

// API Configuration
const API_BASE = '/api';

// DOM Elements
const elements = {
    uploadArea: document.getElementById('uploadArea'),
    fileInput: document.getElementById('fileInput'),
    fileInfo: document.getElementById('fileInfo'),
    fileName: document.getElementById('fileName'),
    fileSize: document.getElementById('fileSize'),
    removeFile: document.getElementById('removeFile'),
    metadataForm: document.getElementById('metadataForm'),
    actionButtons: document.getElementById('actionButtons'),
    btnAnalyze: document.getElementById('btnAnalyze'),
    btnAnonymize: document.getElementById('btnAnonymize'),
    progressSection: document.getElementById('progressSection'),
    progressTitle: document.getElementById('progressTitle'),
    progressFill: document.getElementById('progressFill'),
    progressStatus: document.getElementById('progressStatus'),
    resultsSection: document.getElementById('resultsSection'),
    jobId: document.getElementById('jobId'),
    statPages: document.getElementById('statPages'),
    statIdentified: document.getElementById('statIdentified'),
    statRedacted: document.getElementById('statRedacted'),
    statTime: document.getElementById('statTime'),
    dataTableBody: document.getElementById('dataTableBody'),
    downloadSection: document.getElementById('downloadSection'),
    btnDownload: document.getElementById('btnDownload'),
    hashOriginal: document.getElementById('hashOriginal'),
    hashAnonymized: document.getElementById('hashAnonymized'),
    classeProcessual: document.getElementById('classeProcessual'),
    vara: document.getElementById('vara'),
    comarca: document.getElementById('comarca'),
};

// State
let selectedFile = null;
let currentJobId = null;
let anonymizedBlob = null;

// ============================================
// Event Listeners
// ============================================

// Upload area click
elements.uploadArea.addEventListener('click', () => {
    elements.fileInput.click();
});

// File input change
elements.fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
    }
});

// Drag and drop
elements.uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    elements.uploadArea.classList.add('dragover');
});

elements.uploadArea.addEventListener('dragleave', () => {
    elements.uploadArea.classList.remove('dragover');
});

elements.uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    elements.uploadArea.classList.remove('dragover');

    if (e.dataTransfer.files.length > 0) {
        handleFileSelect(e.dataTransfer.files[0]);
    }
});

// Remove file
elements.removeFile.addEventListener('click', () => {
    resetUpload();
});

// Analyze button
elements.btnAnalyze.addEventListener('click', () => {
    analyzeDocument();
});

// Anonymize button
elements.btnAnonymize.addEventListener('click', () => {
    anonymizeDocument();
});

// Download button
elements.btnDownload.addEventListener('click', () => {
    downloadAnonymized();
});

// ============================================
// Functions
// ============================================

function handleFileSelect(file) {
    // Validate file type
    const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    if (!validTypes.includes(file.type) && !file.name.endsWith('.pdf') && !file.name.endsWith('.docx')) {
        alert('Por favor, selecione um arquivo PDF ou DOCX.');
        return;
    }

    selectedFile = file;

    // Update UI
    elements.fileName.textContent = file.name;
    elements.fileSize.textContent = formatFileSize(file.size);

    elements.uploadArea.classList.add('hidden');
    elements.fileInfo.classList.remove('hidden');
    elements.metadataForm.classList.remove('hidden');
    elements.actionButtons.classList.remove('hidden');

    // Hide previous results
    elements.resultsSection.classList.add('hidden');
}

function resetUpload() {
    selectedFile = null;
    currentJobId = null;
    anonymizedBlob = null;

    elements.fileInput.value = '';
    elements.uploadArea.classList.remove('hidden');
    elements.fileInfo.classList.add('hidden');
    elements.metadataForm.classList.add('hidden');
    elements.actionButtons.classList.add('hidden');
    elements.resultsSection.classList.add('hidden');
    elements.progressSection.classList.add('hidden');
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

async function analyzeDocument() {
    if (!selectedFile) return;

    showProgress('Analisando documento...', 'Extraindo texto e identificando dados sensíveis');

    try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('classe_processual', elements.classeProcessual.value);
        formData.append('vara', elements.vara.value);
        formData.append('comarca', elements.comarca.value);

        // Simulate progress
        simulateProgress();

        const response = await fetch(`${API_BASE}/analyze`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error('Erro ao analisar documento');
        }

        const data = await response.json();
        showAnalysisResults(data);

    } catch (error) {
        console.error('Error:', error);
        alert('Erro ao analisar documento: ' + error.message);
        hideProgress();
    }
}

async function anonymizeDocument() {
    if (!selectedFile) return;

    showProgress('Anonimizando documento...', 'Aplicando tarjas sobre dados sensíveis');

    try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('classe_processual', elements.classeProcessual.value);
        formData.append('vara', elements.vara.value);
        formData.append('comarca', elements.comarca.value);

        // Simulate progress
        simulateProgress();

        const response = await fetch(`${API_BASE}/anonymize`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error('Erro ao anonimizar documento');
        }

        // Get metadata from headers
        currentJobId = response.headers.get('X-Job-ID');
        const totalRedactions = response.headers.get('X-Total-Redactions');
        const hashOriginal = response.headers.get('X-Original-Hash');
        const hashAnonymized = response.headers.get('X-Anonymized-Hash');
        const processingTime = response.headers.get('X-Processing-Time-Ms');

        // Save blob for download
        anonymizedBlob = await response.blob();

        // Show results
        showAnonymizationResults({
            job_id: currentJobId,
            total_redacoes: parseInt(totalRedactions) || 0,
            hash_original: hashOriginal,
            hash_anonimizado: hashAnonymized,
            tempo_processamento_ms: parseInt(processingTime) || 0,
        });

    } catch (error) {
        console.error('Error:', error);
        alert('Erro ao anonimizar documento: ' + error.message);
        hideProgress();
    }
}

function showProgress(title, status) {
    elements.progressTitle.textContent = title;
    elements.progressStatus.textContent = status;
    elements.progressFill.style.width = '0%';
    elements.progressSection.classList.remove('hidden');
    elements.actionButtons.classList.add('hidden');
}

function hideProgress() {
    elements.progressSection.classList.add('hidden');
    elements.actionButtons.classList.remove('hidden');
}

function startProgressStream(jobId) {
    // Tentar usar SSE para progresso em tempo real
    try {
        const evtSource = new EventSource(`${API_BASE}/progress/${jobId}`);

        evtSource.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.done) {
                evtSource.close();
                return;
            }

            // Atualizar barra de progresso
            elements.progressFill.style.width = data.porcentagem + '%';

            // Atualizar status com informações detalhadas
            let statusMsg = data.mensagem;
            if (data.total_paginas > 0) {
                statusMsg += ` (Página ${data.pagina_atual}/${data.total_paginas})`;
            }
            if (data.dados_encontrados > 0) {
                statusMsg += ` • ${data.dados_encontrados} dados encontrados`;
            }
            elements.progressStatus.textContent = statusMsg;
        };

        evtSource.onerror = () => {
            evtSource.close();
            // Fallback para polling se SSE falhar
            startProgressPolling(jobId);
        };

        return evtSource;
    } catch (e) {
        // Fallback para polling
        return startProgressPolling(jobId);
    }
}

function startProgressPolling(jobId) {
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/progress/${jobId}/status`);
            const data = await response.json();

            if (data.status === 'not_found') {
                clearInterval(pollInterval);
                return;
            }

            elements.progressFill.style.width = data.porcentagem + '%';

            let statusMsg = data.mensagem;
            if (data.total_paginas > 0) {
                statusMsg += ` (Página ${data.pagina_atual}/${data.total_paginas})`;
            }
            elements.progressStatus.textContent = statusMsg;

            if (data.porcentagem >= 100) {
                clearInterval(pollInterval);
            }
        } catch (e) {
            // Ignorar erros de polling
        }
    }, 500);

    return { close: () => clearInterval(pollInterval) };
}

// Mantém simulação como fallback quando SSE não está disponível
function simulateProgress() {
    let progress = 0;
    const stages = [
        { progress: 10, status: 'Iniciando processamento...' },
        { progress: 25, status: 'Extraindo texto do documento' },
        { progress: 45, status: 'Identificando padrões com Regex' },
        { progress: 65, status: 'Analisando entidades com NLP' },
        { progress: 80, status: 'Aplicando anonimização' },
        { progress: 95, status: 'Finalizando processamento' },
    ];

    let stageIndex = 0;
    const interval = setInterval(() => {
        if (stageIndex < stages.length) {
            const stage = stages[stageIndex];
            elements.progressFill.style.width = stage.progress + '%';
            elements.progressStatus.textContent = stage.status;
            stageIndex++;
        } else {
            clearInterval(interval);
        }
    }, 800);

    return { close: () => clearInterval(interval) };
}

function showAnalysisResults(data) {
    hideProgress();

    elements.jobId.textContent = `Job: ${data.job_id}`;
    elements.statPages.textContent = data.total_paginas;
    elements.statIdentified.textContent = data.total_identificados;
    elements.statRedacted.textContent = '-';
    elements.statTime.textContent = data.tempo_processamento_ms + 'ms';

    // Populate table
    elements.dataTableBody.innerHTML = '';

    if (data.dados_sensiveis.length === 0) {
        elements.dataTableBody.innerHTML = `
            <tr>
                <td colspan="4" style="text-align: center; color: var(--color-text-muted);">
                    Nenhum dado sensível identificado
                </td>
            </tr>
        `;
    } else {
        data.dados_sensiveis.forEach(item => {
            const row = document.createElement('tr');
            const typeClass = item.tipo.toLowerCase().replace('_', '');
            row.innerHTML = `
                <td><span class="type-badge ${typeClass}">${item.tipo}</span></td>
                <td>${maskValue(item.valor)}</td>
                <td>${item.pagina}</td>
                <td>
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width: ${item.confianca * 100}%"></div>
                    </div>
                </td>
            `;
            elements.dataTableBody.appendChild(row);
        });
    }

    // Hide download section for analysis only
    elements.downloadSection.classList.add('hidden');

    elements.resultsSection.classList.remove('hidden');
    elements.actionButtons.classList.remove('hidden');
}

function showAnonymizationResults(data) {
    hideProgress();

    elements.jobId.textContent = `Job: ${data.job_id}`;
    elements.statRedacted.textContent = data.total_redacoes;
    elements.statTime.textContent = data.tempo_processamento_ms + 'ms';

    // Show hashes
    elements.hashOriginal.textContent = truncateHash(data.hash_original);
    elements.hashOriginal.title = data.hash_original;
    elements.hashAnonymized.textContent = truncateHash(data.hash_anonimizado);
    elements.hashAnonymized.title = data.hash_anonimizado;

    // Show download section
    elements.downloadSection.classList.remove('hidden');

    elements.resultsSection.classList.remove('hidden');
    elements.actionButtons.classList.remove('hidden');
}

function maskValue(value) {
    if (!value) return '***';
    if (value.length <= 4) return '***';
    return value.substring(0, 3) + '***';
}

function truncateHash(hash) {
    if (!hash) return '---';
    return hash.substring(0, 16) + '...';
}

function downloadAnonymized() {
    if (!anonymizedBlob) {
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
}

// ============================================
// Type Badge Classes
// ============================================

function getTypeBadgeClass(type) {
    const classes = {
        'CPF': 'cpf',
        'CNPJ': 'cnpj',
        'EMAIL': 'email',
        'TELEFONE': 'telefone',
        'PESSOA': 'pessoa',
        'ENDERECO': 'endereco',
    };
    return classes[type] || 'default';
}
