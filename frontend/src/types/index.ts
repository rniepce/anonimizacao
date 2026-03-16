// ─── Domain Types ────────────────────────────────────────────

/** Entidade sensível detectada pelo backend. */
export interface SensitiveEntity {
    tipo: string;
    valor: string;
    pagina: number;
    posicao?: Record<string, unknown>;
    confianca?: number;
}

/** Metadados do processo judicial. */
export interface Metadata {
    classeProcessual: string;
    vara: string;
    comarca: string;
    nerMode: string;
}

/** Resposta de /api/analyze-preview. */
export interface PreviewData {
    job_id: string;
    preview_url: string;
    dados_sensiveis: SensitiveEntity[];
    total_paginas: number;
    total_identificados: number;
    tempo_processamento_ms: number;
    texto_por_pagina: Record<string, string>;
}

/** Metadados retornados após anonimização. */
export interface AnonymizationMeta {
    jobId: string | null;
    totalRedactions: number;
    hashOriginal: string | null;
    hashAnonymized: string | null;
    mode?: string | null;
    processingTimeMs?: number;
}

/** Informações de progresso da análise. */
export interface ProgressInfo {
    title: string;
    status: string;
    progress: number;
}

// ─── API Types ───────────────────────────────────────────────

/** Entidade confirmada para envio ao endpoint de anonimização. */
export interface ConfirmedEntity {
    tipo: string;
    valor: string;
    pagina: number;
    posicao?: Record<string, unknown>;
}

/** Resultado de analyzeDocument / análise legada. */
export interface AnalysisResults {
    job_id: string;
    total_paginas: number;
    total_identificados: number;
    tempo_processamento_ms: number;
    dados_sensiveis: SensitiveEntity[];
}

/** Dados do stream de progresso SSE. */
export interface ProgressEvent {
    done?: boolean;
    status?: string;
    porcentagem?: number;
}
