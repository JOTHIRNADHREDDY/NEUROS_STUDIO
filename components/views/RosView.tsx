'use client';
import { motion, AnimatePresence } from 'motion/react';
import { Play, Square, RefreshCcw, Activity, Terminal, Cpu, Check, AlertTriangle, X, Radio, Server, DatabaseZap, Bot, Send } from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import { useTerminalTheme } from '@/components/TerminalThemeContext';
import { XtermTerminal, type TerminalConnectionState, type XtermTerminalHandle } from '@/components/terminal/XtermTerminal';
import PanelControls, { PanelDefinition } from '@/components/layout/PanelControls';

const rosPanels: PanelDefinition[] = [
  { id: 'telemetry', label: 'Telemetry' },
  { id: 'terminal', label: 'ROS Terminal', shortLabel: 'Terminal' },
  { id: 'graph', label: 'Node Graph', shortLabel: 'Graph' },
  { id: 'ai', label: 'AI Copilot', shortLabel: 'AI' },
  { id: 'logs', label: 'System Logs', shortLabel: 'Logs' },
];

const defaultRosPanelVisibility = {
  telemetry: true,
  terminal: true,
  graph: true,
  ai: true,
  logs: true,
};

function getSavedRosLayout() {
  if (typeof window === 'undefined') {
    return {};
  }

  const saved = window.localStorage.getItem('neuros-ros-panel-layout-v1');
  if (!saved) {
    return {};
  }

  try {
    return JSON.parse(saved) as {
      visibility?: Record<string, boolean>;
      telemetryWidth?: number;
      rightWidth?: number;
      logsHeight?: number;
      graphHeight?: number;
    };
  } catch {
    window.localStorage.removeItem('neuros-ros-panel-layout-v1');
    return {};
  }
}

