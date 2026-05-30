import { create } from 'zustand';

interface GlobalState {
  ros: {
    core_running: boolean;
    active_nodes: number;
  };
  ide: {
    is_compiling: boolean;
    last_build: string | null;
  };
  devices: {
    connected_devices: any[];
  };
  setRosState: (state: Partial<GlobalState['ros']>) => void;
  setIdeState: (state: Partial<GlobalState['ide']>) => void;
  setDevicesState: (state: Partial<GlobalState['devices']>) => void;
  updateFromBackend: (fullState: any) => void;
}

export const useGlobalState = create<GlobalState>((set) => ({
  ros: {
    core_running: false,
    active_nodes: 0,
  },
  ide: {
    is_compiling: false,
    last_build: null,
  },
  devices: {
    connected_devices: [],
  },
  setRosState: (newState) => set((state) => ({ ros: { ...state.ros, ...newState } })),
  setIdeState: (newState) => set((state) => ({ ide: { ...state.ide, ...newState } })),
  setDevicesState: (newState) => set((state) => ({ devices: { ...state.devices, ...newState } })),
  updateFromBackend: (fullState) => set((state) => ({
    ros: { ...state.ros, ...fullState.ros },
    ide: { ...state.ide, ...fullState.ide },
    devices: { ...state.devices, ...fullState.devices },
  })),
}));
