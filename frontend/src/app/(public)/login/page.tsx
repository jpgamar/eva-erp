"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#f5f5f7]">
      {/* Ambient blur orbs */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-1/3 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/60 blur-[120px]" />
        <div className="absolute bottom-0 left-1/4 h-[300px] w-[400px] rounded-full bg-gray-200/40 blur-[100px]" />
        <div className="absolute right-1/4 top-1/4 h-[250px] w-[350px] rounded-full bg-gray-300/20 blur-[80px]" />
      </div>

      {/* Glassmorphic card */}
      <div className="relative z-10 w-full max-w-[420px] animate-erp-entrance rounded-2xl border border-white/80 bg-white/90 p-8 shadow-[0_1px_2px_rgba(0,0,0,0.04),0_4px_12px_rgba(0,0,0,0.04),0_16px_40px_rgba(0,0,0,0.06)] backdrop-blur-xl">
        {/* Logo */}
        <div className="mb-6 flex flex-col items-center gap-3">
          <EvaMark className="h-10 w-auto" />
          <h1 className="text-xl font-bold text-gray-900">EVA ERP</h1>
          <div className="h-px w-12 bg-gray-200" />
          <p className="text-xs text-gray-400">Internal operations for goeva.ai</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600 ring-1 ring-red-200">
              {error}
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="email" className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
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
              className="w-full rounded-xl border border-gray-200/80 bg-gray-50/80 px-4 py-3 text-sm text-gray-900 placeholder:text-gray-400 transition-all focus:border-gray-300 focus:bg-white focus:shadow-[0_0_0_3px_rgba(0,0,0,0.04)] focus:outline-none"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
              Password
            </label>
            <input
              id="password"
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full rounded-xl border border-gray-200/80 bg-gray-50/80 px-4 py-3 text-sm text-gray-900 placeholder:text-gray-400 transition-all focus:border-gray-300 focus:bg-white focus:shadow-[0_0_0_3px_rgba(0,0,0,0.04)] focus:outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-gray-900 px-4 py-3 text-sm font-medium text-white transition-all hover:bg-gray-800 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
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

        {/* Powered by Eva */}
        <div className="mt-6 flex items-center justify-center gap-1.5 text-[11px] text-gray-400">
          <EvaMark className="h-3 w-auto opacity-40" />
          <span>Powered by Eva AI</span>
        </div>
      </div>
    </div>
  );
}
