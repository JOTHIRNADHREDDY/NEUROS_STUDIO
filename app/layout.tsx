import type {Metadata} from 'next';
import {Inter, IBM_Plex_Mono} from 'next/font/google';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
});

const ibmPlexMono = IBM_Plex_Mono({
  weight: ['400', '500', '600', '700'],
  subsets: ['latin'],
  variable: '--font-mono',
});

export const metadata: Metadata = {
  title: 'NEUROS Studio',
  description: 'Robotics OS for Intelligent Machines',
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en" className={`${inter.variable} ${ibmPlexMono.variable} dark`}>
      <body className="bg-[#050608] text-white font-sans antialiased selection:bg-[#00f2ff] selection:text-black" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
