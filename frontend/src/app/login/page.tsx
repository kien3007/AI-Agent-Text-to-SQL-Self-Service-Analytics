'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/components/ThemeProvider';
import {
  Lock,
  User,
  Key,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  Database,
  ShieldCheck,
  Zap,
  Sun,
  Moon,
  ArrowRight,
  Server,
} from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const { login, loginWithOAuth, isAuthenticated, isLoading } = useAuth();
  const { theme, setTheme } = useTheme();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isOAuthSubmitting, setIsOAuthSubmitting] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    // Prefetch for zero-latency instant transitions
    router.prefetch('/');
    router.prefetch('/register');

    if (!isLoading && isAuthenticated) {
      router.replace('/');
    }
  }, [isAuthenticated, isLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError('Vui lòng nhập đầy đủ tên tài khoản/email và mật khẩu.');
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      await login(username.trim(), password);
      setIsSuccess(true);
      router.replace('/');
    } catch (err: any) {
      setError(err?.message || 'Tên đăng nhập hoặc mật khẩu không chính xác.');
      setIsSubmitting(false);
    }
  };

  const handleOAuthLogin = async (provider: 'google' | 'github') => {
    setError(null);
    setIsOAuthSubmitting(provider);
    try {
      await loginWithOAuth(provider);
    } catch (err: any) {
      setError(err?.message || `Đăng nhập qua ${provider} thất bại.`);
      setIsOAuthSubmitting(null);
    }
  };

  const handleQuickFill = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
    setError(null);
  };

  return (
    <div className="min-h-screen w-full flex flex-col justify-center items-center bg-[var(--bg-app)] text-[var(--text-primary)] px-4 py-8 relative overflow-hidden selection:bg-blue-500 selection:text-white">
      {/* Decorative ambient background glows */}
      <div className="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] rounded-full bg-emerald-500/10 dark:bg-emerald-600/15 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] rounded-full bg-blue-500/10 dark:bg-blue-600/15 blur-[120px] pointer-events-none" />

      {/* Top right theme toggle */}
      <div className="absolute top-6 right-6 z-20">
        {mounted && (
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="w-9 h-9 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-medium)] transition-all shadow-xs"
            title="Chuyển chế độ Giao diện"
          >
            {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-zinc-600" />}
          </button>
        )}
      </div>

      {/* Card Container */}
      <div className="w-full max-w-md z-10 animate-in fade-in zoom-in-95 duration-300">
        {/* Brand Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center gap-2 px-3 py-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 mb-4 shadow-xs">
            <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[11px] font-semibold tracking-wide uppercase">
              Supabase Auth Self-Hosted
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--text-primary)]">
            Đăng nhập hệ thống
          </h1>
          <p className="mt-2 text-xs sm:text-sm text-[var(--text-muted)] max-w-sm mx-auto">
            Truy cập Sana AI Text-to-SQL Self-Service Analytics với DuckDB OLAP & LLM kép
          </p>
        </div>

        {/* Login Box */}
        <div className="p-6 sm:p-8 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-[var(--shadow-float)] backdrop-blur-md">
          {error && (
            <div className="mb-5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs flex items-start gap-2.5 animate-in slide-in-from-top-2 duration-200">
              <AlertCircle size={16} className="shrink-0 mt-0.5" />
              <div className="flex-1 font-medium">{error}</div>
            </div>
          )}

          {/* Social OAuth Buttons */}
          <div className="grid grid-cols-2 gap-3 mb-5">
            <button
              type="button"
              onClick={() => handleOAuthLogin('github')}
              disabled={isSubmitting || !!isOAuthSubmitting}
              className="py-2.5 px-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-app)] hover:border-[var(--border-medium)] hover:bg-[var(--bg-hover)] text-xs font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-50 cursor-pointer"
            >
              {isOAuthSubmitting === 'github' ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                  <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                </svg>
              )}
              <span>GitHub</span>
            </button>

            <button
              type="button"
              onClick={() => handleOAuthLogin('google')}
              disabled={isSubmitting || !!isOAuthSubmitting}
              className="py-2.5 px-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-app)] hover:border-[var(--border-medium)] hover:bg-[var(--bg-hover)] text-xs font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-50 cursor-pointer"
            >
              {isOAuthSubmitting === 'google' ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <svg className="w-4 h-4" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                </svg>
              )}
              <span>Google</span>
            </button>
          </div>

          <div className="relative mb-5 flex items-center justify-center">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[var(--border-subtle)]" />
            </div>
            <span className="relative px-3 bg-[var(--bg-card)] text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-medium">
              hoặc đăng nhập bằng tài khoản
            </span>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {/* Username / Email Input */}
            <div>
              <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5">
                Tài khoản hoặc Email
              </label>
              <div className="relative">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none">
                  <User size={16} />
                </div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Nhập email hoặc username (ví dụ: admin, analyst)"
                  autoComplete="username"
                  required
                  className="w-full pl-10 pr-3.5 py-2.5 text-sm rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-app)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                />
              </div>
            </div>

            {/* Password Input */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold text-[var(--text-secondary)]">
                  Mật khẩu
                </label>
              </div>
              <div className="relative">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none">
                  <Key size={16} />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                  className="w-full pl-10 pr-10 py-2.5 text-sm rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-app)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-1"
                  tabIndex={-1}
                  title={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting || isSuccess || !!isOAuthSubmitting}
              className={`mt-2 w-full py-2.5 px-4 rounded-xl text-sm font-semibold transition-all flex items-center justify-center gap-2 shadow-sm cursor-pointer ${
                isSuccess
                  ? 'bg-emerald-600 text-white'
                  : 'bg-[var(--accent-primary)] text-[var(--accent-primary-text)] hover:bg-[var(--accent-primary-hover)] active:scale-[0.99] disabled:opacity-60 disabled:cursor-not-allowed'
              }`}
            >
              {isSuccess ? (
                <>
                  <ShieldCheck size={16} />
                  <span>Đăng nhập thành công!</span>
                </>
              ) : isSubmitting ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>Đang xác thực Supabase...</span>
                </>
              ) : (
                <>
                  <span>Đăng nhập</span>
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Credentials */}
          <div className="mt-6 pt-5 border-t border-[var(--border-subtle)]">
            <span className="text-[11px] font-medium text-[var(--text-muted)] block mb-2 text-center">
              Tài khoản tích hợp sẵn:
            </span>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => handleQuickFill('admin', 'admin123')}
                className="px-2.5 py-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] hover:border-blue-500 hover:bg-blue-500/5 text-left text-xs transition-colors flex flex-col cursor-pointer"
              >
                <div className="flex items-center gap-1 font-semibold text-[var(--text-primary)]">
                  <ShieldCheck size={12} className="text-blue-500" />
                  <span>admin</span>
                </div>
                <span className="text-[10px] text-[var(--text-muted)]">Quyền Administrator</span>
              </button>

              <button
                type="button"
                onClick={() => handleQuickFill('analyst', 'analyst123')}
                className="px-2.5 py-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] hover:border-emerald-500 hover:bg-emerald-500/5 text-left text-xs transition-colors flex flex-col cursor-pointer"
              >
                <div className="flex items-center gap-1 font-semibold text-[var(--text-primary)]">
                  <Zap size={12} className="text-emerald-500" />
                  <span>analyst</span>
                </div>
                <span className="text-[10px] text-[var(--text-muted)]">Quyền Data Analyst</span>
              </button>
            </div>
          </div>

          {/* Link to Register */}
          <div className="mt-5 text-center">
            <p className="text-xs text-[var(--text-muted)]">
              Chưa có tài khoản?{' '}
              <Link
                href="/register"
                className="font-semibold text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-0.5"
              >
                Đăng ký tài khoản
                <ArrowRight size={12} />
              </Link>
            </p>
          </div>
        </div>

        {/* Footer Meta */}
        <div className="mt-6 flex items-center justify-center gap-4 text-[11px] text-[var(--text-muted)]">
          <span className="flex items-center gap-1">
            <Server size={12} />
            Supabase GoTrue Engine
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <Lock size={12} />
            HS256 Verified
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <Database size={12} />
            DuckDB OLAP
          </span>
        </div>
      </div>
    </div>
  );
}
