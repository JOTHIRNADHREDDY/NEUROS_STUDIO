'use client';
import { motion } from 'motion/react';
import { useEffect, useState } from 'react';

export default function TelemetryBackground() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none bg-white dark:bg-[#050608]">
      {/* Grid Pattern */}
      <div 
        className="absolute inset-0 opacity-[0.06]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(0, 229, 255, 0.12) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 229, 255, 0.12) 1px, transparent 1px)
          `,
          backgroundSize: '20px 20px'
        }}
      />

      {/* Grid Pulse overlay */}
      <motion.div
        className="absolute inset-0 bg-gradient-to-b from-transparent via-[#00f2ff]/3 to-transparent"
        animate={{
          y: ['-100%', '200%']
        }}
        transition={{
          duration: 10,
          repeat: Infinity,
          ease: "linear"
        }}
      />

      {/* Subtle nodes */}
      {Array.from({ length: 15 }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-1 h-1 bg-[#00f2ff] shadow-[0_0_8px_2px_rgba(0,242,255,0.18)] rounded-md"
          initial={{
            x: `${(i * 17) % 100}vw`,
            y: `${(i * 23) % 100}vh`,
            opacity: 0.06
          }}
          animate={{
            y: [null, `${((i + 5) * 31) % 100}vh`],
            opacity: [0.06, 0.18, 0.06]
          }}
          transition={{
            duration: (i % 10) + 10,
            repeat: Infinity,
            ease: "linear"
          }}
        />
      ))}
    </div>
  );
}
