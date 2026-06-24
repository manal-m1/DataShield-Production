import React from 'react';
import { Database, Globe2, Shield, Users } from 'lucide-react';

export interface DataCardData {
    secteur: string;
    finalite: string;
    population: string;
    pays: string;
    origine: string;
    information: string;
}

export const DATACARD_OPTIONS = {
    secteurs: [
    'Ressources humaines / Emploi',
    'Santé humaine et Action sociale',
    "Activités financières et d'assurance",
    'Éducation',
    'Administration publique',
    "Forces de l'ordre",
    'Défense et sécurité nationale',
    'Transport et Entreposage',
    'Activités professionnelles, scientifiques et techniques',
    'Industrie manufacturière',
    'Information et Communication',
    'Activités de services administratifs et de soutien',
    'Activités immobilières',
    'Arts, Divertissement et Loisirs',
    'Commerce de gros et de détail',
    'Hébergement et Restauration',
    'Autres activités de services',
    ],
    finalites: [
    'Décision automatisée',
    'Profilage comportemental',
    'Reconnaissance faciale / identification biométrique',
    'Scoring / évaluation',
    'Vision par ordinateur - détection comportementale',
    'Classification',
    "Détection d'anomalie",
    'Vision par ordinateur - analyse de contenu',
    'Prédiction / prévision',
    'Aide à la décision',
    'Traitement du langage (NLP)',
    'Recommandation',
    'Entraînement de modèle',
    'Autre - à préciser :',
    ],
    populations: [
    'Salariés / employés',
    "Candidats à l'embauche",
    'Patients',
    'Clients',
    'Citoyens',
    'Étudiants',
    'Usagers de service public',
    'Justiciables',
    'Mineurs',
    'Personnes vulnérables',
    'Autre - à préciser :',
    ],
    pays: [
    'Maroc',
    'France',
    'Union européenne',
    'Tunisie',
    'Algérie',
    'Sénégal',
    'États-Unis',
    'International / Multizone',
    'Autre - à préciser :',
    ],
    origines: [
    'Collecte interne (first-party)',
    'Achat ou partenaire (third-party)',
    'Source publique / Open Data',
    'Données synthétiques générées',
    'Autre - à préciser :',
    ],
    informations: [
    'Oui - avant la collecte',
    'Oui - après la collecte',
    'Partiellement informées',
    'Non informées',
    'Sans objet (données anonymisées)',
    ],
};

interface DataCardFormProps {
    data: DataCardData;
    onChange: (data: DataCardData) => void;
}

interface SelectFieldProps {
    label: string;
    value: string;
    options: string[];
    placeholder: string;
    onChange: (value: string) => void;
}

const SelectField: React.FC<SelectFieldProps> = ({ label, value, options, placeholder, onChange }) => (
    <label className="block">
        <span className="block text-xs font-bold text-slate-400 mb-1">{label}</span>
        <select
            className="input-premium w-full text-sm"
            value={value}
            onChange={(event) => onChange(event.target.value)}
        >
            <option value="" className="bg-slate-900 text-white">{placeholder}</option>
            {options.map((option) => (
                <option key={option} value={option} className="bg-slate-900 text-white">
                    {option}
                </option>
            ))}
        </select>
    </label>
);

const DataCardForm: React.FC<DataCardFormProps> = ({ data, onChange }) => {
    const handleChange = (field: keyof DataCardData, value: string) => {
        onChange({ ...data, [field]: value });
    };

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4">
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                <Shield className="text-brand-primary" size={24} />
                DataCard — Contexte d&apos;usage
            </h3>

            <section className="glass p-6 rounded-3xl border border-white/5 space-y-4">
                <div className="flex items-center gap-2 text-brand-primary font-bold mb-4">
                    <Database size={18} />
                    <h4>Bloc 1 - Contexte d'usage</h4>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <SelectField
                        label="Secteur d'activite (ISIC Rev.4)"
                        value={data.secteur}
                        options={DATACARD_OPTIONS.secteurs}
                        placeholder="Selectionner un secteur..."
                        onChange={(value) => handleChange('secteur', value)}
                    />
                    <SelectField
                        label="Finalite du traitement IA"
                        value={data.finalite}
                        options={DATACARD_OPTIONS.finalites}
                        placeholder="Selectionner une finalite..."
                        onChange={(value) => handleChange('finalite', value)}
                    />
                </div>
            </section>

            <section className="glass p-6 rounded-3xl border border-white/5 space-y-4">
                <div className="flex items-center gap-2 text-indigo-400 font-bold mb-4">
                    <Users size={18} />
                    <h4>Bloc 2 - Population & perimetre</h4>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <SelectField
                        label="Personnes concernees"
                        value={data.population}
                        options={DATACARD_OPTIONS.populations}
                        placeholder="Selectionner une population..."
                        onChange={(value) => handleChange('population', value)}
                    />
                    <SelectField
                        label="Pays d'application"
                        value={data.pays}
                        options={DATACARD_OPTIONS.pays}
                        placeholder="Selectionner un pays..."
                        onChange={(value) => handleChange('pays', value)}
                    />
                </div>
            </section>

            <section className="glass p-6 rounded-3xl border border-white/5 space-y-4">
                <div className="flex items-center gap-2 text-amber-400 font-bold mb-4">
                    <Globe2 size={18} />
                    <h4>Bloc 3 - Origine & consentement</h4>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <SelectField
                        label="D'ou viennent les donnees ?"
                        value={data.origine}
                        options={DATACARD_OPTIONS.origines}
                        placeholder="Selectionner l'origine..."
                        onChange={(value) => handleChange('origine', value)}
                    />
                    <SelectField
                        label="Les personnes ont-elles ete informees de cet usage ?"
                        value={data.information}
                        options={DATACARD_OPTIONS.informations}
                        placeholder="Selectionner l'information..."
                        onChange={(value) => handleChange('information', value)}
                    />
                </div>
            </section>
        </div>
    );
};

export default DataCardForm;
