'use client';

import { useState, useRef, useEffect } from 'react';
import { Bell, Database, DatabaseZap, Moon, Search, Settings, Sun, Terminal, User, Wifi, X } from 'lucide-react';
import { ViewType } from '@/components/shared/Sidebar';
import { useTerminalTheme } from '@/components/TerminalThemeContext';

interface TopNavProps {
  currentView?: ViewType;
  onChangeView?: (view: ViewType) => void;
  onLogout?: () => void;
}

type Notification = {
  id: string;
  title: string;
  message: string;
  read: boolean;
};

export default function TopNav({ currentView, onChangeView, onLogout }: TopNavProps) {
  const { theme, toggleTheme } = useTerminalTheme();
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([
    { id: '1', title: 'IMU Drift Detected', message: 'Calibration compensation applied.', read: false },
    { id: '2', title: 'Build Complete', message: 'nav_stack compiled successfully.', read: true },
  ]);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setShowNotifications(false);
      }
    }

    if (showNotifications) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showNotifications]);

  return (
    <header className="relative z-30 flex h-20 shrink-0 items-center justify-between border-b border-[#d8dee8] bg-white/95 px-8 shadow-[0_6px_20px_rgba(15,23,42,0.08)] dark:border-white/10 dark:bg-[#111827]/95 dark:shadow-[0_8px_22px_rgba(0,0,0,0.35)]">
      <div className="relative w-[480px] max-w-[34vw]">
        <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-[#64748b] dark:text-[#94a3b8]" />
        <input
          type="text"
          placeholder="Search telemetry, commands, files..."
          className="h-12 w-full rounded-[5px] border border-[#d8dee8] bg-white pl-12 pr-20 font-mono text-lg text-[#64748b] outline-none placeholder:text-[#64748b] focus:border-[#00ddeb] dark:border-white/10 dark:bg-[#0a0f1a] dark:text-white dark:placeholder:text-[#94a3b8]"
        />
        <div className="absolute right-3 top-1/2 flex -translate-y-1/2 gap-1 font-mono text-xs text-[#64748b] dark:text-[#94a3b8]">
          <span className="rounded border border-[#d8dee8] px-1 dark:border-white/10">⌘</span>
          <span className="rounded border border-[#d8dee8] px-1 dark:border-white/10">K</span>
        </div>
      </div>

      <div className="flex items-center gap-10 font-mono text-sm tracking-[0.08em] text-[#64748b] dark:text-[#94a3b8]">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-2">
            <DatabaseZap className="h-5 w-5 text-[#00ddeb]" />
            WS-01
          </span>
          <span className="flex items-center gap-2 font-black text-[#00ddeb]">
            <Wifi className="h-5 w-5" />
            99.9% UPLINK
          </span>
        </div>

        <div className="h-8 w-px bg-[#d8dee8] dark:bg-white/10" />

        <button
          type="button"
          onClick={() => onChangeView?.('files')}
          className={`flex items-center gap-2 hover:text-black dark:hover:text-white ${currentView === 'files' ? 'text-[#00ddeb]' : ''}`}
        >
          <Database className="h-5 w-5" />
          Files & Registry
        </button>

        <button
          type="button"
          onClick={() => onChangeView?.('settings')}
          className={`flex items-center gap-2 hover:text-black dark:hover:text-white ${currentView === 'settings' ? 'text-[#00ddeb]' : ''}`}
        >
          <Settings className="h-5 w-5" />
          Settings / Support
        </button>

        <div className="h-8 w-px bg-[#d8dee8] dark:bg-white/10" />

        <button type="button" onClick={() => onChangeView?.('ros')} className="hover:text-black dark:hover:text-white" title="Open terminal">
          <Terminal className="h-5 w-5" />
        </button>

        <button
          type="button"
          onClick={toggleTheme}
          className="flex h-9 w-9 items-center justify-center rounded-[5px] border border-[#d8dee8] text-[#64748b] hover:border-[#00ddeb] hover:text-[#00ddeb] dark:border-white/10 dark:bg-[#1f2937] dark:text-[#94a3b8] dark:hover:border-[#00ddeb] dark:hover:text-[#00ddeb] dark:hover:shadow-[0_0_16px_rgba(0,229,255,0.18)]"
          title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          aria-label={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        >
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>

        <div className="relative" ref={panelRef}>
          <button
            type="button"
            onClick={() => setShowNotifications((open) => !open)}
            className="relative hover:text-black"
            title="Notifications"
          >
            <Bell className="h-5 w-5" />
            {notifications.some((item) => !item.read) && (
              <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border border-black bg-[#ffb21a] dark:border-white" />
            )}
          </button>

          {showNotifications && (
            <div className="absolute right-0 top-9 w-80 border border-[#d8dee8] bg-white font-mono text-xs shadow-2xl dark:border-white/10 dark:bg-[#111827] dark:text-white">
              <div className="flex items-center justify-between border-b border-[#d8dee8] px-4 py-3 dark:border-white/10">
                <span className="font-black uppercase tracking-[0.16em]">Notifications</span>
                <button onClick={() => setNotifications([])} className="text-[#64748b] hover:text-red-500 dark:text-[#94a3b8]">
                  Clear
                </button>
              </div>
              {notifications.length === 0 ? (
                <div className="p-6 text-center text-[#64748b] dark:text-[#94a3b8]">No Notifications</div>
              ) : (
                notifications.map((notification) => (
                  <div key={notification.id} className="group relative border-b border-[#eef2f7] p-4 dark:border-white/10">
                    <div className="font-black">{notification.title}</div>
                    <div className="mt-1 text-[#64748b] dark:text-[#94a3b8]">{notification.message}</div>
                    <button
                      onClick={() => setNotifications((items) => items.filter((item) => item.id !== notification.id))}
                      className="absolute right-3 top-3 text-[#94a3b8] opacity-0 group-hover:opacity-100"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <button onClick={onLogout} className="flex h-10 w-10 items-center justify-center rounded-[5px] border border-[#d8dee8] hover:border-[#00ddeb] dark:border-white/10 dark:bg-[#1f2937] dark:hover:border-[#00ddeb]" title="Sign out">
          <User className="h-5 w-5" />
        </button>
      </div>
    </header>
  );
}
