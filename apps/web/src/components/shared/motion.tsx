import { MotionConfig, motion } from "motion/react";
import type { ReactNode } from "react";

/** Honour the OS "reduce motion" setting for every animation in the app. */
export function MotionProvider({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

/** Restrained entrance: a short fade + 6px rise. Re-keyed by the caller when content changes. */
export function Rise({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: [0.2, 0.7, 0.2, 1] }}
    >
      {children}
    </motion.div>
  );
}
