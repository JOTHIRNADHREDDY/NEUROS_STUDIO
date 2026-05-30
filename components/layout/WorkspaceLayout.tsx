'use client';

import { ReactNode } from 'react';
import { ViewType } from '@/components/shared/Sidebar';
import TopNav from '@/components/shared/TopNav';
import { motion, AnimatePresence } from 'motion/react';

interface WorkspaceLayoutProps {
  children: ReactNode;
  currentView: ViewType;
  onChangeView: (view: ViewType) => void;
  onLogout?: () => void;
  showTopNavigation?: boolean;
  bottomNode?: ReactNode;
}

export default function WorkspaceLayout({
  children,
  currentView,
  onChangeView,
  onLogout,
  showTopNavigation = true,
  bottomNode,
}: WorkspaceLayoutProps) {
  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      {showTopNavigation && (
        <TopNav currentView={currentView} onChangeView={onChangeView} onLogout={onLogout} />
      )}

      <main className="relative flex-1 overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentView}
            initial={{ opacity: 0, y: 14, scale: 0.99 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.985 }}
            transition={{ duration: 0.28, ease: 'easeOut' }}
            className="absolute inset-0 overflow-hidden"
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </main>

      {bottomNode}
    </div>
  );
}
