'use client';

import { Eye, EyeOff } from 'lucide-react';
import { cn } from '@/lib/utils';

export type PanelDefinition = {
  id: string;
  label: string;
  shortLabel?: string;
};

export default function PanelControls({
  panels,
  visible,
  onToggle,
  className,
}: {
  panels: PanelDefinition[];
  visible: Record<string, boolean>;
  onToggle: (panelId: string) => void;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-wrap items-center justify-end gap-2', className)}>
      {panels.map((panel) => {
        const isVisible = visible[panel.id] ?? true;

        return (
          <button
            key={panel.id}
            type="button"
            title={`${isVisible ? 'Hide' : 'Show'} ${panel.label}`}
            aria-pressed={isVisible}
            onClick={() => onToggle(panel.id)}
            className={cn(
              'inline-flex h-8 items-center gap-2 rounded-md border px-3 text-[11px] font-mono uppercase tracking-wider transition-all duration-200 ease-in-out',
              isVisible
                ? 'border-[#00e5ff]/40 bg-[#00e5ff]/10 text-[#00e5ff] shadow-[0_0_14px_rgba(0,229,255,0.16)]'
                : 'border-[var(--panel-border)] bg-[var(--panel-bg)] text-[var(--text-secondary)] hover:border-[#00e5ff]/30 hover:text-[var(--text-primary)]'
            )}
          >
            {isVisible ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
            <span>{panel.shortLabel ?? panel.label}</span>
          </button>
        );
      })}
    </div>
  );
}
