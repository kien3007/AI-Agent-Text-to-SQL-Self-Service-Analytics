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
  Sparkles,
} from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, isLoading } = useAuth();
  const { theme, setTheme } = useTheme();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
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
      setError('Vui lòng nhập đầy đủ tên tài khoản và mật khẩu.');
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

  const handleQuickFill = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
    setError(null);
  };

  return (
    <div className="min-h-screen w-full flex flex-col justify-center items-center bg-[var(--bg-app)] text-[var(--text-primary)] px-4 py-8 relative overflow-hidden selection:bg-blue-500 selection:text-white">
      {/* Decorative ambient background glows */}
      <div className="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] rounded-full bg-blue-500/10 dark:bg-blue-600/15 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] rounded-full bg-indigo-500/10 dark:bg-purple-600/15 blur-[120px] pointer-events-none" />

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
          <div className="inline-flex items-center justify-center gap-2.5 px-3 py-1.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-card)] mb-4 shadow-xs">
            <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[11px] font-semibold tracking-wide uppercase text-[var(--text-secondary)]">
              Multi-Agent Enterprise Analytics
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--text-primary)]">
            Đăng nhập hệ thống
          </h1>
          <p className="mt-2 text-xs sm:text-sm text-[var(--text-muted)] max-w-sm mx-auto">
            Truy cập Sana AI Text-to-SQL Self-Service Analytics với Apache Doris 2.0 & LLM kép
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

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {/* Username Input */}
            <div>
              <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5">
                Tài khoản đăng nhập
              </label>
              <div className="relative">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none">
                  <User size={16} />
                </div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Nhập username (ví dụ: admin, analyst)"
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
              disabled={isSubmitting || isSuccess}
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
                  <span>Đang xác thực...</span>
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
              Chọn nhanh tài khoản mẫu:
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
                Đăng ký ngay
                <ArrowRight size={12} />
              </Link>
            </p>
          </div>
        </div>

        {/* Footer Meta */}
        <div className="mt-6 flex items-center justify-center gap-4 text-[11px] text-[var(--text-muted)]">
          <span className="flex items-center gap-1">
            <Lock size={12} />
            JWT RBAC Secured
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <Database size={12} />
            Apache Doris OLAP
          </span>
        </div>
      </div>
    </div>
  );
}
