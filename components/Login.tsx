'use client';

import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Fingerprint } from 'lucide-react';
import {
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  updateProfile,
} from 'firebase/auth';
import { auth, applyAuthPersistence, googleProvider, isFirebaseConfigured, syncUserProfile } from '@/lib/firebase';

const strongPassword = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/;

function getAuthErrorMessage(error: unknown) {
  const code = typeof error === 'object' && error && 'code' in error ? String(error.code) : '';

  if (code === 'auth/configuration-not-found') {
    return 'Firebase Auth is not enabled for this project. Enable Email/Password in Firebase Authentication.';
  }

  if (code === 'auth/operation-not-allowed') {
    return 'This sign-in method is disabled in Firebase Authentication.';
  }

  if (code === 'auth/unauthorized-domain') {
    return 'This domain is not authorized in Firebase Authentication.';
  }

  if (code === 'auth/invalid-credential' || code === 'auth/wrong-password' || code === 'auth/user-not-found') {
    return 'Invalid email or password.';
  }

  return error instanceof Error ? error.message : 'Authentication failed.';
}

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('commander@neuros.dev');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [rememberDevice, setRememberDevice] = useState(false);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const runAuth = async (operation: () => Promise<unknown>) => {
    setMessage('');
    setBusy(true);
    try {
      if (!auth || !isFirebaseConfigured) {
        throw new Error('Firebase is not configured. Add NEXT_PUBLIC_FIREBASE_* values to your environment.');
      }
      await applyAuthPersistence(rememberDevice);
      await operation();
      onLogin();
    } catch (error) {
      setMessage(getAuthErrorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    void runAuth(async () => {
      if (!auth) return;

      if (mode === 'signup') {
        if (!name.trim()) throw new Error('Name is required.');
        if (!strongPassword.test(password)) throw new Error('Use 8+ characters with uppercase, lowercase, and a number.');
        if (password !== confirmPassword) throw new Error('Passwords do not match.');

        const credential = await createUserWithEmailAndPassword(auth, email, password);
        await updateProfile(credential.user, { displayName: name.trim() });
        await syncUserProfile(credential.user);
        return;
      }

      const credential = await signInWithEmailAndPassword(auth, email, password);
      await syncUserProfile(credential.user);
    });
  };

  const handleReset = async () => {
    setMessage('');
    if (!email.trim()) {
      setMessage('Enter your email first, then request a password reset.');
      return;
    }

    await runAuth(async () => {
      if (!auth) return;
      await sendPasswordResetEmail(auth, email);
      setMessage('Password reset email sent.');
    });
  };

  const handleGoogleLogin = () => {
    void runAuth(async () => {
      if (!auth) return;
      const credential = await signInWithPopup(auth, googleProvider);
      await syncUserProfile(credential.user);
    });
  };

  return (
    <div className="fixed inset-0 z-50 grid overflow-hidden bg-white text-[#05070a] dark:bg-[#0a0f1a] dark:text-white lg:grid-cols-[61%_39%]">
      <section className="relative hidden overflow-hidden border-r border-[#111827]/25 bg-[#eefdff] dark:border-white/10 dark:bg-[#0a0f1a] lg:block">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(0,229,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(0,229,255,0.08)_1px,transparent_1px)] bg-[length:40px_40px]" />
        <div className="absolute inset-0 shadow-[inset_-70px_0_70px_rgba(2,6,23,0.22)]" />

        <div className="relative z-10 flex h-full flex-col justify-between px-[5.2vw] py-[8vh]">
          <div className="flex h-20 w-20 rotate-45 items-center justify-center rounded-[10px] bg-[#00e5ff] shadow-[0_18px_35px_rgba(0,229,255,0.36)]">
            <span className="-rotate-45 font-mono text-base font-black tracking-tight text-black">NS</span>
          </div>

          <div className="max-w-xl border-l-2 border-[#00e5ff] pl-5">
            <h1 className="font-mono text-[30px] uppercase leading-[1.65] tracking-[0.08em]">
              Robotics OS
              <br />
              For Intelligent
              <br />
              Machines
            </h1>
          </div>

          <div className="mb-16 space-y-12">
            <SystemLine color="cyan" label="MASTER CONTROLLER" align="right" />
            <SystemLine color="amber" label="ROS CORE SYNC" align="middle" />
            <SystemLine color="slate" label="PHYSICS AI LINK" align="left" />
          </div>

          <div className="border-t border-[#cbd5e1] pt-8 font-mono text-xs uppercase tracking-[0.18em] text-[#64748b] dark:border-white/10 dark:text-[#94a3b8]">
            <span className="mr-7"><Dot color="cyan" /> System Status: <b className="font-medium text-[#00cfe8]">Online</b></span>
            <span className="mr-7"><Dot color="green" /> Auth Secure</span>
            <span className="mr-7"><Dot color="slate" /> Encryption Active</span>
            <span><Dot color="cyan" /> Cloud Sync: <b className="font-medium text-[#00cfe8]">Ready</b></span>
          </div>
        </div>
      </section>

      <section className="flex min-h-screen items-center bg-white px-8 py-10 dark:bg-[#0a0f1a] sm:px-16 lg:px-[5vw]">
        <div className="mx-auto w-full max-w-xl">
          <div className="mb-16 flex border-b border-[#d9dee7] font-mono text-sm tracking-[0.22em] dark:border-white/10">
            {(['signin', 'signup'] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setMode(tab)}
                className={`mr-10 border-b-2 px-0 pb-5 transition-colors ${
                  mode === tab
                    ? 'border-[#00ddeb] text-[#00ddeb]'
                    : 'border-transparent text-[#64748b] hover:text-[#0f172a] dark:text-[#94a3b8] dark:hover:text-white'
                }`}
              >
                {tab === 'signin' ? 'Sign In' : 'Create Account'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-8">
            <AnimatePresence mode="wait">
              {mode === 'signup' && (
                <motion.label initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="block overflow-hidden">
                  <span className="mb-2 block font-mono text-xs uppercase tracking-[0.22em] text-[#64748b] dark:text-[#94a3b8]">Commander Name</span>
                  <input value={name} onChange={(event) => setName(event.target.value)} className="h-14 w-full rounded-[5px] border border-[#d9dee7] bg-white px-5 font-mono text-sm outline-none focus:border-[#00ddeb] dark:border-white/10 dark:bg-[#111827] dark:text-white" />
                </motion.label>
              )}
            </AnimatePresence>

            <label className="block">
              <span className="mb-2 block font-mono text-xs uppercase tracking-[0.22em] text-[#64748b] dark:text-[#94a3b8]">Secure Email</span>
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required className="h-14 w-full rounded-[5px] border border-[#d9dee7] bg-white px-5 font-mono text-sm outline-none focus:border-[#00ddeb] dark:border-white/10 dark:bg-[#111827] dark:text-white" />
            </label>

            <label className="block">
              <span className="mb-2 flex items-center justify-between font-mono text-xs uppercase tracking-[0.22em] text-[#64748b] dark:text-[#94a3b8]">
                Credential Key
                {mode === 'signin' && (
                  <button type="button" onClick={handleReset} className="hover:text-[#00ddeb]">
                    Forgot Password?
                  </button>
                )}
              </span>
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required className="h-14 w-full rounded-[5px] border border-[#d9dee7] bg-white px-5 font-mono text-sm outline-none focus:border-[#00ddeb] dark:border-white/10 dark:bg-[#111827] dark:text-white" />
            </label>

            {mode === 'signup' && (
              <label className="block">
                <span className="mb-2 block font-mono text-xs uppercase tracking-[0.22em] text-[#64748b] dark:text-[#94a3b8]">Confirm Credential</span>
                <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required className="h-14 w-full rounded-[5px] border border-[#d9dee7] bg-white px-5 font-mono text-sm outline-none focus:border-[#00ddeb] dark:border-white/10 dark:bg-[#111827] dark:text-white" />
              </label>
            )}

            <label className="flex items-center gap-4 font-mono text-sm uppercase tracking-[0.18em] text-[#64748b] dark:text-[#94a3b8]">
              <input type="checkbox" checked={rememberDevice} onChange={(event) => setRememberDevice(event.target.checked)} className="h-5 w-5 rounded border-[#d9dee7] accent-[#00ddeb]" />
              Remember Device
            </label>

            {message && (
              <div className="rounded-[5px] border border-[#d9dee7] bg-[#f8fafc] px-4 py-3 font-mono text-xs text-[#64748b] dark:border-white/10 dark:bg-[#111827] dark:text-[#94a3b8]">{message}</div>
            )}

            <div className="space-y-5 pt-8">
              <button disabled={busy} type="submit" className="h-14 w-full rounded-[5px] border border-[#00ddeb] bg-[#e5fbff] font-mono text-sm font-black uppercase tracking-[0.35em] text-[#00cfe8] hover:bg-[#d8f9ff] disabled:cursor-not-allowed disabled:opacity-60">
                {busy ? 'Authenticating...' : mode === 'signin' ? 'Enter Studio' : 'Create Account'}
              </button>
              <button type="button" onClick={handleGoogleLogin} className="flex h-14 w-full items-center justify-center gap-3 rounded-[5px] border border-[#d9dee7] bg-white font-mono text-sm font-bold uppercase tracking-[0.24em] text-[#64748b] hover:border-[#00ddeb] hover:text-[#00cfe8] dark:border-white/10 dark:bg-[#111827] dark:text-[#94a3b8]">
                <Fingerprint className="h-5 w-5" />
                Google Login
              </button>
            </div>
          </form>
        </div>
      </section>
    </div>
  );
}

function Dot({ color }: { color: 'cyan' | 'green' | 'slate' }) {
  const colors = {
    cyan: 'bg-[#00ddeb]',
    green: 'bg-[#35c79b]',
    slate: 'bg-[#68707a]',
  };

  return <span className={`mr-2 inline-block h-1.5 w-1.5 rounded-full ${colors[color]}`} />;
}

function SystemLine({ color, label, align }: { color: 'cyan' | 'amber' | 'slate'; label: string; align: 'left' | 'middle' | 'right' }) {
  const colorClass = color === 'cyan' ? 'bg-[#67eaf4]' : color === 'amber' ? 'bg-[#ffb21a]' : 'bg-[#68707a]';
  const lineClass = color === 'cyan' ? 'bg-[#a6eef5]' : color === 'amber' ? 'bg-[#f2c45d]' : 'bg-[#cfd8e3]';
  const labelClass = color === 'cyan' ? 'text-[#00ddeb] border-[#9df4fa]' : color === 'amber' ? 'text-[#111827] dark:text-white border-[#d9dee7] dark:border-white/10' : 'text-[#64748b] dark:text-[#94a3b8] border-transparent';
  const labelPosition = align === 'right' ? 'ml-auto' : align === 'middle' ? 'ml-[58%]' : 'ml-[42%]';

  return (
    <div className="flex items-center gap-5 pl-12 pr-10">
      <span className={`h-4 w-4 rounded-[4px] ${colorClass} shadow-[0_0_20px_currentColor]`} />
      <div className={`h-px flex-1 ${lineClass}`} />
      <span className={`${labelPosition} whitespace-nowrap rounded-[5px] border bg-white/55 px-4 py-2 font-mono text-xs uppercase tracking-[0.16em] dark:bg-[#111827]/70 ${labelClass}`}>{label}</span>
    </div>
  );
}
