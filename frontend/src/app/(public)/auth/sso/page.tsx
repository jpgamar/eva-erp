"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useState, Suspense } from "react";

function SSOHandler() {
  const params = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setError("No SSO token provided");
      return;
    }

    fetch(`/api/v1/auth/sso?token=${encodeURIComponent(token)}`, {
      credentials: "include",
    })
      .then((res) => {
        if (!res.ok) throw new Error("SSO failed");
        return res.json();
      })
      .then((data) => {
        if (data.name) sessionStorage.setItem("welcomeName", data.name);
        router.push("/dashboard");
      })
      .catch(() => {
        setError("SSO authentication failed");
      });
  }, [params, router]);

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
