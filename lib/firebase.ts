'use client';

import { initializeApp, getApps } from 'firebase/app';
import {
  GithubAuthProvider,
  GoogleAuthProvider,
  getAuth,
  browserLocalPersistence,
  browserSessionPersistence,
  setPersistence,
  type User,
} from 'firebase/auth';
import { doc, getDoc, getFirestore, serverTimestamp, setDoc } from 'firebase/firestore';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID,
};

export const isFirebaseConfigured = Boolean(
  firebaseConfig.apiKey &&
  firebaseConfig.authDomain &&
  firebaseConfig.projectId &&
  firebaseConfig.appId
);

export const firebaseApp = isFirebaseConfigured
  ? getApps()[0] ?? initializeApp(firebaseConfig)
  : null;

export const auth = firebaseApp ? getAuth(firebaseApp) : null;
export const db = firebaseApp ? getFirestore(firebaseApp) : null;
export const googleProvider = new GoogleAuthProvider();
export const githubProvider = new GithubAuthProvider();

export async function applyAuthPersistence(rememberDevice: boolean) {
  if (!auth) {
    return;
  }

  await setPersistence(auth, rememberDevice ? browserLocalPersistence : browserSessionPersistence);
}

export async function syncUserProfile(user: User) {
  if (!db) {
    return;
  }

  await setDoc(
    doc(db, 'users', user.uid),
    {
      uid: user.uid,
      email: user.email,
      displayName: user.displayName ?? '',
      photoURL: user.photoURL ?? '',
      lastLoginAt: serverTimestamp(),
      preferences: {
        theme: typeof window !== 'undefined' ? window.localStorage.getItem('neuros-theme') ?? 'dark' : 'dark',
      },
    },
    { merge: true }
  );
}

export async function getUserThemePreference(userId: string) {
  if (!db) {
    return null;
  }

  const snapshot = await getDoc(doc(db, 'users', userId));
  const theme = snapshot.data()?.preferences?.theme;
  return theme === 'light' || theme === 'dark' ? theme : null;
}

export async function saveUserThemePreference(userId: string, theme: 'light' | 'dark') {
  if (!db) {
    return;
  }

  await setDoc(
    doc(db, 'users', userId),
    {
      preferences: { theme },
      updatedAt: serverTimestamp(),
    },
    { merge: true }
  );
}
