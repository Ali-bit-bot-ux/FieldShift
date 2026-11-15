"use client";
import { motion, useReducedMotion } from "motion/react";
import { usePlanner } from "./Store";
export function Transition({ children }: { children: React.ReactNode }) {
  const reduced = useReducedMotion();
  const { hydrated } = usePlanner();
  return (
    <motion.div
      initial={hydrated && !reduced ? { opacity: 0.4, y: 4 } : false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduced ? 0 : 0.18 }}
    >
      {children}
    </motion.div>
  );
}
