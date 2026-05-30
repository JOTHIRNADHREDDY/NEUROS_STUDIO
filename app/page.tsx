'use client';
import { useState, useEffect } from 'react';
import { onAuthStateChanged, signOut } from 'firebase/auth';
import { ViewType } from '@/components/shared/Sidebar';
import Login from '@/components/Login';
import DashboardView from '@/components/views/DashboardView';
import IdeView from '@/components/views/IdeView';
import RosView from '@/components/views/RosView';
import ComingSoonView from '@/components/views/ComingSoonView';
import FilesView from '@/components/views/FilesView';

import { TerminalThemeProvider } from '@/components/TerminalThemeContext';
import LayoutProvider from '@/components/layout/LayoutProvider';
import LayoutShell from '@/components/layout/LayoutShell';
import { auth, isFirebaseConfigured, syncUserProfile } from '@/lib/firebase';

export default function AppShell() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentView, setCurrentView] = useState<ViewType>('dashboard');

  useEffect(() => {
    if (!auth || !isFirebaseConfigured) {
      return;
    }

    return onAuthStateChanged(auth, (user) => {
      setIsAuthenticated(Boolean(user));
      if (user) {
        void syncUserProfile(user);
      }
    });
  }, []);

  useEffect(() => {
    const suppressResizeError = (e: ErrorEvent) => {
      if (
        e.message === 'ResizeObserver loop completed with undelivered notifications.' ||
        e.message === 'ResizeObserver loop limit exceeded'
      ) {
        const resizeObserverErrDiv = document.getElementById(
          'webpack-dev-server-client-overlay-div'
        );
        const resizeObserverErr = document.getElementById(
          'webpack-dev-server-client-overlay'
        );
        if (resizeObserverErr) {
          resizeObserverErr.setAttribute('style', 'display: none');
        }
        if (resizeObserverErrDiv) {
          resizeObserverErrDiv.setAttribute('style', 'display: none');
        }
        
        // Ensure Next.js error overlay is also suppressed if present (though mostly next-error-overlay)
        e.stopImmediatePropagation();
      }
    };
    window.addEventListener('error', suppressResizeError);
    return () => window.removeEventListener('error', suppressResizeError);
  }, []);

  if (!isAuthenticated) {
    return (
      <TerminalThemeProvider>
        <Login onLogin={() => setIsAuthenticated(true)} />
      </TerminalThemeProvider>
    );
  }

  const renderView = () => {
    if (currentView === 'dashboard') {
      return <DashboardView onRouteChange={(route) => setCurrentView(route as ViewType)} />;
    }

    if (currentView === 'ide') {
      return <IdeView onClose={() => setCurrentView('dashboard')} />;
    }

    if (currentView === 'ros') {
      return <RosView onClose={() => setCurrentView('dashboard')} />;
    }

    if (currentView === 'simulation') {
      return <ComingSoonView title="Simulation Environment" type="simulation" onRouteChange={(route) => setCurrentView(route as ViewType)} />;
    }

    if (currentView === 'physics_ai') {
      return <ComingSoonView title="Robot Intelligence" type="physics" onRouteChange={(route) => setCurrentView(route as ViewType)} />;
    }

    if (currentView === 'files') {
      return <FilesView onClose={() => setCurrentView('dashboard')} />;
    }

    return (
      <div className="flex h-full flex-col items-center justify-center relative">
        <button onClick={() => setCurrentView('dashboard')} className="absolute top-8 right-8 p-2 rounded-sm bg-white border border-gray-200 hover:border-[#f44]/30 hover:text-[#f44] text-gray-500 transition-colors font-mono text-xs flex items-center gap-2">
           CLOSE
        </button>
        <p className="text-gray-500 font-mono tracking-widest text-sm">SETTINGS & SUPPORT (OPERATIONAL PREFERENCES)</p>
      </div>
    );
  };

  return (
    <TerminalThemeProvider>
      <LayoutProvider>
        <LayoutShell currentView={currentView} onChangeView={setCurrentView} onLogout={() => auth ? void signOut(auth) : setIsAuthenticated(false)}>
          {renderView()}
        </LayoutShell>
      </LayoutProvider>
    </TerminalThemeProvider>
  );
}
