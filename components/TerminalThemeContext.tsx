'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth, getUserThemePreference, saveUserThemePreference } from '@/lib/firebase';

type TerminalTheme = 'light' | 'dark';

interface TerminalThemeContextType {
  theme: TerminalTheme;
  setTheme: (theme: TerminalTheme) => void;
  toggleTheme: () => void;
}

const TerminalThemeContext = createContext<TerminalThemeContextType | undefined>(undefined);

export function TerminalThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<TerminalTheme>(() => {
    if (typeof window === 'undefined') {
      return 'dark';
    }
    const stored = window.localStorage.getItem('neuros-theme');
    if (stored === 'light' || stored === 'dark') {
      return stored;
    }
    if (window.matchMedia?.('(prefers-color-scheme: light)').matches) {
      return 'light';
    }
    return 'dark';
  });
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    window.localStorage.setItem('neuros-theme', theme);
    if (userId) {
      void saveUserThemePreference(userId, theme);
    }
  }, [theme, userId]);

  useEffect(() => {
    if (!auth) {
      return;
    }

    return onAuthStateChanged(auth, async (user) => {
      setUserId(user?.uid ?? null);
      if (!user) {
        return;
      }

      const savedTheme = await getUserThemePreference(user.uid).catch(() => null);
      if (savedTheme) {
        setTheme(savedTheme);
      }
    });
  }, []);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  return (
    <TerminalThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </TerminalThemeContext.Provider>
  );
}

export function useTerminalTheme() {
  const context = useContext(TerminalThemeContext);
  if (!context) {
    return { theme: 'dark' as TerminalTheme, setTheme: () => {}, toggleTheme: () => {} };
  }
  return context;
}
