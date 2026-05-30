'use client';

import { create } from 'zustand';

export type LayoutMode = 'left' | 'bottom' | 'right';
export type DockPosition = LayoutMode;
export type PanelRole = 'primary' | 'secondary' | 'utility';

export interface PanelDescriptor {
  id: string;
  title: string;
  role: PanelRole;
  preferredDock: DockPosition;
  order: number;
  tabs: string[];
  activeTab: string | null;
  collapsed: boolean;
}

export interface DockDescriptor {
  position: DockPosition;
  size: number;
  collapsed: boolean;
  activeTab: string | null;
  tabs: string[];
}

export interface LayoutSnapshot {
  mode: LayoutMode;
  dockSizes: Record<LayoutMode, number>;
  collapsed: Record<LayoutMode, boolean>;
  openTabs: Record<string, string[]>;
  activeTabs: Record<string, string | null>;
  workspaceArrangement: string[];
}

type LayoutRegistryEntry = {
  id: LayoutMode;
  label: string;
  description: string;
  hotkey: string;
};

export const LAYOUT_STORAGE_KEY = 'neuros-studio-layout-profile-v1';

const defaultDockSizes: Record<LayoutMode, number> = {
  left: 320,
  bottom: 280,
  right: 320,
};

const defaultCollapsed: Record<LayoutMode, boolean> = {
  left: false,
  bottom: false,
  right: false,
};

const defaultLayoutRegistry: Record<LayoutMode, LayoutRegistryEntry> = {
  left: {
    id: 'left',
    label: 'Left Dock',
    description: 'Pins secondary panels to the left side of the workspace.',
    hotkey: 'Alt+1',
  },
  bottom: {
    id: 'bottom',
    label: 'Bottom Dock',
    description: 'Stacks utility panels below the main workspace.',
    hotkey: 'Alt+2',
  },
  right: {
    id: 'right',
    label: 'Right Dock',
    description: 'Pins secondary panels to the right side of the workspace.',
    hotkey: 'Alt+3',
  },
};

const defaultDockRegistry: Record<LayoutMode, DockDescriptor> = {
  left: {
    position: 'left',
    size: defaultDockSizes.left,
    collapsed: defaultCollapsed.left,
    activeTab: null,
    tabs: [],
  },
  bottom: {
    position: 'bottom',
    size: defaultDockSizes.bottom,
    collapsed: defaultCollapsed.bottom,
    activeTab: null,
    tabs: [],
  },
  right: {
    position: 'right',
    size: defaultDockSizes.right,
    collapsed: defaultCollapsed.right,
    activeTab: null,
    tabs: [],
  },
};

const defaultPanelRegistry: Record<string, PanelDescriptor> = {};

function coerceMode(value: unknown): LayoutMode | null {
  return value === 'left' || value === 'bottom' || value === 'right' ? value : null;
}

function coerceStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === 'string') : [];
}

function coerceStringMap(value: unknown): Record<string, string[]> {
  if (!value || typeof value !== 'object') {
    return {};
  }

  return Object.entries(value as Record<string, unknown>).reduce<Record<string, string[]>>((acc, [key, entry]) => {
    acc[key] = coerceStringArray(entry);
    return acc;
  }, {});
}

function coerceNullableStringMap(value: unknown): Record<string, string | null> {
  if (!value || typeof value !== 'object') {
    return {};
  }

  return Object.entries(value as Record<string, unknown>).reduce<Record<string, string | null>>((acc, [key, entry]) => {
    acc[key] = typeof entry === 'string' ? entry : null;
    return acc;
  }, {});
}

export const layoutRegistry = defaultLayoutRegistry;
export const dockRegistry = defaultDockRegistry;
export const panelRegistry = defaultPanelRegistry;

interface LayoutState extends LayoutSnapshot {
  hydrated: boolean;
  layoutRegistry: Record<LayoutMode, LayoutRegistryEntry>;
  dockRegistry: Record<LayoutMode, DockDescriptor>;
  panelRegistry: Record<string, PanelDescriptor>;
  setHydrated: (hydrated: boolean) => void;
  setMode: (mode: LayoutMode) => void;
  toggleMode: (mode: LayoutMode) => void;
  setDockSize: (dock: LayoutMode, size: number) => void;
  setDockCollapsed: (dock: LayoutMode, collapsed: boolean) => void;
  registerPanel: (panel: Omit<PanelDescriptor, 'collapsed' | 'activeTab'> & Partial<Pick<PanelDescriptor, 'collapsed' | 'activeTab'>>) => void;
  unregisterPanel: (id: string) => void;
  setActiveTab: (panelId: string, tabId: string | null) => void;
  setOpenTabs: (panelId: string, tabs: string[]) => void;
  setWorkspaceArrangement: (panelIds: string[]) => void;
  hydrateSnapshot: (snapshot: Partial<LayoutSnapshot>) => void;
}

const baseState: LayoutSnapshot = {
  mode: 'left',
  dockSizes: defaultDockSizes,
  collapsed: defaultCollapsed,
  openTabs: {},
  activeTabs: {},
  workspaceArrangement: [],
};

