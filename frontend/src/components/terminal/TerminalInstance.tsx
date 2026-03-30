"use client";

import { useEffect, useRef, useCallback } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import "@xterm/xterm/css/xterm.css";

const TERMINAL_THEME = {
  background: "#0f1117",
  foreground: "#e0e0e0",
  cursor: "#60a5fa",
  cursorAccent: "#0f1117",
  selectionBackground: "#3b82f680",
  black: "#1a1a2e",
  red: "#ef4444",
  green: "#22c55e",
  yellow: "#eab308",
  blue: "#3b82f6",
  magenta: "#a855f7",
  cyan: "#06b6d4",
  white: "#e0e0e0",
  brightBlack: "#6b7280",
  brightRed: "#f87171",
  brightGreen: "#4ade80",
  brightYellow: "#facc15",
  brightBlue: "#60a5fa",
  brightMagenta: "#c084fc",
  brightCyan: "#22d3ee",
  brightWhite: "#f9fafb",
};

function getWsUrl(): string {
  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL?.replace(/\/api\/v1\/?$/, "") ||
    "http://localhost:8000";
  // Strip any trailing whitespace/newlines from env vars
  const clean = backendUrl.trim();
  return clean.replace(/^http/, "ws") + "/ws/terminal";
}

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

interface TerminalInstanceProps {
  visible: boolean;
}

export function TerminalInstance({ visible }: TerminalInstanceProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(false);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    const term = termRef.current;
    if (!term) return;

    const url = getWsUrl();
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      const token = getCookie("erp_access_token");
      if (token) {
        ws.send(JSON.stringify({ type: "auth", token }));
      } else {
        term.writeln("\r\n\x1b[31mNo auth token found. Please log in again.\x1b[0m");
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "output" && msg.data) {
          const bytes = Uint8Array.from(atob(msg.data), (c) => c.charCodeAt(0));
          term.write(bytes);
        } else if (msg.type === "ready") {
          // Session established
        } else if (msg.type === "exit") {
          term.writeln(`\r\n\x1b[33m[Process exited with code ${msg.code ?? "?"}]\x1b[0m`);
        } else if (msg.type === "error") {
          term.writeln(`\r\n\x1b[31mError: ${msg.message}\x1b[0m`);
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = (event) => {
      if (event.code === 4403) {
        term.writeln("\r\n\x1b[31mAccess denied.\x1b[0m");
        return;
      }
      if (event.code === 4401) {
        term.writeln("\r\n\x1b[31mAuthentication failed.\x1b[0m");
        return;
      }
      // Auto-reconnect after 2 seconds
      if (mountedRef.current) {
        reconnectTimer.current = setTimeout(() => connect(), 2000);
      }
    };

    ws.onerror = () => {
      // onclose will fire after this
    };
  }, []);

  // Initialize terminal once
  useEffect(() => {
    mountedRef.current = true;
    const container = containerRef.current;
    if (!container || termRef.current) return;

    const term = new Terminal({
      theme: TERMINAL_THEME,
      fontSize: 13,
      fontFamily: "'SF Mono', 'Fira Code', 'Cascadia Code', Menlo, monospace",
      cursorBlink: true,
      cursorStyle: "block",
      scrollback: 10000,
      allowProposedApi: true,
    });

    const fit = new FitAddon();
    term.loadAddon(fit);
    term.loadAddon(new WebLinksAddon());

    term.open(container);
    fit.fit();

    termRef.current = term;
    fitRef.current = fit;

    // Forward terminal input to WebSocket
    term.onData((data) => {
      const ws = wsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "input", data: btoa(data) }));
      }
    });

    // Connect WebSocket
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      term.dispose();
      termRef.current = null;
      fitRef.current = null;
    };
  }, [connect]);

  // Fit terminal when visibility changes or container resizes
  useEffect(() => {
    if (!visible || !fitRef.current) return;

    // Small delay to let CSS transitions finish
    const timer = setTimeout(() => {
      fitRef.current?.fit();
      // Send resize to server
      const term = termRef.current;
      const ws = wsRef.current;
      if (term && ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
      }
    }, 50);

    const observer = new ResizeObserver(() => {
      fitRef.current?.fit();
      const term = termRef.current;
      const ws = wsRef.current;
      if (term && ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
      }
    });

    if (containerRef.current) observer.observe(containerRef.current);

    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, [visible]);

  return (
    <div
      ref={containerRef}
      className="h-full w-full"
      style={{ display: visible ? "block" : "none" }}
    />
  );
}
