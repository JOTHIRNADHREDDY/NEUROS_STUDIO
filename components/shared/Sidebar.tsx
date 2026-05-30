'use client';

import { Activity, Box, Code2, Cpu, TerminalSquare } from 'lucide-react';
import { LayoutMode } from '@/stores/useLayoutStore';

export type ViewType = 'dashboard' | 'ide' | 'ros' | 'simulation' | 'physics_ai' | 'files' | 'settings';

interface SidebarProps {
  currentView: ViewType;
  onChangeView: (view: ViewType) => void;
  layoutMode: LayoutMode;
  collapsed: boolean;
  dockSize: number;
  onToggleCollapsed: () => void;
}

const navItems: { id: ViewType; label: string; icon: any }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: Activity },
  { id: 'ide', label: 'Studio IDE', icon: Code2 },
  { id: 'ros', label: 'ROS Console', icon: TerminalSquare },
  { id: 'simulation', label: 'Simulation', icon: Box },
  { id: 'physics_ai', label: 'Physics AI', icon: Cpu },
];

export default function Sidebar({ currentView, onChangeView }: SidebarProps) {
  return (
    <aside className="relative z-40 flex h-full w-20 shrink-0 flex-col items-center border-r border-[#d8dee8] bg-white dark:border-white/10 dark:bg-[#111827]">
      <button
        type="button"
        onClick={() => onChangeView('dashboard')}
        className="mt-6 flex h-16 w-16 rotate-45 items-center justify-center rounded-[8px] bg-[#00e5ff] shadow-[0_14px_24px_rgba(0,229,255,0.32)]"
        title="Dashboard"
      >
        <span className="-rotate-45 font-mono text-sm font-black text-black">NS</span>
      </button>

      <nav className="mt-14 flex flex-1 flex-col items-center gap-7">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = currentView === item.id;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChangeView(item.id)}
              title={item.label}
              className={`flex h-12 w-12 items-center justify-center rounded-[5px] border transition-colors ${
                active
                  ? 'border-[#00ddeb] bg-[#eaffff] text-[#00ddeb] dark:bg-[#00ddeb]/10'
                  : 'border-transparent text-[#555b63] hover:border-[#d8dee8] hover:text-black dark:text-[#94a3b8] dark:hover:border-white/10 dark:hover:text-white'
              }`}
            >
              <Icon className="h-6 w-6" />
            </button>
          );
        })}
      </nav>

      <button
        type="button"
        title="System pulse"
        className="mb-7 flex h-12 w-12 items-center justify-center rounded-full border border-[#24292f] bg-[#2d2f33] font-mono text-2xl text-white shadow-[0_10px_24px_rgba(0,0,0,0.28)]"
      >
        N
      </button>
    </aside>
  );
}
