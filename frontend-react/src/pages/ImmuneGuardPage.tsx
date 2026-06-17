import { useEffect, useMemo, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSearchParams } from 'react-router-dom';
import {
    AlertTriangle,
    CheckCircle2,
    ChevronRight,
    Cpu,
    Database,
    Info,
    LayoutList,
    Lock,
    RefreshCw,
    Shield,
    Zap,
} from 'lucide-react';
import apiClient from '../services/api';
import {
    computeRisk,
    computeScore,
    computeScoreI,
    createAnalysisProfile,
    getScore,
    getScoreI,
    proposeAnalysisProfile,
} from '../services/immuneguardService';
import type {
    AnalysisProfileProposal,
    ComputeRiskResult,
    ScoreIResult,
    ScoreResult,
    SignalScanColumnResult,
} from '../services/immuneguardService';
import { Button } from '../components/ui/Button';
import DataCardForm, { type DataCardData } from '../components/immuneguard/DataCardForm';
import { useToast } from '../context/ToastContext';

const shortSignalLabel = (signal: string | null | undefined) => {
    const map: Record<string, string> = {
        S_pii: 'PII',
        S_prot: 'PROT',
        S_sens: 'SENS',
        S_dec: 'DEC',
    };
    if (!signal) return 'SIG';
    return map[signal] ?? signal.replace(/^S_/, '').toUpperCase();
};

const formatSignalLine = (col: SignalScanColumnResult) =>
    `${shortSignalLabel(col.signal)} · ${col.raw_column}`;

type DecompSubMetricProps = {
    title: string;
    subtitle: string;
    explanation: string;
    value: string;
    color?: string;
};

const DecompSubMetric = ({ title, subtitle, explanation, value, color = '#38bdf8' }: DecompSubMetricProps) => (
    <div className="glass p-5 rounded-2xl border border-white/5 space-y-2">
        <div className="flex items-baseline justify-between gap-3">
            <div className="min-w-0">
                <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">{subtitle}</p>
                <h5 className="text-base font-bold text-white mt-1 leading-snug">{title}</h5>
            </div>
            <span className="text-2xl font-black tabular-nums shrink-0" style={{ color }}>{value}</span>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">{explanation}</p>
    </div>
);

const StatBox = ({ label, value, color, icon: Icon }: any) => (
    <motion.div
        whileHover={{ y: -4, scale: 1.01 }}
        className="glass p-6 rounded-3xl border border-white/5 bg-gradient-to-br from-white/5 to-transparent"
    >
        <div className="flex items-center gap-3 mb-4">
            <div className="p-2 rounded-xl bg-white/5 text-slate-400">
                <Icon size={18} />
            </div>
            <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">{label}</p>
        </div>
        <p className="text-3xl font-black tabular-nums tracking-tighter" style={{ color }}>
            {value}
        </p>
    </motion.div>
);

const Gauge = ({ value, label, color }: { value: number; label: string; color: string }) => {
    const size = 200;
    const strokeWidth = 12;
    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (value / 100) * circumference;

    return (
        <div className="relative flex flex-col items-center">
            <svg width={size} height={size} className="transform -rotate-90">
                <circle cx={size / 2} cy={size / 2} r={radius} stroke="currentColor" strokeWidth={strokeWidth} fill="transparent" className="text-white/5" />
                <motion.circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    stroke={color}
                    strokeWidth={strokeWidth}
                    fill="transparent"
                    strokeDasharray={circumference}
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset: offset }}
                    transition={{ duration: 1.2, ease: 'easeOut' }}
                    strokeLinecap="round"
                />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-4xl font-black text-white">{value}%</span>
                <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest mt-1">{label}</span>
            </div>
        </div>
    );
};

const pct = (value: number | undefined) => `${(((value ?? 0) * 100)).toFixed(1)}%`;

const emptyDataCard = (): DataCardData => ({
    secteur: '',
    finalite: '',
    population: '',
    pays: '',
    origine: '',
    information: '',
});

