'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/components/ThemeProvider';
import {
  UserPlus,
  User,
  Key,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  CheckCircle2,
  Sun,
  Moon,
  ArrowRight,
  ShieldCheck,
  Check,
} from 'lucide-react';

export default function RegisterPage() {
  const router = useRouter();
  const { register, isAuthenticated, isLoading } = useAuth();
  const { theme, setTheme } = useTheme();

  const [displayName, setDisplayName] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    // Prefetch for zero-latency instant transitions
    router.prefetch('/');
    router.prefetch('/login');

    if (!isLoading && isAuthenticated) {
      router.replace('/');
    }
  }, [isAuthenticated, isLoading, router]);

  // Real-time validations
  const isLengthValid = password.length >= 6;
  const isPasswordMatch = password.length > 0 && password === confirmPassword;
  const isUsernameValid = username.trim().length >= 3;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!isUsernameValid) {
      setError('Tên đăng nhập phải có ít nhất 3 ký tự.');
      return;
    }

    if (!isLengthValid) {
      setError('Mật khẩu phải có ít nhất 6 ký tự.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Mật khẩu xác nhận không khớp.');
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      await register(username.trim(), password, displayName.trim());
      setIsSuccess(true);
      router.replace('/');
    } catch (err: any) {
      setError(err?.message || 'Đăng ký không thành công. Tên đăng nhập có thể đã tồn tại.');
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex flex-col justify-center items-center bg-[var(--bg-app)] text-[var(--text-primary)] px-4 py-8 relative overflow-hidden selection:bg-blue-500 selection:text-white">
      {/* Decorative ambient background glows */}
      <div className="absolute top-[-20%] right-[-10%] w-[500px] h-[500px] rounded-full bg-emerald-500/10 dark:bg-emerald-600/15 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] left-[-10%] w-[500px] h-[500px] rounded-full bg-blue-500/10 dark:bg-blue-600/15 blur-[120px] pointer-events-none" />

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
            <span className="flex h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
            <span className="text-[11px] font-semibold tracking-wide uppercase text-[var(--text-secondary)]">
              Tạo tài khoản mới
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--text-primary)]">
            Đăng ký tài khoản
          </h1>
          <p className="mt-2 text-xs sm:text-sm text-[var(--text-muted)] max-w-sm mx-auto">
            Trở thành Data Analyst với quyền truy vấn tự phục vụ thông minh trên Sana AI
          </p>
        </div>

        {/* Register Box */}
        <div className="p-6 sm:p-8 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-[var(--shadow-float)] backdrop-blur-md">
          {error && (
            <div className="mb-5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs flex items-start gap-2.5 animate-in slide-in-from-top-2 duration-200">
              <AlertCircle size={16} className="shrink-0 mt-0.5" />
              <div className="flex-1 font-medium">{error}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
            {/* Display Name Input */}
            <div>
              <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5">
                Họ và tên (Tên hiển thị)
              </label>
              <div className="relative">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none">
                  <User size={16} />
                </div>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Ví dụ: Nguyễn Văn A"
                  className="w-full pl-10 pr-3.5 py-2.5 text-sm rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-app)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                />
              </div>
            </div>

            {/* Username Input */}
            <div>
              <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5">
                Tên đăng nhập <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none">
                  <UserPlus size={16} />
                </div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value.toLowerCase().replace(/\s+/g, ''))}
                  placeholder="vi_du: analyst_hn"
                  autoComplete="username"
                  required
                  className="w-full pl-10 pr-3.5 py-2.5 text-sm rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-app)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all font-mono"
                />
              </div>
              <span className="text-[10px] text-[var(--text-muted)] mt-1 block">
                Tối thiểu 3 ký tự (chỉ gồm chữ cái, số hoặc dấu gạch dưới).
              </span>
            </div>

            {/* Password Input */}
            <div>
              <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5">
                Mật khẩu <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none">
                  <Key size={16} />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="new-password"
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

            {/* Confirm Password Input */}
            <div>
              <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5">
                Xác nhận lại mật khẩu <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none">
                  <ShieldCheck size={16} />
                </div>
                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="new-password"
                  required
                  className="w-full pl-10 pr-10 py-2.5 text-sm rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-app)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-1"
                  tabIndex={-1}
                  title={showConfirmPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                >
                  {showConfirmPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* Requirements Indicator */}
            <div className="flex flex-col gap-1 py-1">
              <div className="flex items-center gap-1.5 text-[11px]">
                <div className={`w-3.5 h-3.5 rounded-full flex items-center justify-center text-[9px] ${
                  isLengthValid
                    ? 'bg-emerald-500 text-white'
                    : 'bg-zinc-200 dark:bg-zinc-800 text-zinc-400'
                }`}>
                  <Check size={10} />
                </div>
                <span className={isLengthValid ? 'text-emerald-600 dark:text-emerald-400 font-medium' : 'text-[var(--text-muted)]'}>
                  Mật khẩu có tối thiểu 6 ký tự
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-[11px]">
                <div className={`w-3.5 h-3.5 rounded-full flex items-center justify-center text-[9px] ${
                  isPasswordMatch
                    ? 'bg-emerald-500 text-white'
                    : 'bg-zinc-200 dark:bg-zinc-800 text-zinc-400'
                }`}>
                  <Check size={10} />
                </div>
                <span className={isPasswordMatch ? 'text-emerald-600 dark:text-emerald-400 font-medium' : 'text-[var(--text-muted)]'}>
                  Mật khẩu xác nhận trùng khớp
                </span>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting || isSuccess || !isLengthValid || !isPasswordMatch || !isUsernameValid}
              className={`mt-2 w-full py-2.5 px-4 rounded-xl text-sm font-semibold transition-all flex items-center justify-center gap-2 shadow-sm cursor-pointer ${
                isSuccess
                  ? 'bg-emerald-600 text-white'
                  : 'bg-[var(--accent-primary)] text-[var(--accent-primary-text)] hover:bg-[var(--accent-primary-hover)] active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed'
              }`}
            >
              {isSuccess ? (
                <>
                  <CheckCircle2 size={16} />
                  <span>Đăng ký thành công!</span>
                </>
              ) : isSubmitting ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>Đang đăng ký tài khoản...</span>
                </>
              ) : (
                <>
                  <span>Tạo tài khoản & Đăng nhập</span>
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </form>

          {/* Link to Login */}
          <div className="mt-5 text-center pt-4 border-t border-[var(--border-subtle)]">
            <p className="text-xs text-[var(--text-muted)]">
              Đã có tài khoản?{' '}
              <Link
                href="/login"
                className="font-semibold text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-0.5"
              >
                Đăng nhập ngay
                <ArrowRight size={12} />
              </Link>
            </p>
          </div>
        </div>

        {/* Footer Meta */}
        <div className="mt-6 text-center text-[11px] text-[var(--text-muted)]">
          Bằng việc đăng ký, bạn đồng ý với chính sách bảo mật dữ liệu doanh nghiệp và quản trị PII.
        </div>
      </div>
    </div>
  );
}