export const useLayoutStore = create<LayoutState>((set) => ({
  ...baseState,
  hydrated: false,
  layoutRegistry: defaultLayoutRegistry,
  dockRegistry: defaultDockRegistry,
  panelRegistry: defaultPanelRegistry,
  setHydrated: (hydrated) => set({ hydrated }),
  setMode: (mode) => set({ mode }),
  toggleMode: (mode) => set({ mode }),
  setDockSize: (dock, size) => set((state) => ({
    dockSizes: { ...state.dockSizes, [dock]: size },
    dockRegistry: {
      ...state.dockRegistry,
      [dock]: { ...state.dockRegistry[dock], size },
    },
  })),
  setDockCollapsed: (dock, collapsed) => set((state) => ({
    collapsed: { ...state.collapsed, [dock]: collapsed },
    dockRegistry: {
      ...state.dockRegistry,
      [dock]: { ...state.dockRegistry[dock], collapsed },
    },
  })),
  registerPanel: (panel) => set((state) => {
    const existing = state.panelRegistry[panel.id];
    const nextPanel: PanelDescriptor = {
      ...existing,
      ...panel,
      collapsed: panel.collapsed ?? existing?.collapsed ?? false,
      activeTab: panel.activeTab ?? existing?.activeTab ?? null,
      tabs: panel.tabs ?? existing?.tabs ?? [],
    };

    const panelRegistryNext = { ...state.panelRegistry, [panel.id]: nextPanel };
    const dock = state.dockRegistry[nextPanel.preferredDock];
    const tabs = Array.from(new Set([...(dock.tabs ?? []), ...nextPanel.tabs]));

    return {
      panelRegistry: panelRegistryNext,
      dockRegistry: {
        ...state.dockRegistry,
        [nextPanel.preferredDock]: {
          ...dock,
          tabs,
          activeTab: nextPanel.activeTab ?? dock.activeTab,
        },
      },
      openTabs: {
        ...state.openTabs,
        [nextPanel.id]: nextPanel.tabs,
      },
      activeTabs: {
        ...state.activeTabs,
        [nextPanel.id]: nextPanel.activeTab,
      },
      workspaceArrangement: Object.values(panelRegistryNext)
        .sort((leftPanel, rightPanel) => leftPanel.order - rightPanel.order)
        .map((entry) => entry.id),
    };
  }),
  unregisterPanel: (id) => set((state) => {
    if (!state.panelRegistry[id]) {
      return state;
    }

    const { [id]: _removed, ...panelRegistryNext } = state.panelRegistry;
    const { [id]: _openTabs, ...openTabsNext } = state.openTabs;
    const { [id]: _activeTab, ...activeTabsNext } = state.activeTabs;

    return {
      panelRegistry: panelRegistryNext,
      openTabs: openTabsNext,
      activeTabs: activeTabsNext,
      workspaceArrangement: Object.values(panelRegistryNext)
        .sort((leftPanel, rightPanel) => leftPanel.order - rightPanel.order)
        .map((entry) => entry.id),
    };
  }),
  setActiveTab: (panelId, tabId) => set((state) => ({
    activeTabs: { ...state.activeTabs, [panelId]: tabId },
    panelRegistry: state.panelRegistry[panelId]
      ? {
          ...state.panelRegistry,
          [panelId]: { ...state.panelRegistry[panelId], activeTab: tabId },
        }
      : state.panelRegistry,
  })),
  setOpenTabs: (panelId, tabs) => set((state) => ({
    openTabs: { ...state.openTabs, [panelId]: tabs },
    panelRegistry: state.panelRegistry[panelId]
      ? {
          ...state.panelRegistry,
          [panelId]: { ...state.panelRegistry[panelId], tabs },
        }
      : state.panelRegistry,
  })),
  setWorkspaceArrangement: (panelIds) => set((state) => {
    if (JSON.stringify(state.workspaceArrangement) === JSON.stringify(panelIds)) {
      return state;
    }
    return { workspaceArrangement: panelIds };
  }),
  hydrateSnapshot: (snapshot) => set((state) => {
    const mode = coerceMode(snapshot.mode) ?? state.mode;
    const dockSizes = { ...defaultDockSizes, ...(snapshot.dockSizes ?? {}) };
    const collapsed = { ...defaultCollapsed, ...(snapshot.collapsed ?? {}) };

    return {
      mode,
      dockSizes,
      collapsed,
      openTabs: coerceStringMap(snapshot.openTabs),
      activeTabs: coerceNullableStringMap(snapshot.activeTabs),
      workspaceArrangement: coerceStringArray(snapshot.workspaceArrangement),
      dockRegistry: {
        left: { ...state.dockRegistry.left, size: dockSizes.left, collapsed: collapsed.left },
        bottom: { ...state.dockRegistry.bottom, size: dockSizes.bottom, collapsed: collapsed.bottom },
        right: { ...state.dockRegistry.right, size: dockSizes.right, collapsed: collapsed.right },
      },
    };
  }),
}));

export function createLayoutSnapshot(state: LayoutState = useLayoutStore.getState()): LayoutSnapshot {
  return {
    mode: state.mode,
    dockSizes: state.dockSizes,
    collapsed: state.collapsed,
    openTabs: state.openTabs,
    activeTabs: state.activeTabs,
    workspaceArrangement: state.workspaceArrangement,
  };
}

export function getDockDescriptor(mode: LayoutMode) {
  return useLayoutStore.getState().dockRegistry[mode];
}

export function getLayoutDescriptor(mode: LayoutMode) {
  return useLayoutStore.getState().layoutRegistry[mode];
}
