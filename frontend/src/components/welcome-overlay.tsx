"use client";

import { useState, useEffect } from "react";
import { EvaMark } from "@/components/eva-mark";

export function WelcomeOverlay() {
  const [userName, setUserName] = useState<string | null>(null);
  const [show, setShow] = useState(false);
  const [phase, setPhase] = useState<"hidden" | "logo" | "greeting" | "footer" | "exit" | "done">("hidden");

  useEffect(() => {
    const name = sessionStorage.getItem("welcomeName");
    if (!name) return;
    sessionStorage.removeItem("welcomeName");
    setUserName(name);
    setShow(true);

    const timers = [
      setTimeout(() => setPhase("logo"), 50),
      setTimeout(() => setPhase("greeting"), 600),
      setTimeout(() => setPhase("footer"), 1400),
      setTimeout(() => setPhase("exit"), 3200),
      setTimeout(() => { setShow(false); setPhase("done"); }, 4000),
    ];

    return () => timers.forEach(clearTimeout);
  }, []);

  if (!show || !userName) return null;

  const stages = ["logo", "greeting", "footer", "exit"] as const;
  const stageIndex = stages.indexOf(phase as typeof stages[number]);
  const visible = (minStage: number) => stageIndex >= minStage;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transition: "opacity 700ms ease-out",
        opacity: phase === "exit" ? 0 : 1,
      }}
    >
      {/* Background */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundColor: "#f5f5f7",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: "33%",
            width: 600,
            height: 600,
            transform: "translate(-50%, -50%)",
            borderRadius: "50%",
            background: "rgba(255,255,255,0.7)",
            filter: "blur(120px)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: "25%",
            width: 400,
            height: 300,
            borderRadius: "50%",
            background: "rgba(229,231,235,0.4)",
            filter: "blur(100px)",
          }}
        />
      </div>

      {/* Content */}
      <div
        style={{
          position: "relative",
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 32,
          padding: "0 24px",
          textAlign: "center",
        }}
      >
        {/* Logo */}
        <div
          style={{
            transition: "opacity 700ms ease-out, transform 700ms ease-out",
            opacity: visible(0) ? 1 : 0,
            transform: visible(0) ? "translateY(0) scale(1)" : "translateY(12px) scale(0.95)",
          }}
        >
          <EvaMark className="h-20 w-auto" />
        </div>

        {/* Greeting */}
        <h1
          style={{
            margin: 0,
            fontSize: 28,
            fontWeight: 400,
            letterSpacing: "-0.01em",
            color: "#111827",
            transition: "opacity 700ms ease-out, transform 700ms ease-out",
            opacity: visible(1) ? 1 : 0,
            transform: visible(1) ? "translateY(0)" : "translateY(16px)",
          }}
        >
          Welcome, {userName}
        </h1>

        {/* Powered by Eva */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            transition: "opacity 600ms ease-out",
            opacity: visible(2) ? 0.6 : 0,
          }}
        >
          <span style={{ fontSize: 11, color: "#9ca3af" }}>Powered by</span>
          <EvaMark className="h-3 w-auto" />
          <span style={{ fontSize: 11, fontWeight: 600, color: "#9ca3af" }}>eva</span>
        </div>
      </div>
    </div>
  );
}
