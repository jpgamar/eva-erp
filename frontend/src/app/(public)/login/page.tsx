"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, LockKeyhole } from "lucide-react";
import { login } from "@/lib/api/auth";
import { EvaMark } from "@/components/eva-mark";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await login(email, password);
      router.push("/dashboard?welcome=1");
    } catch {
      setError("Invalid email or password");
      setPassword("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(56,189,248,0.18),transparent_50%),radial-gradient(circle_at_80%_80%,rgba(20,184,166,0.14),transparent_45%)]" />
        <div className="absolute inset-0 opacity-20 [background-image:linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:48px_48px]" />
      </div>

      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-6xl items-center px-4 py-10 sm:px-8">
        <div className="grid w-full animate-erp-entrance overflow-hidden rounded-3xl border border-white/10 bg-white/[0.04] shadow-[0_24px_80px_rgba(0,0,0,0.45)] backdrop-blur-sm lg:grid-cols-5">
          <div className="hidden border-r border-white/10 p-10 text-white lg:col-span-2 lg:flex lg:flex-col lg:justify-between">
            <div>
              <EvaMark className="h-10 w-auto opacity-95" />
              <h1 className="mt-6 text-3xl font-bold tracking-tight">EVA ERP</h1>
              <p className="mt-3 text-sm text-slate-300">
                Internal command center for goeva.ai operations.
              </p>
            </div>
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm text-slate-200">
                <ShieldCheck className="h-4 w-4 text-sky-300" />
                <span>Protected company workflows</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-slate-200">
                <LockKeyhole className="h-4 w-4 text-teal-300" />
                <span>Secure access for authorized team members</span>
              </div>
            </div>
          </div>

          <div className="bg-white p-7 sm:p-10 lg:col-span-3">
            <div className="mx-auto w-full max-w-md">
              <div className="mb-7">
                <div className="mb-3 flex items-center gap-2 lg:hidden">
                  <EvaMark className="h-7 w-auto" />
                  <span className="text-sm font-semibold text-slate-800">EVA ERP</span>
                </div>
                <h2 className="text-2xl font-bold tracking-tight text-slate-900">Sign in</h2>
                <p className="mt-1 text-sm text-slate-500">Use your EVA workspace credentials.</p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                {error && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                  </div>
                )}

                <div className="space-y-1.5">
                  <label htmlFor="email" className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    placeholder="you@goeva.ai"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoFocus
                    className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 transition-all focus:border-sky-400 focus:shadow-[0_0_0_4px_rgba(56,189,248,0.16)] focus:outline-none"
                  />
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="password" className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Password
                  </label>
                  <input
                    id="password"
                    type="password"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 transition-all focus:border-sky-400 focus:shadow-[0_0_0_4px_rgba(56,189,248,0.16)] focus:outline-none"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition-all hover:bg-slate-800 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                      Signing in...
                    </span>
                  ) : (
                    "Sign in"
                  )}
                </button>
              </form>

              <div className="mt-6 flex items-center justify-between border-t border-slate-100 pt-4 text-[11px] text-slate-400">
                <span>Internal operations for goeva.ai</span>
                <span className="inline-flex items-center gap-1">
                  <EvaMark className="h-3 w-auto opacity-50" />
                  Powered by Eva AI
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
