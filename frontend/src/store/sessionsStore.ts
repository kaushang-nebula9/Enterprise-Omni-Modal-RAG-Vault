import { create } from 'zustand';
import type { SessionResponse } from '../types/chat';
import { chatService } from '../services/chatService';

interface SessionsState {
  sessions: SessionResponse[];
  isLoading: boolean;
  
  pinnedHasMore: boolean;
  pinnedIsLoadingMore: boolean;
  pinnedError: string | null;
  
  unpinnedHasMore: boolean;
  unpinnedIsLoadingMore: boolean;
  unpinnedError: string | null;

  setSessions: (sessions: SessionResponse[]) => void;
  setLoading: (loading: boolean) => void;
  updateSession: (updated: SessionResponse) => void;
  removeSession: (id: string) => void;

  setPinnedHasMore: (hasMore: boolean) => void;
  setPinnedIsLoadingMore: (loading: boolean) => void;
  setPinnedError: (err: string | null) => void;

  setUnpinnedHasMore: (hasMore: boolean) => void;
  setUnpinnedIsLoadingMore: (loading: boolean) => void;
  setUnpinnedError: (err: string | null) => void;

  loadMorePinned: () => Promise<void>;
  loadMoreUnpinned: () => Promise<void>;
}

export const useSessionsStore = create<SessionsState>((set, get) => ({
  sessions: [],
  isLoading: true,
  
  pinnedHasMore: true,
  pinnedIsLoadingMore: false,
  pinnedError: null,
  
  unpinnedHasMore: true,
  unpinnedIsLoadingMore: false,
  unpinnedError: null,

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

  setPinnedHasMore: (hasMore) => set({ pinnedHasMore: hasMore }),
  setPinnedIsLoadingMore: (loading) => set({ pinnedIsLoadingMore: loading }),
  setPinnedError: (err) => set({ pinnedError: err }),

  setUnpinnedHasMore: (hasMore) => set({ unpinnedHasMore: hasMore }),
  setUnpinnedIsLoadingMore: (loading) => set({ unpinnedIsLoadingMore: loading }),
  setUnpinnedError: (err) => set({ unpinnedError: err }),

  loadMorePinned: async () => {
    const { sessions, pinnedIsLoadingMore, pinnedHasMore } = get();
    if (pinnedIsLoadingMore || !pinnedHasMore) return;
    
    set({ pinnedIsLoadingMore: true, pinnedError: null });
    try {
      const pinnedSessions = selectPinnedSessions(sessions);
      const limit = 10;
      const offset = pinnedSessions.length;
      
      const newSessions = await chatService.getSessions({
        is_pinned: true,
        limit,
        offset,
      });
      
      const existingIds = new Set(sessions.map((s) => s.id));
      const filtered = newSessions.filter((s) => !existingIds.has(s.id));
      
      set((state) => ({
        sessions: [...state.sessions, ...filtered],
        pinnedHasMore: newSessions.length === limit,
      }));
    } catch (err: any) {
      set({ pinnedError: err?.message || 'Failed to load more pinned chats' });
    } finally {
      set({ pinnedIsLoadingMore: false });
    }
  },

  loadMoreUnpinned: async () => {
    const { sessions, unpinnedIsLoadingMore, unpinnedHasMore } = get();
    if (unpinnedIsLoadingMore || !unpinnedHasMore) return;
    
    set({ unpinnedIsLoadingMore: true, unpinnedError: null });
    try {
      const unpinnedSessions = selectUnpinnedSessions(sessions);
      const limit = 10;
      const offset = unpinnedSessions.length;
      
      const newSessions = await chatService.getSessions({
        is_pinned: false,
        limit,
        offset,
      });
      
      const existingIds = new Set(sessions.map((s) => s.id));
      const filtered = newSessions.filter((s) => !existingIds.has(s.id));
      
      set((state) => ({
        sessions: [...state.sessions, ...filtered],
        unpinnedHasMore: newSessions.length === limit,
      }));
    } catch (err: any) {
      set({ unpinnedError: err?.message || 'Failed to load more chats' });
    } finally {
      set({ unpinnedIsLoadingMore: false });
    }
  },
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
