import { create } from 'zustand';
import type { UserResponse } from '../types/auth';

interface AuthState {
  user: UserResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setUser: (user: UserResponse | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true, // starts as true (app is checking auth on mount)
  setUser: (user) => set({
    user,
    isAuthenticated: user !== null,
  }),
  setLoading: (loading) => set({
    isLoading: loading,
  }),
  logout: () => set({
    user: null,
    isAuthenticated: false,
  }),
}));