export default function RosView({ onClose }: { onClose?: () => void }) {
  const { theme } = useTerminalTheme();
  const [coreStatus, setCoreStatus] = useState<'stopped' | 'launching' | 'running'>('stopped');
  const [packages, setPackages] = useState([
      { name: 'nav_stack', isRunning: false, freq: '0 Hz', cpu: '0%' },
      { name: 'motor_bridge', isRunning: false, freq: '0 Hz', cpu: '0%' },
      { name: 'sensor_fusion', isRunning: false, freq: '0 Hz', cpu: '0%' },
      { name: 'camera_driver', isRunning: false, freq: '0 Hz', cpu: '0%' },
      { name: 'slam_toolbox', isRunning: false, freq: '0 Hz', cpu: '0%' }
  ]);
  const [termLogs, setTermLogs] = useState<string[]>(['root@neuros-master:~/ws# ']);
  const [sysLogs, setSysLogs] = useState<string[]>([
      "System initialized. Waiting for ROS core."
  ]);
  const [aiMessage, setAiMessage] = useState<string>("Standing by. Awaiting telemetry stream.");
  const [isAiTuning, setIsAiTuning] = useState(false);
  const [aiLogs, setAiLogs] = useState<{type: 'AI' | 'USER', text: string}[]>([]);
  const [aiChatInput, setAiChatInput] = useState('');
  const [isAiChatLoading, setIsAiChatLoading] = useState(false);
  const [terminalSessions, setTerminalSessions] = useState([{ id: 'terminal-1', label: 'Terminal 1', wsUrl: 'ws://localhost:8000/api/ros/pty' }]);
  const [activeTerminalId, setActiveTerminalId] = useState('terminal-1');
  const [terminalStatuses, setTerminalStatuses] = useState<Record<string, TerminalConnectionState>>({ 'terminal-1': 'connecting' });
  const terminalRefs = useRef<Record<string, XtermTerminalHandle | null>>({});
  const [terminalMenu, setTerminalMenu] = useState<{ x: number; y: number } | null>(null);
  const [panelVisibility, setPanelVisibility] = useState<Record<string, boolean>>(() => ({
    ...defaultRosPanelVisibility,
    ...(getSavedRosLayout().visibility ?? {}),
  }));
  const [telemetryWidth, setTelemetryWidth] = useState(() => getSavedRosLayout().telemetryWidth ?? 288);
  const [rightWidth, setRightWidth] = useState(() => getSavedRosLayout().rightWidth ?? 320);
  const [logsHeight, setLogsHeight] = useState(() => getSavedRosLayout().logsHeight ?? 256);
  const [graphHeight, setGraphHeight] = useState(() => getSavedRosLayout().graphHeight ?? 260);
  
  const termRef = useRef<HTMLDivElement>(null);
  const sysRef = useRef<HTMLDivElement>(null);
  const aiChatRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
     if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight;
     if (sysRef.current) sysRef.current.scrollTop = sysRef.current.scrollHeight;
     if (aiChatRef.current) aiChatRef.current.scrollTop = aiChatRef.current.scrollHeight;
  }, [termLogs, sysLogs, aiLogs]);

  useEffect(() => {
    window.localStorage.setItem('neuros-ros-panel-layout-v1', JSON.stringify({
      visibility: panelVisibility,
      telemetryWidth,
      rightWidth,
      logsHeight,
      graphHeight,
    }));
  }, [panelVisibility, telemetryWidth, rightWidth, logsHeight, graphHeight]);

  const togglePanel = (panelId: string) => {
    setPanelVisibility(prev => ({ ...prev, [panelId]: !(prev[panelId] ?? true) }));
  };

  const startResize = (
    axis: 'x' | 'y',
    current: number,
    setter: (value: number) => void,
    min: number,
    max: number,
    invert = false
  ) => (event: React.MouseEvent) => {
    event.preventDefault();
    const start = axis === 'x' ? event.clientX : event.clientY;
    const handleMove = (moveEvent: MouseEvent) => {
      const delta = (axis === 'x' ? moveEvent.clientX : moveEvent.clientY) - start;
      setter(Math.min(max, Math.max(min, current + (invert ? -delta : delta))));
    };
    const handleUp = () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
  };

  const addTermLog = (msg: string) => setTermLogs(l => [...l, msg]);
  const addSysLog = (msg: string) => setSysLogs(l => [...l, msg]);

  const handleLaunchCore = () => {
      if (coreStatus !== 'stopped') return;
      setCoreStatus('launching');
      setTermLogs([]);
      
      const sequence = [
          { t: 0, m: () => addTermLog(`root@neuros-master:~/ws# source devel/setup.bash`) },
          { t: 400, m: () => addTermLog(`root@neuros-master:~/ws# roslaunch nav_stack bringup.launch`) },
          { t: 800, m: () => addTermLog(`... logging to /root/.ros/log/run_id.log`) },
          { t: 1200, m: () => addTermLog(`[SYSTEM] Validating hardware endpoints... OK.`) },
          { t: 1600, m: () => addTermLog(`started roslaunch server http://192.168.1.100:45931/`) },
          { t: 2000, m: () => {
              addTermLog(`SUMMARY\n========\nPARAMETERS\n * /rosdistro: noetic\nNODES\n  / motor_bridge\n  / nav_stack`);
              setCoreStatus('running');
              setAiMessage("Graph analysis indicates /cmd_vel topic congestion. The navigation planner is publishing at 50Hz, but the motor bridge is consuming at 20Hz. Latency spike detected.");
              
              setPackages(p => p.map(pkg => ['nav_stack', 'motor_bridge', 'sensor_fusion'].includes(pkg.name) ? { 
                  ...pkg, 
                  isRunning: true,
                  freq: pkg.name === 'nav_stack' ? '50 Hz' : '20 Hz',
                  cpu: Math.floor(Math.random() * 20 + 5) + '%'
              } : pkg));
              addSysLog('[INFO] [1023.41] Published TF map -> odom');
              addSysLog('[INFO] [1023.42] Motor bridge initialized properly.');
              setTimeout(() => addSysLog('[WARN] [1024.11] IMU calibration drifting. Compensating (+0.02 rad).'), 1000);
          } }
      ];

      sequence.forEach(step => setTimeout(step.m, step.t));
  };

  const handleStopAll = () => {
      if (coreStatus === 'stopped') return;
      setCoreStatus('stopped');
      addTermLog(`^C\n[nav_stack-2] killing on exit\n[motor_bridge-1] killing on exit\nshutting down processing monitor...\n... shutting down processing monitor complete\ndone`);
      addSysLog('[INFO] ROS master terminated.');
      setPackages(p => p.map(pkg => ({ ...pkg, isRunning: false, freq: '0 Hz', cpu: '0%' })));
      setAiMessage("System offline. Telemetry paused.");
  };
  
  const handleCatkinBuild = () => {
      if (coreStatus !== 'stopped') {
          addSysLog("[ERROR] Cannot build while ROS master is running.");
          return;
      }
      setTermLogs([]);
      addTermLog("root@neuros-master:~/ws# catkin build");
      addTermLog("-------------------------------------------------------");
      addTermLog("Profile:                     default");
      addTermLog("Extending:             [env] /opt/ros/noetic");
      addTermLog("Workspace:                   /root/ws");
      addTermLog("-------------------------------------------------------");
      
      setTimeout(() => addTermLog("[build] Starting  >>> nav_stack"), 500);
      setTimeout(() => addTermLog("[build] Finished  <<< nav_stack                [ 1.2 seconds ]"), 1500);
      setTimeout(() => addTermLog("[build] Starting  >>> motor_bridge"), 1600);
      setTimeout(() => addTermLog("[build] Finished  <<< motor_bridge             [ 0.8 seconds ]"), 2400);
      setTimeout(() => addTermLog("[build] Summary: All 5 packages succeeded!"), 2600);
  };

  const handleAutoTune = () => {
      setIsAiTuning(true);
      setTimeout(() => {
          setIsAiTuning(false);
          setAiMessage("Parameters optimized. Navigation planner rate matched to motor bridge capacity (20Hz). Topic congestion resolved.");
          addSysLog('[INFO] [1050.00] AI applied patch: param set /nav_stack/publish_rate 20.0');
          addTermLog('root@neuros-master:~/ws# rosparam set /nav_stack/publish_rate 20.0');
          setPackages(p => p.map(pkg => pkg.name === 'nav_stack' ? { ...pkg, freq: '20 Hz' } : pkg));
      }, 2000);
  };

  const sendAiChat = async (prompt: string) => {
    const trimmed = prompt.trim();
    if (!trimmed || isAiChatLoading) return;
    setAiLogs(l => [...l, { type: 'USER', text: trimmed }]);
    setAiChatInput('');
    setIsAiChatLoading(true);
    try {
      const response = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: trimmed,
          context: `ROS Operations Environment.\nCore Status: ${coreStatus}\nRunning Packages: ${packages.filter(p => p.isRunning).map(p => `${p.name} (${p.freq}, ${p.cpu})`).join(', ') || 'none'}\nRecent Logs:\n${sysLogs.slice(-5).join('\n')}`
        }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => null);
        throw new Error(err?.error ?? 'AI request failed');
      }
      const data = await response.json();
      const reply = typeof data.reply === 'string' && data.reply.trim() ? data.reply.trim() : 'The model returned an empty response.';
      setAiLogs(l => [...l, { type: 'AI', text: reply }]);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown AI request error';
      setAiLogs(l => [...l, { type: 'AI', text: `AI request failed: ${message}` }]);
    } finally {
      setIsAiChatLoading(false);
    }
  };

  const handleAiChatSubmit = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') void sendAiChat(aiChatInput);
  };

  const downloadRosLogs = () => {
    const blob = new Blob([`ROS Terminal\n${termLogs.join('\n')}\n\nSystem Logs\n${sysLogs.join('\n')}`], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `ros-console-logs-${Date.now()}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const activeTerminal = terminalSessions.find(session => session.id === activeTerminalId) ?? terminalSessions[0];
  const activeTerminalStatus = terminalStatuses[activeTerminalId] ?? 'connecting';
  const getActiveTerminalHandle = () => terminalRefs.current[activeTerminalId] ?? null;

  const addTerminal = () => {
    const nextIndex = terminalSessions.length + 1;
    const id = `terminal-${nextIndex}`;
    setTerminalSessions(prev => [...prev, { id, label: `Terminal ${nextIndex}`, wsUrl: 'ws://localhost:8000/api/ros/pty' }]);
    setTerminalStatuses(prev => ({ ...prev, [id]: 'connecting' }));
    setActiveTerminalId(id);
  };

  const closeTerminal = (terminalId: string) => {
    if (terminalSessions.length === 1) {
      return;
    }

    terminalRefs.current[terminalId]?.kill();
    setTerminalSessions(prev => prev.filter(session => session.id !== terminalId));
    setTerminalStatuses(prev => {
      const next = { ...prev };
      delete next[terminalId];
      return next;
    });

    if (activeTerminalId === terminalId) {
      const nextTerminal = terminalSessions.find(session => session.id !== terminalId);
      if (nextTerminal) {
        setActiveTerminalId(nextTerminal.id);
      }
    }
  };

  return (
    <div className="h-full min-h-0 flex flex-col z-10 relative font-sans overflow-hidden bg-tech-grid bg-[#0A0D14] text-slate-300">
      
      {/* Decorative ambient glows */}
      <div className="absolute top-[-100px] left-[-100px] w-[300px] h-[300px] bg-[#00E5FF] rounded-full blur-[120px] opacity-[0.03] dark:opacity-10 pointer-events-none" />
      <div className="absolute bottom-[-100px] right-[-100px] w-[400px] h-[400px] bg-purple-600 rounded-full blur-[150px] opacity-[0.03] dark:opacity-10 pointer-events-none" />

      {/* Header Controls */}
      <div className="h-14 bg-[#111827] backdrop-blur-md border-b border-[rgba(0,255,255,0.08)] flex items-center justify-between px-6 flex-shrink-0 relative z-20">
        <div className="flex items-center gap-4">
          <button 
             onClick={handleLaunchCore}
             disabled={coreStatus !== 'stopped'}
             className={`flex items-center gap-2 px-4 py-1.5 transition-all text-xs uppercase font-bold tracking-widest font-mono rounded-md border ${
                 coreStatus === 'stopped' 
                 ? 'bg-sky-50 dark:bg-[#00E5FF]/10 border-sky-300 dark:border-[#00E5FF]/50 text-sky-600 dark:text-[#00E5FF] hover:bg-sky-100 dark:hover:bg-[#00E5FF]/20 hover:shadow-sm dark:hover:shadow-[0_0_15px_rgba(0,242,255,0.4)]' 
                 : 'bg-[#161B22] border-[rgba(0,255,255,0.08)] text-slate-300 cursor-not-allowed'
             }`}
          >
             <Play className="w-3.5 h-3.5" />
             {coreStatus === 'launching' ? 'LAUNCHING...' : 'LAUNCH CORE'}
          </button>
          
          <button 
             onClick={handleStopAll}
             disabled={coreStatus === 'stopped'}
             className={`flex items-center gap-2 px-4 py-1.5 transition-all text-xs uppercase font-bold tracking-widest font-mono rounded-md border ${
                 coreStatus !== 'stopped' 
                 ? 'bg-red-50 dark:bg-red-500/10 border-red-300 dark:border-red-500/50 text-red-600 dark:text-red-500 hover:bg-red-100 dark:hover:bg-red-500/20 hover:shadow-sm dark:hover:shadow-[0_0_15px_rgba(239,68,68,0.4)]' 
                 : 'bg-[#161B22] border-[rgba(0,255,255,0.08)] text-slate-300 cursor-not-allowed'
             }`}
          >
             <Square className="w-3.5 h-3.5" />
             STOP ALL
          </button>
          
          <button 
             onClick={handleCatkinBuild}
             disabled={coreStatus !== 'stopped'}
             className={`flex items-center gap-2 px-4 py-1.5 transition-all text-xs uppercase font-bold tracking-widest font-mono rounded-md border ${
                 coreStatus === 'stopped' 
                 ? 'bg-[#111827] dark:bg-[#111827] border-[rgba(0,255,255,0.08)] text-slate-300 hover:bg-[#161B22] dark:hover:bg-[#161B22] hover:border-slate-400 dark:hover:border-white/40 hover:text-white dark:hover:text-white' 
                 : 'bg-[#161B22] border-[rgba(0,255,255,0.08)] text-slate-300 cursor-not-allowed'
             }`}
          >
             <RefreshCcw className="w-3.5 h-3.5" />
             CATKIN BUILD
          </button>
        </div>

        <div className="flex items-center gap-6 text-[10px] font-mono tracking-widest uppercase text-white/50 dark:text-white/70">
          <div className="flex items-center gap-2 bg-[#161B22] border border-[rgba(0,255,255,0.08)] px-3 py-1 rounded-full">
            <span className="text-slate-300">DISTRO:</span> 
            <span className="text-slate-300 font-bold flex items-center gap-1">
                NOETIC <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse ml-1"/>
            </span>
          </div>
          <div className="flex items-center gap-2 bg-[#161B22] border border-[rgba(0,255,255,0.08)] px-3 py-1 rounded-full">
            <span className="text-slate-300">WORKSPACE:</span> 
            <span className="text-sky-600 dark:text-[#00E5FF] font-bold">/neuros/ws</span>
          </div>
          {onClose && (
            <button onClick={onClose} className="ml-2 text-slate-300 hover:text-white dark:hover:text-white hover:bg-slate-100 dark:hover:bg-[#111827]/10 transition-colors p-1.5 rounded-md border border-transparent hover:border-slate-200 dark:hover:border-white/20">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      <div className="border-b border-[rgba(0,255,255,0.08)] bg-[#111827] px-4 py-2 relative z-20">
        <PanelControls panels={rosPanels} visible={panelVisibility} onToggle={togglePanel} />
      </div>

      <div className="flex-1 flex overflow-hidden p-4 gap-4 relative z-20">
        
        {/* Left - Packages Telemetry */}
        {panelVisibility.telemetry && <div className="bg-[#111827] backdrop-blur-md border border-[rgba(0,255,255,0.08)] rounded-xl flex flex-col shrink-0 overflow-hidden shadow-md dark:shadow-xl" style={{ width: telemetryWidth }}>
          <div className="px-5 py-3 border-b border-[rgba(0,255,255,0.08)] bg-[#161B22] dark:bg-[#161B22] text-[11px] font-bold font-mono text-slate-300 tracking-widest flex items-center justify-between">
            <div className="flex items-center gap-2" data-tooltip="Real-time robot data and diagnostics.">
                <Server className="w-3.5 h-3.5 text-sky-500 dark:text-[#00E5FF]" />
                TELEMETRY
            </div>
            {coreStatus === 'running' && <div className="w-2 h-2 rounded-full bg-sky-500 dark:bg-[#00E5FF] animate-tech-pulse" />}
          </div>
          <div className="p-3 space-y-2 overflow-y-auto">
            <AnimatePresence>
                {packages.map(pkg => (
                    <motion.div layout key={pkg.name}>
                        <PackageNode pkg={pkg} />
                    </motion.div>
                ))}
              </AnimatePresence>
          </div>
        </div>}
        {panelVisibility.telemetry && <div className="resizer-x -mx-2" onMouseDown={startResize('x', telemetryWidth, setTelemetryWidth, 220, 420)} />}

        {/* Center - CLI & Logs */}
        <div className="flex-1 flex flex-col gap-4 min-w-0">
          {/* ROS Terminal */}
          {panelVisibility.terminal && <div
            className="flex-1 bg-[#111827] border border-[rgba(0,255,255,0.08)] rounded-xl flex flex-col min-h-[250px] shadow-md dark:shadow-xl overflow-hidden relative group"
            onContextMenu={(event) => {
              event.preventDefault();
              setTerminalMenu({ x: event.clientX, y: event.clientY });
            }}
          >
             <div className="absolute inset-0 pointer-events-none overflow-hidden rounded-xl opacity-[0.04]">
                <div className="w-full h-[10%] bg-gradient-to-b from-transparent via-[#00E5FF] to-transparent animate-scanline" />
             </div>

             <div className="px-4 py-2.5 bg-[#161B22] border-b border-[rgba(0,255,255,0.08)] flex flex-col gap-2 shrink-0 relative z-10">
               <div className="flex items-center justify-between gap-3">
                 <div className="flex items-center gap-2 text-[11px] font-bold font-mono tracking-widest text-white/70 uppercase">
                   <Terminal className="w-3.5 h-3.5 text-[#00E5FF]" />
                   <span data-tooltip="Run ROS commands in a live workspace terminal.">ROS TERMINAL</span>
                   <span className={`ml-2 px-2 py-0.5 rounded-full border text-[9px] tracking-[0.25em] uppercase inline-flex items-center gap-1.5 ${activeTerminalStatus === 'connected' ? 'text-emerald-300 border-emerald-500/20 bg-emerald-500/10' : activeTerminalStatus === 'reconnecting' ? 'text-orange-300 border-orange-500/20 bg-orange-500/10' : activeTerminalStatus === 'connecting' ? 'text-yellow-300 border-yellow-500/20 bg-yellow-500/10' : 'text-red-300 border-red-500/20 bg-red-500/10'}`}>
                     <span className="text-[8px] leading-none">●</span>
                     {activeTerminalStatus}
                   </span>
                 </div>
                 <div className="flex items-center gap-2">
                   <button className="px-2 py-1 text-[10px] font-mono rounded-md border border-[rgba(0,255,255,0.08)] text-white/60 hover:text-white hover:bg-white/5" onClick={() => getActiveTerminalHandle()?.reconnect()}>Reconnect</button>
                   <button className="px-2 py-1 text-[10px] font-mono rounded-md border border-[rgba(0,255,255,0.08)] text-white/60 hover:text-white hover:bg-white/5" onClick={() => getActiveTerminalHandle()?.clear()}>Clear</button>
                   <button className="px-2 py-1 text-[10px] font-mono rounded-md border border-[rgba(0,255,255,0.08)] text-white/60 hover:text-white hover:bg-white/5" onClick={() => getActiveTerminalHandle()?.copySelection()}>Copy</button>
                   <button className="px-2 py-1 text-[10px] font-mono rounded-md border border-red-500/20 text-red-300 hover:text-red-200 hover:bg-red-500/10" onClick={() => getActiveTerminalHandle()?.kill()}>Kill</button>
                   <button className="px-2 py-1 text-[10px] font-mono rounded-md border border-[#00E5FF]/20 text-[#00E5FF] hover:bg-[#00E5FF]/10" onClick={addTerminal}>New Terminal</button>
                 </div>
               </div>
               <div className="flex items-center gap-2 overflow-x-auto custom-scrollbar pb-0.5">
                 {terminalSessions.map((session) => (
                   <button
                     key={session.id}
                     onClick={() => setActiveTerminalId(session.id)}
                     className={`flex items-center gap-2 px-3 py-1.5 rounded-md border text-[10px] font-mono uppercase tracking-[0.25em] whitespace-nowrap transition-colors ${activeTerminalId === session.id ? 'bg-[#00E5FF]/10 border-[#00E5FF]/30 text-[#00E5FF]' : 'bg-[#0b0f17] border-[rgba(0,255,255,0.08)] text-white/50 hover:text-white hover:bg-white/5'}`}
                   >
                     {session.label}
                     <span className={`w-1.5 h-1.5 rounded-full ${terminalStatuses[session.id] === 'connected' ? 'bg-emerald-400' : terminalStatuses[session.id] === 'reconnecting' ? 'bg-orange-400' : terminalStatuses[session.id] === 'connecting' ? 'bg-yellow-400' : 'bg-red-400'}`} />
                     {terminalSessions.length > 1 && (
                       <span
                         className="ml-1 text-white/40 hover:text-white"
                         onClick={(event) => {
                           event.stopPropagation();
                           closeTerminal(session.id);
                         }}
                       >
                         x
                       </span>
                     )}
                   </button>
                 ))}
               </div>
             </div>

            <div className="flex-1 p-2 relative z-10">
                {activeTerminal && (
                  <XtermTerminal
                    ref={(instance) => { terminalRefs.current[activeTerminal.id] = instance; }}
                    wsUrl={activeTerminal.wsUrl}
                    onStatusChange={(status) => setTerminalStatuses(prev => ({ ...prev, [activeTerminal.id]: status }))}
                    forceTheme="dark"
                  />
                )}
            </div>
          </div>}
          
          {/* System Log */}
          {panelVisibility.logs && <div className="resizer-y -my-2" onMouseDown={startResize('y', logsHeight, setLogsHeight, 140, 420, true)} />}
          {panelVisibility.logs && <div className="bg-[#111827] backdrop-blur-xl border border-[rgba(0,255,255,0.08)] rounded-xl flex flex-col shadow-md dark:shadow-xl overflow-hidden relative" style={{ height: logsHeight }}>
             <div className="px-5 py-3 border-b border-[rgba(0,255,255,0.08)] bg-[#161B22] dark:bg-[#161B22] flex justify-between tracking-widest uppercase text-[11px] font-bold text-white/70 dark:text-white/70">
              <div className="flex items-center gap-2">
                  <DatabaseZap className="w-3.5 h-3.5" />
                  CORE.SYSTEM.LOG
              </div>
              <span className={`text-sky-500 dark:text-[#00E5FF] flex items-center gap-2 ${coreStatus === 'running' ? 'animate-pulse' : 'opacity-30'}`}>
                  <Radio className="w-3.5 h-3.5" />
                  REC
              </span>
            </div>
            <div ref={sysRef} className="flex-1 space-y-2 overflow-y-auto font-mono text-[11px] p-5 pb-12">
               {sysLogs.map((log, i) => {
                   const isInfo = log.includes('[INFO]');
                   const isWarn = log.includes('[WARN]');
                   const isErr = log.includes('[ERROR]');
                   
                   let tagColor = "text-sky-500 dark:text-[#00E5FF]";
                   if (isErr) tagColor = "text-red-500";
                   if (isWarn) tagColor = "text-amber-600 dark:text-amber-400";

                   return (
                       <div key={i} className="flex gap-4 p-1.5 rounded-md hover:bg-[#161B22] dark:hover:bg-[#161B22] transition-colors">
                           <span className={`${tagColor} font-bold w-12 shrink-0`}>
                               {isErr ? 'ERR ' : isWarn ? 'WARN' : 'INFO'}
                           </span>
                           <span className={isErr ? 'text-red-750 dark:text-red-200' : isWarn ? 'text-amber-800 dark:text-amber-400' : 'text-slate-300'}>
                               {log.replace(/\[(INFO|WARN|ERROR)\] /, '')}
                           </span>
                       </div>
                   );
               })}
               {coreStatus === 'running' && <div className="text-emerald-600 dark:text-[#00ff9d] italic pt-3 border-t border-slate-200 dark:border-white/5 mt-3">System healthy. Stream active.</div>}
            </div>
          </div>}
        </div>

        {/* Right - Graph & AI */}
        {(panelVisibility.graph || panelVisibility.ai) && <div className="resizer-x -mx-2" onMouseDown={startResize('x', rightWidth, setRightWidth, 260, 520, true)} />}
        {(panelVisibility.graph || panelVisibility.ai) && <div className="flex flex-col gap-4 shrink-0" style={{ width: rightWidth }}>
          
          {/* Node Graph */}
          {panelVisibility.graph && <div className="bg-[#111827] backdrop-blur-md border border-[rgba(0,255,255,0.08)] rounded-xl flex flex-col shadow-md dark:shadow-xl overflow-hidden relative" style={{ height: graphHeight }}>
             <div className="px-5 py-3 border-b border-[rgba(0,255,255,0.08)] bg-[#161B22] dark:bg-[#161B22] text-[11px] font-bold font-mono text-white/70 dark:text-white tracking-widest flex items-center justify-between">
               <span data-tooltip="Visual ROS node communication map.">NODE GRAPH</span> <Activity className={`w-3.5 h-3.5 text-sky-500 dark:text-[#00E5FF] ${coreStatus === 'running' ? 'animate-tech-pulse' : 'opacity-30'}`} />
             </div>
             <div className="flex-1 relative overflow-hidden flex items-center justify-center p-4 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] bg-opacity-5">
                {/* Radar sweep background */}
                {coreStatus === 'running' && (
                    <div className="absolute inset-0 flex items-center justify-center opacity-[0.08] dark:opacity-20 pointer-events-none">
                        <div className="w-full h-full rounded-full border border-sky-500/30 dark:border-[#00E5FF]/30 border-t-sky-500 dark:border-t-[#00E5FF] animate-radar" style={{ width: '200%', height: '200%' }} />
                    </div>
                )}
                
                {/* Simulated Node Graph Visual */}
                <svg 
                  className={`w-full h-full transition-opacity duration-1000 relative z-10 ${coreStatus === 'running' ? 'opacity-100' : 'opacity-20'}`} 
                  viewBox="0 0 200 200"
                  style={{
                    '--line-grad-start': theme === 'dark' ? '#4a4a4d' : '#cbd5e1',
                    '--line-grad-end': theme === 'dark' ? '#00E5FF' : '#0284c7',
                  } as React.CSSProperties}
                >
                  <defs>
                    <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" stopColor="var(--line-grad-start)" stopOpacity="0.8" />
                      <stop offset="100%" stopColor="var(--line-grad-end)" stopOpacity="1" />
                    </linearGradient>
                    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                       <feGaussianBlur stdDeviation="3" result="blur" />
                       <feComposite in="SourceGraphic" in2="blur" operator="over" />
                    </filter>
                  </defs>
                  
                  <path d="M 50 100 Q 100 50 150 100" fill="none" stroke="url(#lineGrad)" strokeWidth="1.5" strokeDasharray="3 3" className="animate-[dash_10s_linear_infinite]" />
                  <path d="M 50 100 Q 100 150 150 100" fill="none" stroke="url(#lineGrad)" strokeWidth="1.5" className="animate-[dash_5s_linear_infinite]" />
                  
                  {/* Sensor Node */}
                  <rect x="35" y="85" width="30" height="30" fill={theme === 'dark' ? '#111111' : '#f1f5f9'} stroke={theme === 'dark' ? '#333' : '#cbd5e1'} strokeWidth="2" rx="4" />
                  <text x="50" y="100" fill={theme === 'dark' ? '#888' : '#64748b'} fontSize="6" fontFamily="monospace" textAnchor="middle" dy="2" fontWeight="bold">sensor</text>

                  {/* Nav Node */}
                  <rect x="135" y="85" width="30" height="30" fill={theme === 'dark' ? '#000000' : '#111827'} stroke={theme === 'dark' ? '#00E5FF' : '#0ea5e9'} strokeWidth="2" rx="4" filter={coreStatus === 'running' ? 'url(#glow)' : ''} />
                  <text x="150" y="100" fill={theme === 'dark' ? '#fff' : '#0f172a'} fontSize="6" fontFamily="monospace" textAnchor="middle" dy="2" fontWeight="bold">nav</text>
                  
                  {/* Topic Node */}
                  <rect x="85" y="87" width="30" height="26" fill={theme === 'dark' ? '#00E5FF' : '#0ea5e9'} rx="12" filter={coreStatus === 'running' ? 'url(#glow)' : ''} />
                  <text x="100" y="100" fill={theme === 'dark' ? '#000' : '#fff'} fontSize="5.5" fontFamily="monospace" fontWeight="bold" textAnchor="middle" dy="2">/cmd_vel</text>

                  {/* Pulsing signal on path */}
                  {coreStatus === 'running' && (
                      <circle r="2.5" fill={theme === 'dark' ? '#fff' : '#0ea5e9'} filter="url(#glow)">
                        <animateMotion dur="1.5s" repeatCount="indefinite" path="M 50 100 Q 100 50 150 100" />
                      </circle>
                  )}
                </svg>
             </div>
          </div>}
          {panelVisibility.graph && panelVisibility.ai && <div className="resizer-y -my-2" onMouseDown={startResize('y', graphHeight, setGraphHeight, 160, 460)} />}

          {/* AI Co-Pilot */}
          {panelVisibility.ai && <div className="flex-1 bg-[#111827] backdrop-blur-md border border-[rgba(0,255,255,0.08)] rounded-xl flex flex-col shadow-md dark:shadow-xl overflow-hidden font-mono text-[11px] relative">
             <div className="px-5 py-3 border-b border-[rgba(0,255,255,0.08)] bg-[#161B22] dark:bg-[#161B22] flex justify-between tracking-widest font-bold uppercase text-white/70 dark:text-white/70">
               <span className="flex items-center gap-2" data-tooltip="Ask questions about ROS, code, debugging and robotics."><Cpu className="w-3.5 h-3.5" /> AI CO-PILOT</span>
               <span className="text-sky-600 dark:text-[#00E5FF] bg-sky-50 dark:bg-[#00E5FF]/10 px-2 rounded-md border border-sky-300/50 dark:border-[#00E5FF]/30">ONLINE</span>
             </div>
             
             <div ref={aiChatRef} className="flex-1 p-4 overflow-y-auto flex flex-col gap-3 relative z-10">
               {/* System status message */}
               <div className={`p-3 border-l-4 rounded-r-lg shadow-sm dark:shadow-lg transition-all duration-500 ${
                   coreStatus === 'running' && aiMessage.includes('congestion') 
                   ? 'bg-[#14161c] dark:bg-[#14161c] border-amber-500 text-amber-200 dark:text-amber-400 shadow-[inset_0_0_20px_rgba(245,158,11,0.08)] dark:shadow-[inset_0_0_20px_rgba(245,158,11,0.1)]' 
                   : 'bg-sky-500/5 dark:bg-[#00E5FF]/10 border-sky-500 dark:border-[#00E5FF] text-sky-900 dark:text-[#e0ffff] shadow-[inset_0_0_20px_rgba(14,165,233,0.05)] dark:shadow-[inset_0_0_20px_rgba(0,242,255,0.05)]'
               }`}>
                 <div className="flex items-center gap-2 mb-1.5">
                   <Bot className="w-3 h-3 text-sky-500 dark:text-[#00E5FF]" />
                   <span className="text-[9px] text-sky-600 dark:text-[#00E5FF] font-bold uppercase tracking-widest">System</span>
                 </div>
                 <p className="leading-relaxed text-[12px]">{aiMessage}</p>
               </div>
               
               {coreStatus === 'running' && aiMessage.includes('congestion') && (
                   <button 
                       onClick={handleAutoTune}
                       disabled={isAiTuning}
                       className="relative overflow-hidden w-full py-2.5 border border-sky-500/50 dark:border-[#00E5FF]/50 bg-sky-500/10 dark:bg-[#00E5FF]/10 text-sky-600 dark:text-[#00E5FF] hover:bg-sky-500 hover:text-white dark:hover:bg-[#00E5FF] dark:hover:text-white uppercase font-bold tracking-widest transition-all rounded-lg flex items-center justify-center gap-2 group shadow-[0_0_15px_rgba(14,165,233,0.1)] dark:shadow-[0_0_15px_rgba(0,242,255,0.2)] hover:shadow-[0_0_25px_rgba(14,165,233,0.4)] dark:hover:shadow-[0_0_25px_rgba(0,242,255,0.6)]"
                    >
                     <div className="absolute inset-0 opacity-10 group-hover:opacity-20 bg-[repeating-linear-gradient(45deg,transparent,transparent_10px,currentColor_10px,currentColor_20px)] animate-[matrix-scroll_2s_linear_infinite]" />
                     <span className="relative z-10 flex items-center gap-2">
                        {isAiTuning ? (
                            <>
                                <div className="w-4 h-4 rounded-full border-2 border-t-current border-r-current border-b-transparent border-l-transparent animate-spin"/>
                                TUNING PARAMS...
                            </>
                        ) : (
                            <>
                                <AlertTriangle className="w-4 h-4" /> AUTO-TUNE RATES
                            </>
                        )}
                     </span>
                   </button>
               )}

               {/* Chat messages */}
               {aiLogs.map((log, i) => (
                   <div key={i} className={`flex flex-col ${log.type === 'USER' ? 'items-end' : 'items-start'}`}>
                       {log.type === 'AI' && (
                           <div className="flex items-center gap-2 mb-1 ml-1">
                              <Bot className="w-3 h-3 text-sky-500 dark:text-[#00E5FF]" />
                              <span className="text-[9px] text-sky-600 dark:text-[#00E5FF] font-bold uppercase tracking-widest">AI</span>
                           </div>
                       )}
                       <div className={`p-2.5 rounded-lg text-[11px] leading-relaxed max-w-[90%] relative ${
                           log.type === 'USER' 
                           ? 'bg-slate-100 dark:bg-[#111827]/10 text-slate-300 border border-slate-200 dark:border-white/20' 
                           : 'bg-sky-500/5 dark:bg-[#00E5FF]/10 border border-sky-500/20 dark:border-[#00E5FF]/20 text-sky-900 dark:text-[#e0ffff]'
                       }`}>
                           {log.type === 'AI' && <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-sky-500 dark:bg-[#00E5FF] rounded-l-lg" />}
                           {log.text}
                       </div>
                   </div>
               ))}

               {isAiChatLoading && (
                   <div className="flex items-center gap-2 text-sky-500/70 dark:text-[#00E5FF]/60 ml-1">
                       <div className="w-3 h-3 rounded-full border-2 border-t-sky-500 dark:border-t-[#00E5FF] border-r-sky-500 dark:border-r-[#00E5FF] border-b-transparent border-l-transparent animate-spin"/>
                       <span className="text-[9px] uppercase tracking-widest">Processing...</span>
                   </div>
               )}
               
               {coreStatus === 'stopped' && aiLogs.length === 0 && (
                   <div className="text-center text-slate-300 text-[10px] uppercase flex flex-col items-center gap-2 pt-6">
                       <Radio className="w-6 h-6 opacity-20" />
                       Awaiting telemetry stream.
                   </div>
               )}
             </div>

             {/* Chat Input */}
             <div className="p-3 border-t border-[rgba(0,255,255,0.08)] bg-[#161B22] dark:bg-[#161B22] shrink-0 z-10">
               <div className="bg-[#111827] dark:bg-[#111827] border border-[rgba(0,255,255,0.08)] flex items-center px-3 py-2.5 rounded-lg focus-within:border-sky-500/50 dark:focus-within:border-[#00E5FF]/50 transition-all relative overflow-hidden group">
                 <div className="absolute bottom-0 left-0 h-px w-0 bg-sky-500 dark:bg-[#00E5FF] transition-all duration-500 group-focus-within:w-full" />
                 <input 
                   type="text" 
                   value={aiChatInput}
                   onChange={(e) => setAiChatInput(e.target.value)}
                   onKeyDown={handleAiChatSubmit}
                   placeholder="Ask AI about ROS operations..." 
                   disabled={isAiChatLoading}
                   className="bg-transparent flex-1 outline-none text-[11px] font-mono text-slate-300 placeholder:text-slate-400 dark:placeholder:text-white/30 disabled:cursor-not-allowed disabled:opacity-60" 
                 />
                 <Send
                   className={`w-4 h-4 shrink-0 transition-colors ${aiChatInput && !isAiChatLoading ? 'text-sky-500 dark:text-[#00E5FF] cursor-pointer hover:text-slate-800 dark:hover:text-white' : 'text-slate-300 dark:text-white/20'}`}
                   onClick={() => void sendAiChat(aiChatInput)}
                 />
               </div>
               <div className="flex gap-2 mt-2">
                   <button onClick={() => setAiChatInput("Diagnose current system state")} className="text-[9px] font-mono text-white/60 dark:text-white/60 hover:text-sky-600 dark:hover:text-[#00E5FF] border border-[rgba(0,255,255,0.08)] hover:border-sky-500/30 dark:hover:border-[#00E5FF]/30 bg-[#111827] dark:bg-[#111827] px-2 py-1 rounded-md transition-all flex-1">Diagnose</button>
                   <button onClick={() => setAiChatInput("Suggest parameter optimizations")} className="text-[9px] font-mono text-white/60 dark:text-white/60 hover:text-sky-600 dark:hover:text-[#00E5FF] border border-[rgba(0,255,255,0.08)] hover:border-sky-500/30 dark:hover:border-[#00E5FF]/30 bg-[#111827] dark:bg-[#111827] px-2 py-1 rounded-md transition-all flex-1">Optimize</button>
               </div>
             </div>
          </div>}
        </div>}
      </div>
      
      <AnimatePresence>
        {terminalMenu && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.12 }}
            className="fixed z-[80] min-w-56 rounded-lg border border-[rgba(0,255,255,0.12)] bg-[#111827] p-1 shadow-2xl text-[11px] font-mono text-white"
            style={{ left: terminalMenu.x, top: terminalMenu.y }}
            onClick={(event) => event.stopPropagation()}
            onContextMenu={(event) => event.preventDefault()}
          >
            <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { void getActiveTerminalHandle()?.copySelection(); setTerminalMenu(null); }}>Copy</button>
            <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={async () => {
              const text = await navigator.clipboard.readText().catch(() => '');
              const terminalHandle = getActiveTerminalHandle();
              if (text && terminalHandle) {
                terminalHandle.sendInput(text);
              }
              setTerminalMenu(null);
            }}>Paste</button>
            <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { getActiveTerminalHandle()?.selectAll(); setTerminalMenu(null); }}>Select All</button>
            <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { getActiveTerminalHandle()?.clear(); setTerminalMenu(null); }}>Clear</button>
            <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { getActiveTerminalHandle()?.reconnect(); setTerminalMenu(null); }}>Reconnect</button>
            <button className="w-full text-left px-3 py-2 rounded-md hover:bg-white/5" onClick={() => { downloadRosLogs(); setTerminalMenu(null); }}>Download Logs</button>
          </motion.div>
        )}
      </AnimatePresence>
      
      <style>{`
        @keyframes dash {
          to { stroke-dashoffset: -100; }
        }
      `}</style>
    </div>
  );
}

