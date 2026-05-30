'use client';

import { motion } from 'motion/react';
import { PanelLeft, PanelBottom, PanelRight } from 'lucide-react';
import { LayoutMode, useLayoutStore } from '@/stores/useLayoutStore';

const OPTIONS: Array<{ mode: LayoutMode; label: string; icon: typeof PanelLeft }> = [
  { mode: 'left', label: 'Left Dock Layout', icon: PanelLeft },
  { mode: 'bottom', label: 'Bottom Dock Layout', icon: PanelBottom },
  { mode: 'right', label: 'Right Dock Layout', icon: PanelRight },
];

export default function LayoutToggle() {
  const mode = useLayoutStore((state) => state.mode);
  const setMode = useLayoutStore((state) => state.setMode);

  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 p-1 text-[10px] uppercase tracking-[0.32em] text-white/65 shadow-[0_0_24px_rgba(0,0,0,0.35)] backdrop-blur-xl">
      {OPTIONS.map((option) => {
        const Icon = option.icon;
        const active = mode === option.mode;

        return (
          <button
            key={option.mode}
            type="button"
            onClick={() => setMode(option.mode)}
            aria-pressed={active}
            aria-label={option.label}
            title={option.label}
            className={`relative flex items-center gap-2 rounded-full px-3 py-2 transition-all duration-200 ${
              active
                ? 'bg-[#00f2ff]/15 text-[#9efbff] shadow-[0_0_16px_rgba(0,242,255,0.25)]'
                : 'text-white/55 hover:bg-white/8 hover:text-white'
            }`}
          >
            {active && (
              <motion.span
                layoutId="layout-toggle-active"
                className="absolute inset-0 rounded-full border border-[#00f2ff]/30 bg-[#00f2ff]/10"
                transition={{ type: 'spring', stiffness: 500, damping: 36 }}
              />
            )}
            <span className="relative z-10 flex items-center gap-2">
              <Icon className="h-3.5 w-3.5" />
              <span className="hidden xl:inline">{option.label}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
