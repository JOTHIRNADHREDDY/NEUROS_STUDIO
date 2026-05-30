'use client';

import { ReactNode, useEffect, useMemo, useRef } from 'react';
import { LAYOUT_STORAGE_KEY, createLayoutSnapshot, useLayoutStore } from '@/stores/useLayoutStore';

const LAYOUT_SHORTCUTS: Array<{ key: string; mode: 'left' | 'bottom' | 'right' }> = [
  { key: '1', mode: 'left' },
  { key: '2', mode: 'bottom' },
  { key: '3', mode: 'right' },
];

export default function LayoutProvider({ children }: { children: ReactNode }) {
  const hydrated = useLayoutStore((state) => state.hydrated);
  const setHydrated = useLayoutStore((state) => state.setHydrated);
  const hydrateSnapshot = useLayoutStore((state) => state.hydrateSnapshot);
  const setMode = useLayoutStore((state) => state.setMode);
  const panelSignature = useLayoutStore((state) => state.workspaceArrangement.join('|'));

  const mode = useLayoutStore((state) => state.mode);
  const dockSizes = useLayoutStore((state) => state.dockSizes);
  const collapsed = useLayoutStore((state) => state.collapsed);
  const openTabs = useLayoutStore((state) => state.openTabs);
  const activeTabs = useLayoutStore((state) => state.activeTabs);
  const workspaceArrangement = useLayoutStore((state) => state.workspaceArrangement);

  const snapshotKey = useMemo(
    () =>
      JSON.stringify({
        mode,
        dockSizes,
        collapsed,
        openTabs,
        activeTabs,
        workspaceArrangement,
      }),
    [mode, dockSizes, collapsed, openTabs, activeTabs, workspaceArrangement]
  );

  const previousSnapshot = useRef("");

  useEffect(() => {
    if (hydrated || typeof window === 'undefined') {
      return;
    }

    try {
      const stored = window.localStorage.getItem(LAYOUT_STORAGE_KEY);
      if (stored) {
        hydrateSnapshot(JSON.parse(stored) as Partial<ReturnType<typeof createLayoutSnapshot>>);
      }
    } catch {
      // Ignore corrupt layout snapshots and keep the default arrangement.
    } finally {
      setHydrated(true);
    }
  }, [hydrateSnapshot, setHydrated, hydrated]);

  useEffect(() => {
    if (!hydrated || typeof window === 'undefined') {
      return;
    }

    if (previousSnapshot.current === snapshotKey) {
      return;
    }

    previousSnapshot.current = snapshotKey;
    window.localStorage.setItem(LAYOUT_STORAGE_KEY, snapshotKey);
  }, [hydrated, snapshotKey]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const handleShortcut = (event: KeyboardEvent) => {
      if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
        return;
      }

      const shortcut = LAYOUT_SHORTCUTS.find((entry) => entry.key === event.key);
      if (!shortcut) {
        return;
      }

      event.preventDefault();
      setMode(shortcut.mode);
    };

    window.addEventListener('keydown', handleShortcut, { capture: true });
    return () => window.removeEventListener('keydown', handleShortcut, { capture: true });
  }, [setMode]);

  useEffect(() => {
    if (!panelSignature) {
      return;
    }

    const state = useLayoutStore.getState();

    const arrangement = Object.values(state.panelRegistry)
      .sort((leftPanel, rightPanel) => leftPanel.order - rightPanel.order)
      .map((panel) => panel.id);

    if (JSON.stringify(arrangement) !== JSON.stringify(state.workspaceArrangement)) {
      state.setWorkspaceArrangement(arrangement);
    }
  }, [panelSignature]);

  return <>{children}</>;
}