const ImmuneGuardPage = () => {
    const [searchParams] = useSearchParams();
    const urlDatasetId = searchParams.get('dataset');

    const [datasets, setDatasets] = useState<any[]>([]);
    const [selectedId, setSelectedId] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [analysisProposal, setAnalysisProposal] = useState<AnalysisProfileProposal | null>(null);
    const [scoreResult, setScoreResult] = useState<ScoreResult | null>(null);
    const [scoreIResult, setScoreIResult] = useState<ScoreIResult | null>(null);
    const [riskResult, setRiskResult] = useState<ComputeRiskResult | null>(null);
    const [isComputing, setIsComputing] = useState(false);
    const [view, setView] = useState<'global' | 'details' | 'xai'>('global');
    const [dataCard, setDataCard] = useState<DataCardData>(emptyDataCard);
    const { addToast } = useToast();

    const isDataCardComplete = useMemo(
        () => Object.values(dataCard).every((v) => v.trim() !== ''),
        [dataCard]
    );

    const fetchDatasetsList = useCallback(async () => {
        try {
            const resp = await apiClient.get('/cleaning/datasets');
            const raw = resp.data;
            const list = Array.isArray(raw) ? raw : (raw?.datasets ?? []);
            setDatasets(list);
            if (urlDatasetId && list.some((d: any) => (d.id || d.dataset_id) === urlDatasetId)) {
                setSelectedId(urlDatasetId);
            } else if (list.length > 0) {
                setSelectedId((prev) => {
                    if (prev && list.some((d: any) => (d.id || d.dataset_id) === prev)) return prev;
                    return list[0].id || list[0].dataset_id;
                });
            } else {
                setSelectedId('');
            }
        } catch (err) {
            console.error(err);
            addToast('Impossible de charger les jeux de données', 'error');
        }
    }, [urlDatasetId, addToast]);

    useEffect(() => {
        void fetchDatasetsList();
    }, [fetchDatasetsList]);

    useEffect(() => {
        if (selectedId) loadDatasetContext();
    }, [selectedId]);

    const loadDatasetContext = async () => {
        setIsLoading(true);
        setError(null);
        setAnalysisProposal(null);
        setScoreResult(null);
        setScoreIResult(null);
        setRiskResult(null);
        setView('global');
        setDataCard(emptyDataCard());

        try {
            const [existingScore, existingScoreI] = await Promise.all([
                getScore(selectedId).catch(() => null),
                getScoreI(selectedId).catch(() => null),
            ]);
            if (existingScore) setScoreResult(existingScore);
            if (existingScoreI) setScoreIResult(existingScoreI);
            setAnalysisProposal(await proposeAnalysisProfile(selectedId));
        } catch (err: any) {
            console.error(err);
            setError(err.response?.data?.detail || 'Error scanning dataset.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleRunAnalysis = async () => {
        if (!analysisProposal) return;
        if (!isDataCardComplete) {
            addToast('Veuillez compléter tous les champs de la DataCard.', 'error');
            return;
        }
        setIsComputing(true);
        try {
            const mergedProposal: AnalysisProfileProposal = {
                ...analysisProposal,
                secteur: dataCard.secteur || analysisProposal.secteur,
            };
            await createAnalysisProfile(selectedId, mergedProposal);
            const datacardPayload: Record<string, string> = { ...dataCard };
            const [sA, sI] = await Promise.all([
                computeScore(selectedId),
                computeScoreI(selectedId),
            ]);
            const risk = await computeRisk(selectedId, {
                A: sA.A,
                datacard: datacardPayload,
            });
            setScoreResult(sA);
            setScoreIResult(sI);
            setRiskResult(risk);
            setView('global');
            addToast('Analyse terminée — vues Global, Détail et XAI disponibles.', 'success');
        } catch (err) {
            console.error(err);
            addToast('Échec du calcul du score', 'error');
        } finally {
            setIsComputing(false);
        }
    };

    const riskColor = riskResult && riskResult.R_final >= 75 ? '#ef4444' : riskResult && riskResult.R_final >= 50 ? '#f59e0b' : '#22c55e';

    const currentDatasetName = datasets.find((d) => (d.id || d.dataset_id) === selectedId)?.name
        || datasets.find((d) => (d.id || d.dataset_id) === selectedId)?.dataset_name
        || selectedId;

    const selectedDatasetMeta = useMemo(
        () => datasets.find((d) => (d.id || d.dataset_id) === selectedId),
        [datasets, selectedId],
    );

    const datasetScanContext = useMemo(() => {
        const cols = analysisProposal?.scan_result?.columns ?? [];
        const detected = cols.filter((c) => Boolean(c.signal));
        const total = analysisProposal?.scan_result?.metrics?.total_columns || cols.length || 0;
        return { cols, detected, total };
    }, [analysisProposal]);

    const step1Done = Boolean(selectedId && analysisProposal && !isLoading);
    const step3Done = Boolean(riskResult);

    const showScoreWorkspace = Boolean(riskResult || isComputing);
    const showDataCardWorkspace = Boolean(analysisProposal && !showScoreWorkspace);

    return (
        <div className="space-y-8 pb-20">
            <div className="flex flex-col xl:flex-row justify-between items-start xl:items-end gap-6">
                <div>
                    <h1 className="text-4xl font-black text-white tracking-tighter mb-2">ImmuneGuard Score</h1>
                    <p className="text-slate-400 max-w-xl">
                        Scoring de risque data, IA responsable et facteur d&apos;amplification contextuelle (C) à partir de la DataCard.
                    </p>
                </div>
                <div className="flex gap-3 w-full xl:w-auto">
                    <select
                        className="input-premium min-w-[240px] flex-1 xl:flex-none appearance-none cursor-pointer bg-[#1a1a1a] text-white"
                        value={selectedId}
                        onChange={(e) => setSelectedId(e.target.value)}
                    >
                        {datasets.map((d) => (
                            <option
                                key={d.id || d.dataset_id}
                                value={d.id || d.dataset_id}
                                className="bg-[#1a1a1a] text-white"
                            >
                                {d.name || d.dataset_name}
                            </option>
                        ))}
                    </select>
                    <Button variant="primary" onClick={loadDatasetContext} isLoading={isLoading}>
                        <RefreshCw size={16} />
                    </Button>
                </div>
            </div>

            {selectedId && (
                <div className="glass rounded-2xl border border-white/10 px-6 py-4 flex flex-wrap items-center gap-6 text-sm">
                    <div className={`flex items-center gap-2 font-bold ${step1Done ? 'text-emerald-400' : 'text-slate-500'}`}>
                        {step1Done ? <CheckCircle2 size={18} /> : <Database size={18} className="text-slate-500" />}
                        <span>Vue d'ensemble </span>
                    </div>
                    <ChevronRight className="text-slate-600 hidden sm:block" size={16} />
                    <div className={`flex items-center gap-2 font-bold ${isDataCardComplete ? 'text-emerald-400' : 'text-slate-300'}`}>
                        {isDataCardComplete ? <CheckCircle2 size={18} /> : <span className="w-[18px] text-center text-slate-500">2</span>}
                        <span>Décomposition du score</span>
                    </div>
                    <ChevronRight className="text-slate-600 hidden sm:block" size={16} />
                    <div className={`flex items-center gap-2 font-bold ${step3Done ? 'text-emerald-400' : 'text-slate-500'}`}>
                        {step3Done ? <CheckCircle2 size={18} /> : <span className="w-[18px] text-center text-slate-500">3</span>}
                        <span>Rapport réglementaire</span>
                    </div>
                    <span className="text-xs text-slate-500 ml-auto font-mono truncate max-w-[200px]" title={currentDatasetName}>
                        {currentDatasetName}
                    </span>
                </div>
            )}

            {error && (
                <div className="glass p-6 rounded-3xl border-red-500/20 bg-red-500/5 flex items-center gap-4 text-red-400">
                    <AlertTriangle size={24} />
                    <div>
                        <p className="text-sm font-bold">System Error during scan</p>
                        <p className="text-xs opacity-70">{error}</p>
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                {showDataCardWorkspace && (
                    <div className="lg:col-span-12 max-w-3xl mx-auto w-full space-y-6">
                        <div className="glass p-8 rounded-[2.5rem] border border-white/5 relative overflow-hidden">
                            <div className="absolute top-0 right-0 p-6 opacity-10"><Shield size={80} /></div>
                            <div className="space-y-6">
                                <DataCardForm data={dataCard} onChange={setDataCard} />
                                <Button
                                    className="w-full mt-2 py-4"
                                    onClick={handleRunAnalysis}
                                    isLoading={isComputing}
                                    disabled={!isDataCardComplete || isComputing}
                                    style={{
                                        background: !isDataCardComplete
                                            ? 'linear-gradient(to right, #444, #555)'
                                            : 'linear-gradient(to right, #ff3b30, #ff8e31)',
                                        borderRadius: '9999px',
                                        color: 'white',
                                        fontWeight: '900',
                                        textTransform: 'uppercase',
                                        letterSpacing: '1px',
                                        border: 'none',
                                        boxShadow: '0 4px 15px rgba(255, 59, 48, 0.3)',
                                        cursor: !isDataCardComplete ? 'not-allowed' : 'pointer',
                                        opacity: !isDataCardComplete ? 0.6 : 1,
                                    }}
                                >
                                    {isDataCardComplete
                                        ? 'Lancer le calcul ImmuneGuard Score'
                                        : 'Complétez la DataCard pour calculer'}
                                </Button>
                            </div>
                        </div>
                    </div>
                )}

                {!showDataCardWorkspace && !showScoreWorkspace && (
                    <div className="lg:col-span-4 space-y-6">
                        <div className="glass p-8 rounded-[2.5rem] border border-white/5 relative overflow-hidden">
                            <div className="absolute top-0 right-0 p-6 opacity-10"><Shield size={80} /></div>
                            <h3 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
                                <Zap size={18} className="text-brand-primary" />
                                Contexte technique (scan)
                            </h3>
                            <p className="text-xs text-slate-500 mb-6 leading-relaxed">
                                Sélectionnez un jeu de données et rechargez le scan pour afficher la DataCard.
                            </p>
                            {isLoading ? (
                                <div className="space-y-4 py-8">
                                    <div className="h-4 bg-white/5 rounded-full w-3/4 animate-pulse" />
                                    <div className="h-4 bg-white/5 rounded-full w-1/2 animate-pulse" />
                                    <div className="h-20 bg-white/5 rounded-3xl w-full animate-pulse" />
                                </div>
                            ) : (
                                <p className="text-sm text-slate-500 italic py-10 text-center">Aucun scan disponible.</p>
                            )}
                        </div>
                    </div>
                )}

                {!showDataCardWorkspace && !showScoreWorkspace && (
                    <div className="lg:col-span-8 space-y-6 text-center">
                        <div className="glass p-16 md:p-20 rounded-[3rem] border border-white/5 flex flex-col items-center justify-center text-center">
                            {isLoading ? (
                                <>
                                    <div className="w-16 h-16 border-4 border-brand-primary/20 border-t-brand-primary rounded-full animate-spin mx-auto mb-8" />
                                    <h3 className="text-2xl font-bold text-white mb-2">Scan du dataset</h3>
                                    <p className="text-slate-500 max-w-md leading-relaxed">Analyse des signaux en cours…</p>
                                </>
                            ) : (
                                <>
                                    <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center text-slate-600 mb-8">
                                        <Cpu size={40} />
                                    </div>
                                    <h3 className="text-2xl font-bold text-white mb-2">Sélectionnez un dataset</h3>
                                    <p className="text-slate-500 max-w-md leading-relaxed">
                                        Choisissez un jeu de données ingéré, puis rechargez le scan.
                                    </p>
                                </>
                            )}
                        </div>
                    </div>
                )}

                {showScoreWorkspace && (
                    <div className="lg:col-span-12 space-y-6 text-left">
                        <div className="flex gap-2 p-1.5 bg-white/5 rounded-2xl border border-white/5 w-fit">
                            {(['global', 'details', 'xai'] as const).map((tab) => (
                                <button
                                    key={tab}
                                    type="button"
                                    onClick={() => setView(tab)}
                                    className={`px-6 py-2 rounded-xl text-xs font-bold transition-all ${view === tab ? 'bg-brand-primary text-white shadow-lg shadow-brand-primary/20' : 'text-slate-400 hover:text-white'}`}
                                >
                                    {tab === 'global' ? "Vue d'ensemble" : tab === 'details' ? 'Décomposition du score' : 'Rapport réglementaire'}
                                </button>
                            ))}
                        </div>

                        <AnimatePresence mode="wait">
                            {isComputing ? (
                                <motion.div key="computing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="glass p-20 rounded-[3rem] flex flex-col items-center gap-6">
                                    <div className="relative">
                                        <div className="w-16 h-16 border-4 border-brand-primary/20 border-t-brand-primary rounded-full animate-spin" />
                                        <div className="absolute inset-0 flex items-center justify-center text-brand-primary"><Lock size={24} /></div>
                                    </div>
                                    <div className="text-center">
                                        <p className="text-xl font-bold text-white">Calcul du risque…</p>
                                        <p className="text-sm text-slate-500">B, A, I, C et explications XAI.</p>
                                    </div>
                                </motion.div>
                            ) : view === 'global' && riskResult ? (
                                <motion.div key="global" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
                                    <div className="grid grid-cols-1 xl:grid-cols-12 gap-8 items-start">
                                        <div className="xl:col-span-5 space-y-4">
                                            <div className="glass p-8 rounded-[2rem] border border-white/5">
                                                <div className="flex items-center gap-2 mb-4">
                                                    <LayoutList size={18} className="text-brand-primary" />
                                                    <h3 className="text-lg font-bold text-white tracking-tight">Profil du dataset</h3>
                                                </div>
                                                <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-3">
                                                    Signaux détectés
                                                </p>
                                                {datasetScanContext.detected.length > 0 ? (
                                                    <ul className="flex flex-wrap gap-2 mb-6 max-h-48 overflow-y-auto">
                                                        {datasetScanContext.detected.map((col) => (
                                                            <li
                                                                key={`${col.raw_column}-${col.signal}`}
                                                                className="text-xs font-semibold px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-slate-200"
                                                            >
                                                                {formatSignalLine(col)}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                ) : (
                                                    <p className="text-sm text-slate-500 italic mb-6">
                                                        Aucun signal détecté par le scanner.
                                                    </p>
                                                )}
                                                <dl className="space-y-3 text-sm border-t border-white/10 pt-4">
                                                    <div className="flex justify-between gap-4">
                                                        <dt className="text-slate-500 shrink-0">Secteur</dt>
                                                        <dd className="text-right text-white font-medium truncate">
                                                            {dataCard.secteur?.trim() || analysisProposal?.secteur || '—'}
                                                        </dd>
                                                    </div>
                                                    <div className="flex justify-between gap-4">
                                                        <dt className="text-slate-500 shrink-0">Finalité</dt>
                                                        <dd className="text-right text-white font-medium truncate">
                                                            {dataCard.finalite?.trim() || '—'}
                                                        </dd>
                                                    </div>
                                                    <div className="flex justify-between gap-4">
                                                        <dt className="text-slate-500 shrink-0">Signaux</dt>
                                                        <dd className="text-right text-white font-mono tabular-nums">
                                                            {datasetScanContext.detected.length} / {datasetScanContext.total} cols
                                                        </dd>
                                                    </div>
                                                    <div className="flex justify-between gap-4">
                                                        <dt className="text-slate-500 shrink-0">Lignes</dt>
                                                        <dd className="text-right text-white font-mono tabular-nums">
                                                            {selectedDatasetMeta?.rows != null ? Number(selectedDatasetMeta.rows).toLocaleString('fr-FR') : '—'}
                                                        </dd>
                                                    </div>
                                                </dl>
                                            </div>
                                            <div className="glass p-6 rounded-2xl border border-white/5 space-y-3 text-xs text-slate-400 leading-relaxed">
                                                <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Dimensions</p>
                                                <p><span className="text-sky-400 font-bold">B</span> · Risque intrinsèque — exposition structurelle (scanner).</p>
                                                <p><span className="text-violet-400 font-bold">A</span> · Exploitabilité adversariale — attaques simulées et contrôles.</p>
                                                <p><span className="text-amber-400 font-bold">I</span> · Incidents documentés — similarité avec cas AIID sectoriels.</p>
                                                <p><span className="text-emerald-400 font-bold">C</span> · Amplification contextuelle — secteur et finalité (DataCard).</p>
                                            </div>
                                        </div>

                                        <div className="xl:col-span-7 space-y-6">
                                            <div className="glass p-10 rounded-[3rem] border border-white/5 grid grid-cols-1 md:grid-cols-2 gap-10 items-center">
                                                <div className="flex flex-col items-center">
                                                    <Gauge value={Math.round(riskResult.R_final)} label="R Final" color={riskColor} />
                                                    <div className="mt-8 px-4 py-2 bg-white/5 rounded-full border border-white/10">
                                                        <span className="text-xs font-bold text-white uppercase tracking-widest">{riskResult.classification}</span>
                                                    </div>
                                                </div>
                                                <div className="space-y-5">
                                                    <h4 className="text-2xl font-bold text-white tracking-tight">Score de risque global</h4>
                                                    <div className="rounded-2xl bg-black/20 border border-white/10 p-4 space-y-2 font-mono text-xs text-slate-300 leading-relaxed">
                                                        <p>
                                                            <span className="text-slate-500">R_base</span> = 0,20×B + 0,60×A + 0,20×I ={' '}
                                                            <span className="text-white font-bold">{(riskResult.R_base * 100).toFixed(1)}%</span>
                                                        </p>
                                                        <p>
                                                            <span className="text-slate-500">R_final</span> = min(100 %, 100 × R_base × C) ={' '}
                                                            <span className="text-white font-bold">{Math.round(riskResult.R_final)} %</span>
                                                        </p>
                                                        <p className="text-slate-500">
                                                            C = 1 + 0,20 × (c₁ + c₂) = <span className="text-emerald-400 font-bold">{riskResult.C.toFixed(2)}</span>
                                                        </p>
                                                    </div>
                                                    <p className="text-slate-400 text-sm leading-relaxed">
                                                        Les pondérations B / A / I sont combinées en R_base, puis multipliées par le facteur C issu de la DataCard.
                                                    </p>
                                                    <div className="grid grid-cols-3 gap-2">
                                                        <StatBox icon={Shield} label="B ×0,20" value={pct(riskResult.B)} color="#38bdf8" />
                                                        <StatBox icon={Zap} label="A ×0,60" value={pct(riskResult.A)} color="#a78bfa" />
                                                        <StatBox icon={AlertTriangle} label="I ×0,20" value={pct(riskResult.I)} color="#f59e0b" />
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                                <StatBox icon={Info} label="c₁ (secteur)" value={riskResult.c1.toFixed(2)} color="#22c55e" />
                                                <StatBox icon={Info} label="c₂ (finalité)" value={riskResult.c2.toFixed(2)} color="#22c55e" />
                                                <StatBox icon={Info} label="C (facteur)" value={riskResult.C.toFixed(2)} color="#22c55e" />
                                            </div>
                                        </div>
                                    </div>
                                </motion.div>
                            ) : view === 'details' && riskResult ? (
                                <motion.div key="details" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
                                    <div className="glass p-6 rounded-3xl border border-white/5 space-y-3">
                                        <h3 className="text-lg font-bold text-white">Formule globale du risque</h3>
                                        <p className="font-mono text-sm text-slate-300 leading-relaxed">
                                            R_base = 0,20×B + 0,60×A + 0,20×I &nbsp;→&nbsp; R_final = min(100 %, 100 × R_base × C)
                                        </p>
                                        <p className="text-xs text-slate-500 leading-relaxed">
                                            B mesure le risque intrinsèque du fichier, A l&apos;exploitabilité par attaques, I la proximité
                                            avec des incidents réels. C amplifie selon le secteur et la finalité déclarés dans la DataCard.
                                        </p>
                                    </div>

                                    <section className="space-y-4">
                                        <div className="flex items-center gap-2">
                                            <Shield size={20} className="text-sky-400" />
                                            <h3 className="text-xl font-bold text-white">Score B — Risque intrinsèque</h3>
                                        </div>
                                        <p className="text-sm text-slate-400 font-mono">
                                            B = 0,40×b₁ + 0,25×b₂ + 0,20×b₃ + 0,15×b₄
                                        </p>
                                        <p className="text-xs text-slate-500 max-w-3xl">
                                            Calculé à partir du scanner uniquement (signaux, gravité normative, densité, qualité des données).
                                        </p>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            <DecompSubMetric
                                                subtitle="b₁"
                                                title="Exposition directe"
                                                explanation="Part des colonnes PII / sensibles non masquées parmi les colonnes à signal détecté."
                                                value={pct(riskResult.score_b_details.b1)}
                                            />
                                            <DecompSubMetric
                                                subtitle="b₂"
                                                title="Gravité réglementaire"
                                                explanation="Moyenne des probabilités normatives p(signal) sur les colonnes à signal."
                                                value={pct(riskResult.score_b_details.b2)}
                                            />
                                            <DecompSubMetric
                                                subtitle="b₃"
                                                title="Densité des signaux"
                                                explanation="Nombre de colonnes avec signal rapporté au nombre total de colonnes du dataset."
                                                value={pct(riskResult.score_b_details.b3)}
                                            />
                                            <DecompSubMetric
                                                subtitle="b₄"
                                                title="Qualité brute"
                                                explanation="Combinaison de valeurs manquantes, déséquilibre des modalités et variance nulle sur les colonnes numériques."
                                                value={pct(riskResult.score_b_details.b4)}
                                            />
                                        </div>
                                        <div className="glass p-5 rounded-2xl border border-sky-500/20 bg-sky-500/5">
                                            <p className="text-sm text-slate-300">
                                                <span className="font-bold text-sky-300">B agrégé</span>{' '}
                                                = 0,40×b₁ + 0,25×b₂ + 0,20×b₃ + 0,15×b₄ ={' '}
                                                <span className="font-black text-white tabular-nums">{pct(riskResult.B)}</span>
                                            </p>
                                        </div>
                                    </section>

                                    <section className="space-y-4">
                                        <div className="flex items-center gap-2">
                                            <AlertTriangle size={20} className="text-amber-400" />
                                            <h3 className="text-xl font-bold text-white">Score I — Incidents documentés</h3>
                                        </div>
                                        <p className="text-sm text-slate-400 font-mono">
                                            I = 0,60×similarité moyenne + 0,40×sévérité moyenne
                                        </p>
                                        <p className="text-xs text-slate-500 max-w-3xl">
                                            Similarité entre les signaux du dataset et des incidents AIID du secteur ; la sévérité reflète
                                            l&apos;ampleur documentée des cas retenus.
                                        </p>
                                        {(() => {
                                            const sid = riskResult.score_i_details as Record<string, unknown> | null | undefined;
                                            const secteurI = typeof sid?.secteur === 'string' ? sid.secteur : scoreIResult?.secteur;
                                            const nSig = typeof sid?.n_signaux === 'number' ? sid.n_signaux : null;
                                            const simM = typeof sid?.sim_moyen === 'number' ? sid.sim_moyen : null;
                                            const gravM = typeof sid?.grav_moyen === 'number' ? sid.grav_moyen : null;
                                            const domaines = Array.isArray(sid?.domaines_actives)
                                                ? (sid?.domaines_actives as string[])
                                                : scoreIResult?.domaines ?? [];
                                            const rawIncidents = Array.isArray(sid?.incidents) ? sid.incidents : null;
                                            return (
                                                <>
                                                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                                                        <div className="glass p-4 rounded-2xl border border-white/5">
                                                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Secteur (I)</p>
                                                            <p className="text-sm font-semibold text-white mt-2 break-words leading-snug">{secteurI || '—'}</p>
                                                        </div>
                                                        <div className="glass p-4 rounded-2xl border border-white/5">
                                                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Colonnes à signal</p>
                                                            <p className="text-2xl font-black text-amber-400/90 tabular-nums mt-2">{nSig != null ? String(nSig) : '—'}</p>
                                                        </div>
                                                        <div className="glass p-4 rounded-2xl border border-white/5">
                                                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Sim. moyenne</p>
                                                            <p className="text-2xl font-black text-amber-400/90 tabular-nums mt-2">{simM != null ? pct(simM) : '—'}</p>
                                                        </div>
                                                        <div className="glass p-4 rounded-2xl border border-white/5">
                                                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Sév. moyenne</p>
                                                            <p className="text-2xl font-black text-amber-400/90 tabular-nums mt-2">{gravM != null ? pct(gravM) : '—'}</p>
                                                        </div>
                                                    </div>
                                                    {domaines.length > 0 && (
                                                        <p className="text-xs text-slate-500">
                                                            Domaines MIT actifs :{' '}
                                                            <span className="text-slate-300">{domaines.join(', ')}</span>
                                                        </p>
                                                    )}
                                                    {rawIncidents && rawIncidents.length > 0 && (
                                                        <div className="glass p-6 rounded-3xl border border-white/5">
                                                            <h4 className="text-sm font-bold text-white mb-3">Incidents retenus pour le calcul</h4>
                                                            <ul className="space-y-3">
                                                                {(rawIncidents as Record<string, unknown>[]).map((inc, idx) => {
                                                                    const titre = String(inc.title ?? inc.titre ?? `Incident ${idx + 1}`);
                                                                    const grav = typeof inc.grav === 'number' ? inc.grav : 0;
                                                                    const sim = typeof inc.sim === 'number' ? inc.sim : 0;
                                                                    return (
                                                                        <li key={String(inc.incident_id ?? idx)} className="border-t border-white/5 pt-3 first:border-0 first:pt-0 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                                                                            <span className="text-sm font-semibold text-white">{titre}</span>
                                                                            <span className="text-xs text-amber-400/90 font-mono shrink-0">
                                                                                sim {sim.toFixed(2)} · sév {grav.toFixed(2)}
                                                                            </span>
                                                                        </li>
                                                                    );
                                                                })}
                                                            </ul>
                                                        </div>
                                                    )}
                                                </>
                                            );
                                        })()}
                                        <div className="glass p-5 rounded-2xl border border-amber-500/20 bg-amber-500/5">
                                            <p className="text-sm text-slate-300">
                                                <span className="font-bold text-amber-300">I agrégé</span> ={' '}
                                                <span className="font-black text-white tabular-nums">{pct(riskResult.I)}</span>
                                            </p>
                                        </div>
                                        {scoreIResult?.top3 && scoreIResult.top3.length > 0 && (
                                            <div className="glass p-6 rounded-3xl border border-white/5">
                                                <h4 className="text-lg font-bold text-white mb-2">Aperçu incidents (Score I service)</h4>
                                                <p className="text-xs text-slate-500 mb-4">Top 3 exposés par l&apos;API score-I.</p>
                                                {scoreIResult.top3.map((inc, idx) => (
                                                    <div key={idx} className="flex items-center justify-between py-3 border-t border-white/5 first:border-0">
                                                        <span className="text-sm font-bold text-white">{inc.titre}</span>
                                                        <span className="text-xs text-amber-400">sévérité {inc.grav.toFixed(2)}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </section>

                                    {scoreResult && (
                                        <section className="space-y-4">
                                            <div className="flex items-center gap-2">
                                                <Zap size={20} className="text-violet-400" />
                                                <h3 className="text-xl font-bold text-white">Score A — Exploitabilité adversariale</h3>
                                            </div>
                                            <p className="text-sm text-slate-400 font-mono">
                                                A = 0,60×Succ + 0,40×Vuln
                                            </p>
                                            <p className="text-xs text-slate-500 max-w-3xl">
                                                Succ agrège trois attaques (singling, linkage, inférence d&apos;attribut). Vuln agrège des
                                                contrôles structurels complémentaires sur le dataset.
                                            </p>
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                <DecompSubMetric
                                                    subtitle="Taux · Singling out"
                                                    title="Singling out"
                                                    explanation="Capacité à isoler un individu par combinaison de quasi-identifiants."
                                                    value={pct(scoreResult.taux_singling)}
                                                    color="#a78bfa"
                                                />
                                                <DecompSubMetric
                                                    subtitle="Taux · Linkage"
                                                    title="Linkage attack"
                                                    explanation="Risque de ré-identification par jonction avec une source externe simulée."
                                                    value={pct(scoreResult.taux_linkage)}
                                                    color="#818cf8"
                                                />
                                                <DecompSubMetric
                                                    subtitle="Taux · Attribute inference"
                                                    title="Inférence d&apos;attribut"
                                                    explanation="Fuite d&apos;information sur un attribut sensible via un modèle prédictif."
                                                    value={pct(scoreResult.taux_inference)}
                                                    color="#c084fc"
                                                />
                                            </div>
                                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                                <StatBox icon={Zap} label="Succ (attaques)" value={pct(scoreResult.Succ)} color="#a78bfa" />
                                                <StatBox icon={Shield} label="Vuln (contrôles)" value={pct(scoreResult.Vuln)} color="#818cf8" />
                                            </div>
                                            {scoreResult.xai?.attacks && scoreResult.xai.attacks.length > 0 && (
                                                <div className="space-y-2">
                                                    <h4 className="text-sm font-bold text-slate-300">Détail des attaques simulées</h4>
                                                    <div className="grid grid-cols-1 gap-3">
                                                        {scoreResult.xai.attacks.map((atk) => (
                                                            <div key={atk.attack_id} className="glass p-4 rounded-2xl border border-white/5">
                                                                <div className="flex justify-between gap-2 mb-1">
                                                                    <span className="text-sm font-bold text-white">{atk.attack}</span>
                                                                    <span className="text-xs font-mono text-violet-300">{pct(atk.score)}</span>
                                                                </div>
                                                                <p className="text-xs text-slate-400 leading-relaxed">{atk.explanation}</p>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                            {scoreResult.xai?.checks && scoreResult.xai.checks.length > 0 && (
                                                <div className="space-y-2">
                                                    <h4 className="text-sm font-bold text-slate-300">Vérifications structurelles (Vuln)</h4>
                                                    <div className="grid grid-cols-1 gap-3">
                                                        {scoreResult.xai.checks.map((chk) => (
                                                            <div key={chk.check_id} className="glass p-4 rounded-2xl border border-white/5">
                                                                <div className="flex justify-between gap-2 mb-1">
                                                                    <span className="text-sm font-bold text-white">{chk.label}</span>
                                                                    <span className={`text-[10px] font-black uppercase ${chk.detected ? 'text-amber-400' : 'text-slate-500'}`}>
                                                                        {chk.detected ? 'Détecté' : 'OK'}
                                                                    </span>
                                                                </div>
                                                                <p className="text-xs text-slate-500 mb-2">{chk.description}</p>
                                                                <p className="text-xs text-slate-400 leading-relaxed">{chk.explanation}</p>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                            <div className="glass p-5 rounded-2xl border border-violet-500/20 bg-violet-500/5">
                                                <p className="text-sm text-slate-300">
                                                    <span className="font-bold text-violet-300">A agrégé</span> = 0,60×Succ + 0,40×Vuln ={' '}
                                                    <span className="font-black text-white tabular-nums">{pct(scoreResult.A)}</span>
                                                </p>
                                            </div>
                                        </section>
                                    )}
                                </motion.div>
                            ) : view === 'xai' && riskResult ? (
                                <motion.div key="xai" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {riskResult.xai.map((item, idx) => (
                                        <div key={idx} className="glass p-6 rounded-3xl border border-white/5">
                                            <div className="flex items-center justify-between mb-4">
                                                <h5 className="font-bold text-white">{item.column || item.signal}</h5>
                                                <span className="text-xs font-black text-red-400">{item.severity}/5</span>
                                            </div>
                                            <p className="text-sm text-slate-400 leading-relaxed mb-4">{item.explanation}</p>
                                            <span className="text-[10px] font-black uppercase tracking-widest text-brand-primary">{item.legal_source}</span>
                                        </div>
                                    ))}
                                </motion.div>
                            ) : null}
                        </AnimatePresence>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ImmuneGuardPage;
