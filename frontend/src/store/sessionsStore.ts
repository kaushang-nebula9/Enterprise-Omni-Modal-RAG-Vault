import { create } from 'zustand';
import type { SessionResponse } from '../types/chat';

interface SessionsState {
  sessions: SessionResponse[];
  isLoading: boolean;
  setSessions: (sessions: SessionResponse[]) => void;
  setLoading: (loading: boolean) => void;
  updateSession: (updated: SessionResponse) => void;
  removeSession: (id: string) => void;
}

export const useSessionsStore = create<SessionsState>((set) => ({
  sessions: [],
  isLoading: true,

  setSessions: (sessions) => set({ sessions }),

  setLoading: (loading) => set({ isLoading: loading }),

  updateSession: (updated) =>
    set((state) => ({
      sessions: state.sessions.map((s) => (s.id === updated.id ? updated : s)),
    })),

  removeSession: (id) =>
    set((state) => ({
      sessions: state.sessions.filter((s) => s.id !== id),
    })),
}));

// ---------------------------------------------------------------------------
// Derived selectors (computed outside the store to avoid stale closures)
// ---------------------------------------------------------------------------

/** Sessions sorted by updated_at desc, is_pinned === true */
export const selectPinnedSessions = (sessions: SessionResponse[]): SessionResponse[] =>
  sessions
    .filter((s) => s.is_pinned)
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());

/** Sessions sorted by updated_at desc, is_pinned === false */
export const selectUnpinnedSessions = (sessions: SessionResponse[]): SessionResponse[] =>
  sessions
    .filter((s) => !s.is_pinned)
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
