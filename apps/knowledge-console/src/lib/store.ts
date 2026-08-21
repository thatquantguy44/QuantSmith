import { create } from "zustand";
import type { Model } from "./types";
import { fetchModel } from "./api";

interface ConsoleState {
  model: Model | null;
  loading: boolean;
  error: string | null;
  lastLoaded: number | null;
  load: (refresh?: boolean) => Promise<void>;
}

export const useConsole = create<ConsoleState>((set) => ({
  model: null,
  loading: false,
  error: null,
  lastLoaded: null,
  load: async (refresh = false) => {
    set({ loading: true, error: null });
    try {
      const model = await fetchModel(refresh);
      set({ model, loading: false, lastLoaded: Date.now() });
    } catch (e) {
      set({ error: String(e), loading: false });
    }
  },
}));
