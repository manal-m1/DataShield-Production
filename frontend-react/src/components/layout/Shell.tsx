import React, { useState, useEffect } from 'react';
import Sidebar from './Sidebar';
import { motion, AnimatePresence } from 'framer-motion';
import apiClient from '../../services/api';
import AccessIndicator from '../AccessIndicator';
import { useAuthStore } from '../../store/authStore';

interface ShellProps {
    children: React.ReactNode;
}

const Shell = ({ children }: ShellProps) => {
    const user = useAuthStore((s) => s.user);
    const [nodeStatus, setNodeStatus] = useState({ online: 0, total: 6, status: 'Initializing' });

    const checkNodes = async () => {
        const services = [
            '/auth/health',
            '/cleaning/health',
            '/quality/health',
            '/presidio/health',
            '/taxonomie/health',
            '/ethimask/health'
        ];

        try {
            const results = await Promise.allSettled(services.map(s => apiClient.get(s)));
            const onlineCount = results.filter(r => r.status === 'fulfilled').length;
            setNodeStatus({
                online: onlineCount,
                total: services.length,
                status: onlineCount === services.length ? 'Operational' : onlineCount > 0 ? 'Degraded' : 'Critical'
            });
        } catch (err) {
            setNodeStatus(prev => ({ ...prev, status: 'Error' }));
        }
    };

    useEffect(() => {
        checkNodes();
        const interval = setInterval(checkNodes, 60000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="h-screen bg-bg-deep flex overflow-hidden selection:bg-brand-primary/30">
            <Sidebar />
            <main className="flex-1 p-8 overflow-y-auto max-h-screen relative">
                {/* Background Glow */}
                <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-brand-primary/10 blur-[120px] rounded-full pointer-events-none" />
                <div className="absolute bottom-[-10%] right-[-10%] w-[30%] h-[30%] bg-brand-accent/5 blur-[100px] rounded-full pointer-events-none" />

                <header className="flex justify-between items-center mb-12 relative z-10">
                    <div className="flex items-center gap-6">
                        <div className="flex flex-col">
                            <h1 className="text-[10px] font-black text-brand-primary uppercase tracking-[0.3em] mb-1 drop-shadow-[0_0_8px_rgba(100,100,255,0.5)]">
                                Quantum Workspace
                            </h1>
                            <div className="flex items-center gap-3">
                                <h2 className="text-2xl font-black text-white tracking-tighter">Main Command Deck</h2>
                                <div className={`px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-widest ${
                                    nodeStatus.status === 'Operational' ? 'bg-green-500/10 text-green-400 border border-green-500/20' :
                                    'bg-red-500/10 text-red-400 border border-red-500/20'
                                }`}>
                                    {nodeStatus.status}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-5">
                        <AccessIndicator />
                        
                        <div className="h-10 w-[1px] bg-white/10 mx-2" />

                        <div className="flex items-center gap-4">
                            <div className="flex flex-col text-right">
                                <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Active Nodes</span>
                                <span className="text-sm font-bold text-white tabular-nums">
                                    {nodeStatus.online} <span className="text-slate-600">/ {nodeStatus.total}</span>
                                </span>
                            </div>
                            <div className="w-12 h-12 rounded-2xl glass-premium p-[1px] flex items-center justify-center group cursor-pointer transition-all hover:scale-105 active:scale-95">
                                <div className="w-full h-full rounded-[15px] bg-bg-deep/50 flex items-center justify-center text-brand-primary font-black text-sm">
                                    {user?.username?.substring(0, 2).toUpperCase() || 'GV'}
                                </div>
                            </div>
                        </div>
                    </div>
                </header>

                <AnimatePresence mode="wait">
                    <motion.div
                        key={window.location.pathname}
                        initial={{ opacity: 0, filter: 'blur(10px)', y: 20 }}
                        animate={{ opacity: 1, filter: 'blur(0px)', y: 0 }}
                        exit={{ opacity: 0, filter: 'blur(10px)', y: -20 }}
                        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                        className="relative z-10"
                    >
                        {children}
                    </motion.div>
                </AnimatePresence>
            </main>
        </div>
    );
};

export default Shell;
