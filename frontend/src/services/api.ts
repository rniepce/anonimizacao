import type {
    Metadata,
    PreviewData,
    AnalysisResults,
    AnonymizationMeta,
    ConfirmedEntity,
    CustomTerm,
    ProgressEvent,
} from '../types';

const API_BASE = '/api';

// ─── Helpers ─────────────────────────────────────────────────

function buildMetadataForm(file: File, metadata: Metadata): FormData {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('classe_processual', metadata.classeProcessual || '');
    formData.append('vara', metadata.vara || '');
    formData.append('comarca', metadata.comarca || '');
    formData.append('ner_mode', metadata.nerMode || 'legacy');
    return formData;
}

async function extractErrorMessage(response: Response, fallback: string): Promise<string> {
    const errorText = await response.text();
    try {
        const errorJson = JSON.parse(errorText);
        return errorJson.detail || fallback;
    } catch {
        return errorText || fallback;
    }
}

// ─── API Functions ───────────────────────────────────────────

/** Analisa documento e retorna dados sensíveis identificados. */
export async function analyzeDocument(file: File, metadata: Metadata): Promise<AnalysisResults> {
    const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        body: buildMetadataForm(file, metadata),
    });

    if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Erro ao analisar documento'));
    }

    return response.json();
}

/** Analisa documento e gera PDF de preview com destaques visuais. */
export async function analyzePreview(file: File, metadata: Metadata): Promise<PreviewData> {
    const response = await fetch(`${API_BASE}/analyze-preview`, {
        method: 'POST',
        body: buildMetadataForm(file, metadata),
    });

    if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Erro ao analisar documento'));
    }

    return response.json();
}

/** Anonimiza seletivamente com entidades confirmadas + termos customizados. */
export async function anonymizeSelective(
    jobId: string,
    entities: ConfirmedEntity[],
    customTerms: CustomTerm[],
    mode?: string | null
): Promise<{ blob: Blob; meta: AnonymizationMeta }> {
    const body = {
        job_id: jobId,
        entities,
        custom_terms: customTerms || [],
        mode: mode || null,
    };

    const response = await fetch(`${API_BASE}/anonymize-selective`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });

    if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Erro ao anonimizar documento'));
    }

    const blob = await response.blob();
    const meta: AnonymizationMeta = {
        jobId: response.headers.get('X-Job-ID'),
        totalRedactions: parseInt(response.headers.get('X-Total-Redactions') || '0') || 0,
        hashOriginal: response.headers.get('X-Original-Hash'),
        hashAnonymized: response.headers.get('X-Anonymized-Hash'),
        mode: response.headers.get('X-Anonymization-Mode'),
    };

    return { blob, meta };
}

/** Anonimiza documento e retorna o blob do PDF + metadados dos headers. */
export async function anonymizeDocument(
    file: File,
    metadata: Metadata
): Promise<{ blob: Blob; meta: AnonymizationMeta }> {
    const response = await fetch(`${API_BASE}/anonymize`, {
        method: 'POST',
        body: buildMetadataForm(file, metadata),
    });

    if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Erro ao anonimizar documento'));
    }

    const blob = await response.blob();
    const meta: AnonymizationMeta = {
        jobId: response.headers.get('X-Job-ID'),
        totalRedactions: parseInt(response.headers.get('X-Total-Redactions') || '0') || 0,
        hashOriginal: response.headers.get('X-Original-Hash'),
        hashAnonymized: response.headers.get('X-Anonymized-Hash'),
        processingTimeMs: parseInt(response.headers.get('X-Processing-Time-Ms') || '0') || 0,
    };

    return { blob, meta };
}

/** Conecta ao stream SSE de progresso. Retorna função de cleanup. */
export function streamProgress(
    jobId: string,
    onUpdate: (data: ProgressEvent) => void,
    onError?: () => void
): () => void {
    try {
        const evtSource = new EventSource(`${API_BASE}/progress/${jobId}`);

        evtSource.onmessage = (event: MessageEvent) => {
            const data: ProgressEvent = JSON.parse(event.data);
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
        return () => {};
    }
}

/** Polling de progresso (fallback para SSE). */
export function pollProgress(
    jobId: string,
    onUpdate: (data: ProgressEvent) => void
): () => void {
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/progress/${jobId}/status`);
            const data: ProgressEvent = await response.json();

            if (data.status === 'not_found') {
                clearInterval(interval);
                return;
            }

            onUpdate(data);

            if ((data.porcentagem ?? 0) >= 100) {
                clearInterval(interval);
            }
        } catch {
            // Ignore polling errors
        }
    }, 500);

    return () => clearInterval(interval);
}
