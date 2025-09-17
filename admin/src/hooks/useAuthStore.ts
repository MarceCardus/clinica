import { create } from 'zustand';

interface AuthState {
  token: string | null;
  role: string | null;
  setAuth: (token: string, role: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('admin_token'),
  role: localStorage.getItem('admin_role'),
  setAuth: (token, role) => {
    localStorage.setItem('admin_token', token);
    localStorage.setItem('admin_role', role);
    set({ token, role });
  },
  logout: () => {
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_role');
    set({ token: null, role: null });
  }
}));
