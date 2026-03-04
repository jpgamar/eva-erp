"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { AlertTriangle, ExternalLink, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const EVA_SIDEBAR_WIDTH_PX = 72;
const BOOTSTRAP_DELAY_MS = 1200;
const FRAME_READY_FALLBACK_MS = 3000;

interface EvaEmbedPayload {
  embedUrl: string | null;
  bootstrapUrl: string | null;
  manualUrl: string;
  agentId: string | null;
  warning?: string | null;
  detail?: string | null;
  error?: string | null;
}

function LoadingOverlay() {
  return (
    <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/75 backdrop-blur-[1px]">
      <div className="flex items-center gap-3 rounded-lg border bg-background px-4 py-2 text-sm text-muted-foreground shadow-sm">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        Loading Eva workspace...
      </div>
    </div>
  );
}

export default function AssistantPage() {
  const [payload, setPayload] = useState<EvaEmbedPayload | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [phase, setPhase] = useState<"bootstrap" | "final" | null>(null);
  const [frameSrc, setFrameSrc] = useState<string | null>(null);
  const [frameReady, setFrameReady] = useState(false);
  const [loadCount, setLoadCount] = useState(0);
  const runIdRef = useRef(0);

  const resetFrameState = useCallback(() => {
    setPhase(null);
    setFrameSrc(null);
    setFrameReady(false);
    setLoadCount(0);
  }, []);

  const fetchEmbed = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    resetFrameState();
    runIdRef.current += 1;
    const runId = runIdRef.current;

    try {
      const response = await fetch("/api/eva/embed", {
        method: "GET",
        cache: "no-store",
      });
      const data = (await response.json()) as EvaEmbedPayload;
      setPayload(data);

      if (!response.ok) {
        throw new Error(data.detail || data.error || "Failed to load EVA embed");
      }

      if (data.embedUrl && data.bootstrapUrl) {
        setPhase("bootstrap");
        setFrameSrc(data.bootstrapUrl);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load EVA embed";
      setErrorMessage(message);
    } finally {
      if (runId === runIdRef.current) {
        setIsLoading(false);
      }
    }
  }, [resetFrameState]);

  useEffect(() => {
    fetchEmbed();
  }, [fetchEmbed]);

  useEffect(() => {
    if (phase !== "bootstrap" || !payload?.embedUrl) return;
    const timer = window.setTimeout(() => {
      setPhase("final");
      setFrameSrc(payload.embedUrl);
    }, BOOTSTRAP_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [phase, payload?.embedUrl]);

  useEffect(() => {
    if (!frameSrc || frameReady) return;
    const timer = window.setTimeout(() => {
      setFrameReady(true);
    }, FRAME_READY_FALLBACK_MS);
    return () => window.clearTimeout(timer);
  }, [frameSrc, frameReady, loadCount]);

  const handleFrameLoad = useCallback(() => {
    setLoadCount((current) => {
      const next = current + 1;
      if (next >= 2) {
        setFrameReady(true);
      }
      return next;
    });
  }, []);

  const warning = payload?.warning || null;
  const showStateCard = !isLoading && Boolean(errorMessage || warning || !frameSrc);
  const manualUrl = payload?.manualUrl || "https://app.goeva.ai/auth/login?redirect=%2Finbox";
  const canRetry = !isLoading;
  const stateTitle = useMemo(() => {
    if (errorMessage) return "Could not open EVA";
    if (warning) return "EVA credentials not configured";
    return "Preparing EVA workspace";
  }, [errorMessage, warning]);

  if (isLoading && !frameSrc) {
    return (
      <div className="relative h-[calc(100vh-8rem)] overflow-hidden rounded-xl border bg-white">
        <LoadingOverlay />
      </div>
    );
  }

  if (showStateCard) {
    return (
      <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center">
        <Card className="w-full max-w-xl border-amber-200/70 bg-amber-50/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              {stateTitle}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              {errorMessage ||
                "Set EVA shared credentials in environment variables and retry this page."}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline" size="sm">
                <a href={manualUrl} target="_blank" rel="noopener noreferrer">
                  Open EVA manually
                  <ExternalLink className="ml-1 h-3.5 w-3.5" />
                </a>
              </Button>
              <Button onClick={fetchEmbed} disabled={!canRetry} size="sm">
                <RefreshCw className="mr-1 h-3.5 w-3.5" />
                Retry
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const frameStyle: CSSProperties = {
    width: `calc(100% + ${EVA_SIDEBAR_WIDTH_PX}px)`,
    marginLeft: `-${EVA_SIDEBAR_WIDTH_PX}px`,
    height: "100%",
    border: "0",
    display: "block",
  };

  return (
    <div className="relative h-[calc(100vh-8rem)] overflow-hidden rounded-xl border bg-white">
      {(!frameReady || isLoading) && <LoadingOverlay />}
      <iframe
        key={frameSrc}
        src={frameSrc || undefined}
        title="Eva Embedded Workspace"
        onLoad={handleFrameLoad}
        style={frameStyle}
        allow="clipboard-read; clipboard-write"
      />
    </div>
  );
}
