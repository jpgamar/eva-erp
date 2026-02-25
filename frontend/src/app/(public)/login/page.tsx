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
      setError("Correo o contrasena invalidos");
      setPassword("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="flex min-h-screen items-center justify-center px-4 py-12"
      style={{ background: "linear-gradient(160deg, #e8ecf4 0%, #f0f2f7 30%, #eef0f6 60%, #e6eaf3 100%)" }}
    >
      <div className="w-full max-w-[460px]">
        <div
          className="rounded-2xl bg-white px-10 pb-10 pt-10 sm:px-12"
          style={{ boxShadow: "0 4px 24px rgba(0, 0, 0, 0.06)" }}
        >
          <div className="mb-12 flex flex-col items-center">
            <div className="flex items-center gap-3">
              <EvaMark className="h-11 w-auto" />
              <span className="text-[26px] font-semibold tracking-[-0.02em] text-gray-900">
                EvaAI <span className="font-normal text-gray-400">ERP</span>
              </span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <label htmlFor="email" className="block text-[11px] font-semibold uppercase tracking-[0.1em] text-gray-400">
                Correo
              </label>
              <input
                id="email"
                type="email"
                placeholder="tu@ejemplo.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                className="h-12 w-full rounded-xl border-0 bg-[#edf0f8] px-4 text-[15px] text-gray-900 outline-none transition-colors placeholder:text-gray-300 focus:bg-[#e5e9f4]"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="block text-[11px] font-semibold uppercase tracking-[0.1em] text-gray-400">
                Contrasena
              </label>
              <input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="h-12 w-full rounded-xl border-0 bg-[#edf0f8] px-4 text-[15px] text-gray-900 outline-none transition-colors placeholder:text-gray-300 focus:bg-[#e5e9f4]"
              />
            </div>

            {error && (
              <div className="rounded-xl bg-red-50 px-4 py-3 text-[13px] text-red-500">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="flex h-12 w-full items-center justify-center rounded-xl text-[15px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{ background: "linear-gradient(135deg, #111827 0%, #1f2937 100%)" }}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Iniciando sesion...
                </span>
              ) : (
                "Iniciar sesion"
              )}
            </button>
          </form>
        </div>

        <div className="mt-6 flex items-center justify-center gap-1.5">
          <EvaMark className="h-3 w-auto opacity-50" />
          <span className="text-[12px] text-gray-400">Powered by Eva AI</span>
        </div>
      </div>
    </div>
  );
}
