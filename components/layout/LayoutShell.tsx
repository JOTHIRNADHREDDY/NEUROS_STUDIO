'use client';

import { ReactNode, useMemo } from 'react';
import TelemetryBackground from '@/components/shared/TelemetryBackground';
import Sidebar, { ViewType } from '@/components/shared/Sidebar';
import WorkspaceLayout from '@/components/layout/WorkspaceLayout';
import { LayoutMode, useLayoutStore } from '@/stores/useLayoutStore';
import { useIsMobile } from '@/hooks/use-mobile';

interface LayoutShellProps {
  currentView: ViewType;
  onChangeView: (view: ViewType) => void;
  onLogout?: () => void;
  children: ReactNode;
}

export default function LayoutShell({ currentView, onChangeView, onLogout, children }: LayoutShellProps) {
  const isMobile = useIsMobile();
  const dockSizes = useLayoutStore((state) => state.dockSizes);
  const collapsed = useLayoutStore((state) => state.collapsed);
  const setDockCollapsed = useLayoutStore((state) => state.setDockCollapsed);

  const effectiveMode: LayoutMode = isMobile ? 'bottom' : 'left';
  const dockCollapsed = collapsed[effectiveMode];
  const dockSize = dockSizes[effectiveMode];

  const dockNode = useMemo(() => {
    return (
      <Sidebar
        currentView={currentView}
        onChangeView={onChangeView}
        layoutMode={effectiveMode}
        collapsed={dockCollapsed}
        dockSize={dockSize}
        onToggleCollapsed={() => setDockCollapsed(effectiveMode, !dockCollapsed)}
      />
    );
  }, [currentView, dockCollapsed, dockSize, effectiveMode, onChangeView, setDockCollapsed]);

  const showTopNav = !['ide', 'ros', 'simulation', 'physics_ai'].includes(currentView);

  return (
    <div className="relative flex h-screen overflow-hidden bg-white font-sans text-[#05070a] selection:bg-[#00f2ff] selection:text-black dark:bg-[#0a0f1a] dark:text-white">
      <TelemetryBackground />

      <div className={`relative z-10 h-full w-full min-w-0 overflow-hidden ${effectiveMode === 'left' ? 'grid grid-cols-[80px_minmax(0,1fr)]' : 'flex flex-col'}`}>
        {effectiveMode === 'left' && dockNode}

        <WorkspaceLayout 
          currentView={currentView} 
          onChangeView={onChangeView}
          onLogout={onLogout}
          showTopNavigation={showTopNav}
          bottomNode={effectiveMode === 'bottom' ? dockNode : undefined}
        >
          {children}
        </WorkspaceLayout>
      </div>
    </div>
  );
}
