'use client';

import { AnimatePresence, motion } from 'motion/react';
import { Box, Cpu, Play, SlidersHorizontal, TerminalSquare, X, Zap } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

function useTelemetry(baseValue: number, variance: number, intervalMs = 1000) {
  const [val, setVal] = useState(baseValue);

  useEffect(() => {
    const int = setInterval(() => {
      setVal(baseValue + (Math.random() * variance * 2 - variance));
    }, intervalMs);
    return () => clearInterval(int);
  }, [baseValue, variance, intervalMs]);

  return val;
}

function useUptime() {
  const [seconds, setSeconds] = useState(151928);

  useEffect(() => {
    const timer = setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

export default function DashboardView({ onRouteChange }: { onRouteChange: (route: string) => void }) {
  const uptime = useUptime();
  const cpuLoad = useTelemetry(42.3, 5.5, 900);
  const memLoad = useTelemetry(62.3, 2.2, 1200);
  const networkDown = useTelemetry(45.1, 6, 1000);
  const networkUp = useTelemetry(14.5, 2.4, 1300);
  const [pendingTerminate, setPendingTerminate] = useState<string | null>(null);
  const [missions, setMissions] = useState([
    { id: 'MSN-092', name: 'Auto-Navigation Alpha', status: 'Active', time: '02:45:10' },
    { id: 'MSN-093', name: 'Mapping Payload', status: 'Deploying', time: '00:01:23' },
    { id: 'MSN-091', name: 'Sensor Calibration', status: 'Completed', time: '01:10:00' },
  ]);

  const metrics = useMemo(
    () => [
      { title: 'Compute Core', value: cpuLoad.toFixed(1), unit: '%', accent: 'cyan', width: '45%' },
      { title: 'Memory Alloc', value: memLoad.toFixed(1), unit: 'GB', accent: 'amber', width: '48%' },
      { title: 'Network Down', value: networkDown.toFixed(1), unit: 'MB', accent: 'cyan', width: '45%' },
      { title: 'Network Up', value: networkUp.toFixed(1), unit: 'MB', accent: 'slate', width: '28%' },
    ],
    [cpuLoad, memLoad, networkDown, networkUp]
  );

  const actions = [
    { label: 'Studio IDE', icon: Zap, route: 'ide', accent: 'cyan' },
    { label: 'ROS Console', icon: SlidersHorizontal, route: 'ros', accent: 'amber' },
    { label: 'Simulation', icon: Box, route: 'simulation', accent: 'black' },
    { label: 'Physics AI', icon: Cpu, route: 'physics_ai', accent: 'black' },
    { label: 'New Deployment', icon: Play, route: 'ide', accent: 'primary' },
  ];

  const confirmTerminate = () => {
    if (!pendingTerminate) return;
    setMissions((items) => items.map((mission) => mission.id === pendingTerminate ? { ...mission, status: 'Terminated' } : mission));
    setPendingTerminate(null);
  };

  return (
    <div className="h-full overflow-y-auto bg-[#f5feff] text-[#05070a] dark:bg-[#0a0f1a] dark:text-white">
      <div className="min-h-full bg-[linear-gradient(rgba(148,163,184,0.22)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.22)_1px,transparent_1px)] bg-[length:25px_25px] px-8 pb-8 pt-10 dark:bg-[linear-gradient(rgba(0,229,255,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(0,229,255,0.05)_1px,transparent_1px)]">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-[1780px]">
          <section className="relative border-b border-[#d8dee8] pb-10 text-center dark:border-white/10">
            <div className="absolute left-[52%] top-3 h-1 w-1 bg-[#aaf8ff]" />
            <div className="absolute right-[14%] top-12 h-1 w-1 bg-[#78eefa]" />
            <h1 className="text-[30px] font-light tracking-[-0.04em]">
              Good Evening, <span className="font-black">Commander.</span>
            </h1>
            <p className="mt-1 text-sm text-[#64748b] dark:text-[#94a3b8]">
              All robotics infrastructure operating normally across <span className="font-semibold text-[#00ddeb]">Cluster 02.</span>
            </p>
            <div className="mt-6 flex items-center justify-center gap-4 font-mono text-xs uppercase tracking-[0.16em] text-[#64748b] dark:text-[#94a3b8]">
              <span>Uptime</span>
              <span className="rounded-[5px] border border-[#d8dee8] bg-white px-3 py-2 text-lg font-black tracking-[0.1em] text-black dark:border-white/10 dark:bg-[#111827] dark:text-white">{uptime}</span>
            </div>
          </section>

          <section className="mt-8 grid gap-5 xl:grid-cols-4">
            {metrics.map((metric) => (
              <MetricCard key={metric.title} {...metric} />
            ))}
          </section>

          <section className="mt-8 grid gap-5 xl:grid-cols-5">
            {actions.map((action) => {
              const Icon = action.icon;
              return (
                <button
                  key={action.label}
                  type="button"
                  onClick={() => onRouteChange(action.route)}
                  className={`group flex h-[68px] items-center gap-5 rounded-[5px] border bg-white/80 px-6 text-left font-mono text-sm uppercase tracking-[0.13em] transition-colors ${
                    action.accent === 'primary'
                      ? 'border-[#00ddeb] bg-[#effcff] font-black hover:bg-[#defbff] dark:bg-[#00ddeb]/10 dark:hover:bg-[#00ddeb]/15'
                      : 'border-[#d8dee8] hover:border-[#00ddeb] hover:bg-[#f8feff] dark:border-white/10 dark:bg-[#111827]/90 dark:hover:border-[#00ddeb] dark:hover:bg-[#1f2937]'
                  }`}
                >
                  <Icon className={`h-6 w-6 ${action.accent === 'amber' ? 'text-[#ffb21a]' : action.accent === 'cyan' || action.accent === 'primary' ? 'text-[#00ddeb]' : 'text-black dark:text-white'}`} />
                  <span>{action.label}</span>
                </button>
              );
            })}
          </section>

          <section className="mt-8 border border-[#d8dee8] bg-white/70 dark:border-white/10 dark:bg-[#111827]/80">
            <div className="flex h-[68px] items-center justify-between border-b border-[#d8dee8] px-5 dark:border-white/10">
              <h2 className="flex items-center gap-3 font-mono text-sm font-black uppercase tracking-[0.12em]">
                <span className="h-2 w-2 rounded-full bg-[#31ddec]" />
                Active Missions
              </h2>
              <span className="rounded-[4px] border border-[#ffc960] bg-[#fff9ec] px-3 py-1 font-mono text-xs uppercase text-[#ffae00]">
                1 Deploying
              </span>
            </div>

            <div className="space-y-3 p-5">
              {missions.map((mission) => (
                <div key={mission.id} className="grid min-h-[61px] grid-cols-[74px_1fr_120px_100px_34px] items-center gap-4 border border-[#d8dee8] bg-white px-4 font-mono text-sm dark:border-white/10 dark:bg-[#0a0f1a]">
                  <span className="text-xs text-[#64748b] dark:text-[#94a3b8]">{mission.id}</span>
                  <span className="truncate text-black dark:text-white">{mission.name}</span>
                  <span className={`text-right text-xs uppercase tracking-[0.18em] ${mission.status === 'Active' ? 'text-[#00ddeb]' : mission.status === 'Deploying' ? 'text-[#ffae00]' : 'text-[#64748b]'}`}>{mission.status}</span>
                  <span className="text-right text-xs text-[#64748b] dark:text-[#94a3b8]">{mission.time}</span>
                  {!['Completed', 'Terminated'].includes(mission.status) ? (
                    <button title="Terminate session" onClick={() => setPendingTerminate(mission.id)} className="flex h-8 w-8 items-center justify-center rounded-[5px] border border-[#d8dee8] text-[#64748b] hover:border-red-300 hover:text-red-500 dark:border-white/10 dark:text-[#94a3b8]">
                      <X className="h-4 w-4" />
                    </button>
                  ) : (
                    <span />
                  )}
                </div>
              ))}
            </div>
          </section>
        </motion.div>
      </div>

      <AnimatePresence>
        {pendingTerminate && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
            <motion.div initial={{ scale: 0.96, y: 10 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.96, y: 10 }} className="w-full max-w-md rounded-[5px] border border-[#d8dee8] bg-white p-5 shadow-2xl dark:border-white/10 dark:bg-[#111827]">
              <h3 className="font-mono text-lg font-black uppercase tracking-[0.12em]">Terminate Session?</h3>
              <p className="mt-2 text-sm text-[#64748b] dark:text-[#94a3b8]">This will stop the selected mission session. This action requires confirmation.</p>
              <div className="mt-5 flex justify-end gap-2">
                <button onClick={() => setPendingTerminate(null)} className="rounded-[5px] border border-[#d8dee8] px-4 py-2 text-sm dark:border-white/10">Cancel</button>
                <button onClick={confirmTerminate} className="rounded-[5px] border border-red-500 bg-red-500 px-4 py-2 text-sm font-semibold text-white">Terminate</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function MetricCard({ title, value, unit, accent, width }: { title: string; value: string; unit: string; accent: string; width: string }) {
  const accentClass = accent === 'amber' ? 'bg-[#ffb21a]' : accent === 'slate' ? 'bg-[#c7c7c7]' : 'bg-[#00ddeb]';

  return (
    <div className="relative min-h-[130px] border border-[#d8dee8] bg-white/75 p-5 dark:border-white/10 dark:bg-[#111827]/90">
      <div className={`absolute right-0 top-0 h-1 w-[120px] ${accentClass}`} />
      <div className="font-mono text-xs font-black uppercase tracking-[0.18em] text-[#64748b] dark:text-[#94a3b8]">{title}</div>
      <div className="mt-5 flex items-end gap-2 font-mono">
        <span className="text-[40px] font-black leading-none tracking-[0.08em] text-black dark:text-white">{value}</span>
        <span className="pb-1 text-base font-black text-[#64748b] dark:text-[#94a3b8]">{unit}</span>
      </div>
      <div className="mt-5 h-1 bg-white">
        <div className={`h-full ${accentClass}`} style={{ width }} />
      </div>
    </div>
  );
}
