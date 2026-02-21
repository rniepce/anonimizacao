const API_BASE = '/api';

/**
 * Analisa documento e retorna dados sensíveis identificados.
 */
export async function analyzeDocument(file, metadata) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('classe_processual', metadata.classeProcessual || '');
    formData.append('vara', metadata.vara || '');
    formData.append('comarca', metadata.comarca || '');
    formData.append('ner_mode', metadata.nerMode || 'standard');

    const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Erro ao analisar documento');
    }

    return response.json();
}

/**
 * Anonimiza documento e retorna o blob do PDF + metadados dos headers.
 */
export async function anonymizeDocument(file, metadata) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('classe_processual', metadata.classeProcessual || '');
    formData.append('vara', metadata.vara || '');
    formData.append('comarca', metadata.comarca || '');
    formData.append('ner_mode', metadata.nerMode || 'standard');

    const response = await fetch(`${API_BASE}/anonymize`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Erro ao anonimizar documento');
    }

    const blob = await response.blob();
    const headerMeta = {
        jobId: response.headers.get('X-Job-ID'),
        totalRedactions: parseInt(response.headers.get('X-Total-Redactions')) || 0,
        hashOriginal: response.headers.get('X-Original-Hash'),
        hashAnonymized: response.headers.get('X-Anonymized-Hash'),
        processingTimeMs: parseInt(response.headers.get('X-Processing-Time-Ms')) || 0,
    };

    return { blob, meta: headerMeta };
}

/**
 * Conecta ao stream SSE de progresso. Retorna função de cleanup.
 */
export function streamProgress(jobId, onUpdate, onError) {
    try {
        const evtSource = new EventSource(`${API_BASE}/progress/${jobId}`);

        evtSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.done) {
                evtSource.close();
                return;
            }
            onUpdate(data);
        };

        evtSource.onerror = () => {
            evtSource.close();
            if (onError) onError();
        };

        return () => evtSource.close();
    } catch {
        if (onError) onError();
        return () => { };
    }
}

/**
 * Polling de progresso (fallback para SSE).
 */
export function pollProgress(jobId, onUpdate) {
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/progress/${jobId}/status`);
            const data = await response.json();

            if (data.status === 'not_found') {
                clearInterval(interval);
                return;
            }

            onUpdate(data);

            if (data.porcentagem >= 100) {
                clearInterval(interval);
            }
        } catch {
            // Ignore polling errors
        }
    }, 500);

    return () => clearInterval(interval);
}
