import { create } from 'zustand';

type ThemeMode = 'light' | 'dark';

interface ThemeState {
  mode: ThemeMode;
  toggle: () => void;
  setMode: (mode: ThemeMode) => void;
}

function applyTheme(mode: ThemeMode) {
  document.documentElement.dataset.theme = mode;
}

export const useThemeStore = create<ThemeState>((set) => {
  const initial: ThemeMode =
    (localStorage.getItem('knot-theme') as ThemeMode) || 'light';
  applyTheme(initial);

  return {
    mode: initial,
    toggle: () =>
      set((state) => {
        const next = state.mode === 'light' ? 'dark' : 'light';
        localStorage.setItem('knot-theme', next);
        applyTheme(next);
        return { mode: next };
      }),
    setMode: (mode) => {
      localStorage.setItem('knot-theme', mode);
      applyTheme(mode);
      set({ mode });
    },
  };
});
