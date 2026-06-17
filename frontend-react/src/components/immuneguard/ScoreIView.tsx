import React from 'react';
import type { ScoreIResult } from '../../services/immuneguardService';

interface ScoreIViewProps {
    data: ScoreIResult | null;
}

const ScoreIView: React.FC<ScoreIViewProps> = ({ data }) => {
    if (!data) {
        return (
            <div className="glass p-16 rounded-[3rem] text-center border-dashed border-2 border-white/5">
                <div className="w-12 h-12 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-slate-400">Lancez le calcul pour afficher le Score I.</p>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <div className="glass p-8 rounded-3xl border border-white/5">
                <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">
                    Score d'Impact (Score I)
                </h3>
                <p className="text-5xl font-black text-cyan-400">{data.scoreI.toFixed(4)}</p>
                <p className="text-xs text-slate-500 mt-2">I = 0.60 x Similarite + 0.40 x Gravite</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="glass p-6 rounded-3xl border border-white/5">
                    <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">Secteur</h4>
                    <p className="text-white text-sm">{data.secteur}</p>
                </div>
                <div className="glass p-6 rounded-3xl border border-white/5">
                    <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">Domaines MIT detectes</h4>
                    <div className="flex flex-wrap gap-2">
                        {data.domaines.length === 0 && <span className="text-slate-500 text-sm">Aucun domaine detecte.</span>}
                        {data.domaines.map((d, i) => (
                            <span key={`${d}-${i}`} className="px-2 py-1 rounded text-[10px] font-bold bg-cyan-500/10 text-cyan-300">
                                {d}
                            </span>
                        ))}
                    </div>
                </div>
            </div>

            <div className="glass p-6 rounded-3xl border border-white/5">
                <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-4">Top 3 incidents similaires</h4>
                <div className="space-y-3">
                    {data.top3.map((incident) => (
                        <div key={incident.incident_id} className="bg-white/[0.03] rounded-2xl p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                            <div>
                                <p className="text-xs text-slate-500 font-mono">ID: {incident.incident_id}</p>
                                <p className="text-sm text-white font-semibold">{incident.titre || 'Incident non titre'}</p>
                            </div>
                            <div className="flex items-center gap-4 text-xs">
                                <span className="text-slate-300">Sim: {(incident.sim * 100).toFixed(0)}%</span>
                                <span className="text-slate-300">Grav: {incident.grav.toFixed(2)}</span>
                                <a
                                    href={`https://incidentdatabase.ai/cite/${incident.incident_id}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-cyan-400 hover:text-cyan-300 underline"
                                >
                                    Voir
                                </a>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {data.mapping_actions && data.mapping_actions.length > 0 && (
                <div className="glass p-6 rounded-3xl border border-white/5">
                    <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-4">Actions correctives Signaux</h4>
                    <div className="space-y-3">
                        {data.mapping_actions.map((item) => (
                            <div key={`${item.colonne}-${item.signal}`} className="bg-white/[0.03] rounded-2xl p-4">
                                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 mb-2">
                                    <p className="text-sm text-white font-semibold">{item.colonne}</p>
                                    <span className="w-fit px-2 py-1 rounded text-[10px] font-bold bg-orange-500/10 text-orange-300">
                                        {item.signal}
                                    </span>
                                </div>
                                <p className="text-xs text-slate-400 leading-relaxed">{item.action || 'Action corrective non renseignee.'}</p>
                                <p className="text-[10px] text-slate-600 mt-2">{item.source_reglementaire}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default ScoreIView;
