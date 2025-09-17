import { create } from 'zustand';

interface AuthState {
  token: string | null;
  user: { email: string } | null;
  setAuth: (token: string, email: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  setAuth: (token, email) => set({ token, user: { email } }),
  logout: () => set({ token: null, user: null })
}));
