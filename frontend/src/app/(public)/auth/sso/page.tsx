"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";

function SSOHandler() {
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setError("No SSO token provided");
      return;
    }

    // Redirect to the backend SSO endpoint which validates the token,
    // sets session cookies, and 307-redirects to /dashboard.
    window.location.href = `/api/v1/auth/sso?token=${encodeURIComponent(token)}`;
  }, [params]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <h1 className="text-xl font-semibold">SSO Error</h1>
          <p className="mt-2 text-muted-foreground">{error}</p>
          <a href="/login" className="mt-4 inline-block text-primary underline">
            Go to login
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-muted-foreground">Signing you in...</p>
    </div>
  );
}

export default function SSOPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <p className="text-muted-foreground">Loading...</p>
        </div>
      }
    >
      <SSOHandler />
    </Suspense>
  );
}
