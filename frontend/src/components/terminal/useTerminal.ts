"use client";

import { createContext, useContext } from "react";

export interface TerminalContextValue {
  isOpen: boolean;
  toggle: () => void;
  open: () => void;
  close: () => void;
}

export const TerminalContext = createContext<TerminalContextValue>({
  isOpen: false,
  toggle: () => {},
  open: () => {},
  close: () => {},
});

export function useTerminal() {
  return useContext(TerminalContext);
}
