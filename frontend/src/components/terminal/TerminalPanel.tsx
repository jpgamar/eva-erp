"use client";

import { useState, useCallback, useEffect, type ReactNode } from "react";
import { X, Terminal as TerminalIcon, Minus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { TerminalContext } from "./useTerminal";
import { TerminalInstance } from "./TerminalInstance";

interface TerminalProviderProps {
  children: ReactNode;
}

export function TerminalProvider({ children }: TerminalProviderProps) {
  const [isOpen, setIsOpen] = useState(false);

  const toggle = useCallback(() => setIsOpen((v) => !v), []);
  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);

  // Ctrl+` keyboard shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === "`") {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [toggle]);

  return (
    <TerminalContext.Provider value={{ isOpen, toggle, open, close }}>
      {children}
      <TerminalOverlay isOpen={isOpen} onClose={close} />
    </TerminalContext.Provider>
  );
}

interface TerminalOverlayProps {
  isOpen: boolean;
  onClose: () => void;
}

function TerminalOverlay({ isOpen, onClose }: TerminalOverlayProps) {
  const [minimized, setMinimized] = useState(false);

  return (
    <div
      className={cn(
        "fixed top-0 right-0 z-50 flex h-screen flex-col border-l border-border/50 bg-[#0f1117] shadow-2xl transition-transform duration-300 ease-in-out",
        "w-[520px]",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      {/* Header */}
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-white/10 px-3">
        <div className="flex items-center gap-2">
          <TerminalIcon className="h-3.5 w-3.5 text-green-400" />
          <span className="text-xs font-medium text-gray-300">Terminal</span>
          <span className="h-1.5 w-1.5 rounded-full bg-green-500" title="Connected" />
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-gray-400 hover:text-white hover:bg-white/10"
            onClick={() => setMinimized((v) => !v)}
          >
            <Minus className="h-3 w-3" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-gray-400 hover:text-white hover:bg-white/10"
            onClick={onClose}
          >
            <X className="h-3 w-3" />
          </Button>
        </div>
      </div>

      {/* Terminal area */}
      <div className={cn("flex-1 min-h-0 p-1", minimized && "hidden")}>
        <TerminalInstance visible={isOpen && !minimized} />
      </div>
    </div>
  );
}