function PackageNode({ pkg }: { pkg: { name: string, isRunning: boolean, freq: string, cpu: string } }) {
  return (
    <div className={`p-3 border rounded-lg flex flex-col gap-2 transition-all ${
        pkg.isRunning 
        ? 'bg-[#14161c] dark:bg-[#14161c] border-sky-500/30 dark:border-[#00E5FF]/30 shadow-[0_0_10px_rgba(14,165,233,0.08)] dark:shadow-[0_0_10px_rgba(0,242,255,0.08)]' 
        : 'bg-[#161B22] dark:bg-[#161B22] border-slate-100 dark:border-white/10'
    }`}>
      <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-2 h-2 rounded-full transition-all duration-500 ${
                pkg.isRunning ? 'bg-sky-500 dark:bg-[#00E5FF] shadow-[0_0_10px_rgba(14,165,233,0.8)] dark:shadow-[0_0_10px_rgba(0,242,255,0.8)]' : 'bg-slate-300 dark:bg-[#111827]/20'
            }`} />
            <span className={`text-[12px] font-mono tracking-wide ${pkg.isRunning ? 'text-slate-300 font-bold' : 'text-slate-300'}`}>
                {pkg.name}
            </span>
          </div>
          {pkg.isRunning && (
              <span className="text-[10px] font-mono text-emerald-600 dark:text-[#00ff9d] border border-emerald-500/30 dark:border-[#00ff9d]/30 bg-emerald-50 dark:bg-[#00ff9d]/10 px-1.5 py-0.5 rounded">
                  ACTIVE
              </span>
          )}
      </div>
      
      {pkg.isRunning && (
          <div className="flex items-center gap-4 pl-5 text-[10px] font-mono text-white/50 dark:text-white/60">
             <div className="flex items-center gap-1">
                 <Activity className="w-3 h-3 text-sky-500 dark:text-[#00E5FF]" />
                 {pkg.freq}
             </div>
             <div className="flex items-center gap-1">
                 <Cpu className="w-3 h-3 text-purple-500 dark:text-purple-400" />
                 {pkg.cpu}
             </div>
          </div>
      )}
    </div>
  );
}
