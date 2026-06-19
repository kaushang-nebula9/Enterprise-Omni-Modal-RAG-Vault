import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { useThemeStore } from '../../store/themeStore';

export const ThemeToggle: React.FC = () => {
  const { theme, toggleTheme } = useThemeStore();

  return (
    <button
      onClick={toggleTheme}
      type="button"
      className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors"
      aria-label="Toggle theme"
    >
      {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
    </button>
  );
};

export default ThemeToggle;
