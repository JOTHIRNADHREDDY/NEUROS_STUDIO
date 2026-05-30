'use client';
import { motion } from 'motion/react';
import { Cpu, Box } from 'lucide-react';

export default function ComingSoonView({ title, type, onRouteChange }: { title: string, type: 'simulation' | 'physics', onRouteChange?: (route: string) => void }) {
  return (
    <div className="h-full flex flex-col items-center justify-center p-8 relative z-10 overflow-hidden bg-[var(--bg-primary)] text-[var(--text-primary)]">
      <motion.div 
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="flex flex-col items-center max-w-2xl text-center space-y-6"
      >
        <div className="relative">
           {/* Decorative Squares instead of Rings */}
           <motion.div 
             animate={{ rotate: 90 }} 
             transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
             className={`absolute inset-[-40px] border border-dashed opacity-20 ${type === 'simulation' ? 'border-[#00f2ff]' : 'border-[#00f2ff]'}`}
           />
           <div className={`w-24 h-24 flex items-center justify-center shadow-2xl relative bg-[var(--panel-bg)] rounded-full border border-[var(--panel-border)] text-[var(--accent)]`}>
             <div className="absolute inset-0 animate-pulse opacity-10 bg-current" />
             {type === 'simulation' ? <Box className="w-8 h-8" /> : <Cpu className="w-8 h-8" />}
           </div>
        </div>

        <h1 className="text-3xl font-light tracking-tight text-[var(--text-primary)] uppercase mt-4">
          {title}
        </h1>
        
        <div className="px-4 py-1.5 rounded-full border border-[var(--panel-border)] bg-[var(--bg-secondary)] text-[var(--accent)] font-mono text-[10px] tracking-widest font-bold shadow-[0_0_15px_rgba(0,229,255,0.1)]">
          SUBSYSTEM COMING SOON
        </div>

        <p className="text-[var(--text-secondary)] leading-relaxed font-mono text-xs mt-4 max-w-lg mb-8">
          {type === 'simulation' 
            ? "Advanced digital twin environment, sensor emulation, and path planning validation are currently undergoing infrastructure integration."
            : "Reinforcement learning, predictive analytics, and dynamic control tuning models will be available in the upcoming NEUROS OS update."}
        </p>

        {onRouteChange && (
           <button onClick={() => onRouteChange('dashboard')} className="px-6 py-2 rounded-lg border border-[var(--panel-border)] bg-[var(--panel-bg)] hover:bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-[var(--accent)] hover:border-[var(--accent)]/50 font-mono text-[11px] uppercase tracking-widest transition-colors shadow-lg mt-8">
             Return to Dashboard
           </button>
        )}
      </motion.div>

      {/* Blueprint grid background specifically for this view */}
      <div 
        className="absolute inset-0 z-[-1] opacity-10 pointer-events-none"
        style={{
          backgroundImage: `
            linear-gradient(#2a2a2d 1px, transparent 1px),
            linear-gradient(90deg, #2a2a2d 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
          maskImage: 'radial-gradient(ellipse at center, black 20%, transparent 70%)'
        }}
      />
    </div>
  );
}
