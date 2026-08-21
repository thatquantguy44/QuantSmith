import { create } from "zustand";
import type { Model, ResearchModel } from "./types";
import { fetchModel, fetchResearch } from "./api";

interface ConsoleState {
  model: Model | null;
  loading: boolean;
  error: string | null;
  lastLoaded: number | null;
  load: (refresh?: boolean) => Promise<void>;

  research: ResearchModel | null;
  researchLoading: boolean;
  researchError: string | null;
  loadResearch: (refresh?: boolean) => Promise<void>;
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

  research: null,
  researchLoading: false,
  researchError: null,
  loadResearch: async (refresh = false) => {
    set({ researchLoading: true, researchError: null });
    try {
      const research = await fetchResearch(refresh);
      set({ research, researchLoading: false });
    } catch (e) {
      set({ researchError: String(e), researchLoading: false });
    }
  },
}));
