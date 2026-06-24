import apiClient from './api';

export type ColumnRole = 'quasi_identifier' | 'sensitive_attribute' | 'pii' | 'feature';

export interface ColumnMapping {
    name: string;
    roles: ColumnRole[];
    type: string;
    description: string;
}

export interface AnalysisProfileCreatePayload {
    dataset_name: string;
    description: string;
    columns: ColumnMapping[];
    secteur?: string;
    public_sample_frac?: number;
    imbalance_columns?: string[];
    correlation_columns?: string[];
    id_column?: string | null;
    sensitive_health_columns?: string[];
}

export interface AttackExplanation {
    attack: string;
    attack_id: string;
    score: number;
    level: string;
    color: string;
    emoji: string;
    explanation: string;
    recommendation: string;
}

export interface CheckExplanation {
    check_id: string;
    label: string;
    description: string;
    status: string;
    color: string;
    emoji: string;
    detected: boolean;
    explanation: string;
}

export interface ScoreAExplanation {
    score: number;
    level: string;
    color: string;
    emoji: string;
    summary: string;
    verdict: string;
}

export interface XAIReport {
    score_a: ScoreAExplanation;
    attacks: AttackExplanation[];
    checks: CheckExplanation[];
    succ_score: number;
    vuln_score: number;
}

export interface ScoreResult {
    dataset_id: string;
    dataset_name: string;
    computed_at: string;
    taux_linkage: number;
    taux_singling: number;
    taux_inference: number;
    Succ: number;
    detected_checks: number;
    Vuln: number;
    A: number;
    xai: XAIReport;
}

export interface AnalysisProfile {
    dataset_id: string;
    dataset_name: string;
    description: string;
    secteur?: string;
    columns: Record<string, { roles: string[]; type: string; description: string }>;
    attacks: {
        quasi_identifiers: string[];
        sensitive_attribute: string;
        public_sample_frac: number;
    };
    checks: Record<string, any>;
    created_at: string;
}

export interface ScoreIIncident {
    incident_id: string;
    titre: string;
    sim: number;
    grav: number;
}

export interface ScoreIResult {
    dataset_id: string;
    dataset_name: string;
    computed_at: string;
    scoreI: number;
    secteur: string;
    domaines: string[];
    top3: ScoreIIncident[];
    mapping_actions?: {
        colonne: string;
        signal: string;
        domaine_mit: string;
        source_reglementaire: string;
        action: string;
    }[];
    score_i_details?: Record<string, any>;
}

export interface ScoreBResult {
    dataset_id: string;
    dataset_name: string;
    computed_at: string;
    B: number;
    b1: number;
    b2: number;
    b3: number;
    b4: number;
    details: Record<string, any>;
}

export interface RiskXAIItem {
    column: string;
    signal: string;
    explanation: string;
    severity: number;
    legal_source: string;
}

export interface ComputeRiskResult {
    dataset_id: string;
    dataset_name: string;
    computed_at: string;
    B: number;
    A: number;
    I: number;
    score_b_details: { b1: number; b2: number; b3: number; b4: number };
    score_i_details: Record<string, any>;
    c1: number;
    c2: number;
    C: number;
    R_base: number;
    R_final: number;
    classification: 'Faible' | 'Modéré' | 'Élevé' | 'Critique' | string;
    xai: RiskXAIItem[];
}

export interface SignalScanColumnResult {
    raw_column: string;
    normalized: string;
    match_method: 'exact_fr' | 'exact_en' | 'alias' | 'fuzzy' | 'profiling' | 'none';
    ref_entry: string | null;
    signal: 'S_pii' | 'S_prot' | 'S_sens' | 'S_dec' | null;
    mit_domain: string;
    legal_source: string;
    confidence: number;
    human_validated: boolean;
    comment: string;
}

export interface SignalScanMetrics {
    exact: number;
    alias: number;
    fuzzy: number;
    profiling: number;
    none: number;
    total_columns: number;
}

export interface SignalScanResult {
    columns: SignalScanColumnResult[];
    metrics: SignalScanMetrics;
}

export interface AnalysisProfileSummary {
    quasi_identifiers: string[];
    pii_columns: string[];
    sensitive_attribute: string | null;
    id_column: string | null;
    sensitive_health_columns: string[];
}

export interface AnalysisProfileProposal {
    dataset_id: string;
    dataset_name: string;
    description: string;
    secteur: string;
    public_sample_frac: number;
    columns: ColumnMapping[];
    imbalance_columns: string[];
    correlation_columns: string[];
    id_column: string | null;
    sensitive_health_columns: string[];
    scan_result: SignalScanResult;
    derived_summary: AnalysisProfileSummary;
}

export const computeScore = async (datasetId: string): Promise<ScoreResult> => {
    const resp = await apiClient.post(`/immuneguard/score/${datasetId}`);
    return resp.data;
};

export const getScore = async (datasetId: string): Promise<ScoreResult | null> => {
    try {
        const resp = await apiClient.get(`/immuneguard/score/${datasetId}`);
        return resp.data;
    } catch (err: any) {
        if (err.response?.status === 404) return null;
        throw err;
    }
};

export const computeScoreI = async (datasetId: string): Promise<ScoreIResult> => {
    const resp = await apiClient.post(`/immuneguard/score-i/${datasetId}`);
    return resp.data;
};

export const computeScoreB = async (datasetId: string): Promise<ScoreBResult> => {
    const resp = await apiClient.post('/immuneguard/score-b', { dataset_id: datasetId });
    return resp.data;
};

export const computeRisk = async (
    datasetId: string,
    options?: { A?: number; datacard?: Record<string, string> }
): Promise<ComputeRiskResult> => {
    const resp = await apiClient.post('/immuneguard/compute-risk', {
        dataset_id: datasetId,
        ...(options?.A !== undefined ? { A: options.A } : {}),
        ...(options?.datacard ? { datacard: options.datacard } : {}),
    });
    return resp.data;
};

export const getScoreI = async (datasetId: string): Promise<ScoreIResult | null> => {
    try {
        const resp = await apiClient.get(`/immuneguard/score-i/${datasetId}`);
        return resp.data;
    } catch (err: any) {
        if (err.response?.status === 404) return null;
        throw err;
    }
};

export const listScores = async (): Promise<ScoreResult[]> => {
    const resp = await apiClient.get('/immuneguard/scores');
    return resp.data;
};

export const scanSignalsForDataset = async (datasetId: string): Promise<SignalScanResult> => {
    const resp = await apiClient.post(`/immuneguard/scan-signals/${datasetId}`);
    return resp.data;
};

export const getAnalysisProfile = async (datasetId: string): Promise<AnalysisProfile | null> => {
    try {
        const resp = await apiClient.get(`/immuneguard/analysis-profile/${datasetId}`);
        return resp.data;
    } catch (err: any) {
        if (err.response?.status === 404) return null;
        throw err;
    }
};

export const proposeAnalysisProfile = async (datasetId: string): Promise<AnalysisProfileProposal> => {
    const resp = await apiClient.post(`/immuneguard/analysis-profile/${datasetId}/auto`);
    return resp.data;
};

export const createAnalysisProfile = async (
    datasetId: string,
    payload: AnalysisProfileProposal | AnalysisProfileCreatePayload
): Promise<any> => {
    const resp = await apiClient.post(`/immuneguard/analysis-profile/${datasetId}`, payload);
    return resp.data;
};
