'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { UserProfile, AuthContextType, AuthResponse } from '@/types/auth';
import { supabase } from '@/lib/supabase';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = 'jwt_token';
const USER_KEY = 'sana_user_profile';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const router = useRouter();

  const syncTokenCookie = (newToken: string | null) => {
    if (typeof window === 'undefined') return;
    if (newToken) {
      document.cookie = `jwt_token=${newToken}; path=/; max-age=86400; SameSite=Lax`;
    } else {
      document.cookie = `jwt_token=; path=/; max-age=0; SameSite=Lax`;
    }
  };

  const handleSetAuth = (authToken: string, userProfile: UserProfile) => {
    setToken(authToken);
    setUser(userProfile);
    if (typeof window !== 'undefined') {
      localStorage.setItem(TOKEN_KEY, authToken);
      localStorage.setItem(USER_KEY, JSON.stringify(userProfile));
      localStorage.setItem('sana_user', userProfile.username);
      syncTokenCookie(authToken);
    }
  };

  const handleClearAuth = () => {
    setToken(null);
    setUser(null);
    if (typeof window !== 'undefined') {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem('sana_user');
      syncTokenCookie(null);
    }
  };

  // Lắng nghe trạng thái đăng nhập từ Supabase Auth
  useEffect(() => {
    let isMounted = true;

    const initAuth = async () => {
      // 1. Kiểm tra session từ Supabase client trước
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (session && isMounted) {
          const sbUser = session.user;
          const meta = sbUser.user_metadata || {};
          const isAdm =
            meta.role === 'admin' ||
            sbUser.email?.toLowerCase().includes('admin') ||
            sbUser.email === 'kiennguyen300703@gmail.com';

          const profile: UserProfile = {
            user_id: sbUser.id,
            username: sbUser.email || sbUser.id,
            email: sbUser.email,
            display_name: meta.display_name || sbUser.email?.split('@')[0] || 'User',
            role: isAdm ? 'admin' : (meta.role || 'analyst'),
          };

          handleSetAuth(session.access_token, profile);
          setIsLoading(false);
          return;
        }
      } catch (err) {
        console.warn('Lỗi kiểm tra session Supabase:', err);
      }

      // 2. Fallback: đọc từ localStorage nếu Supabase session chưa load
      if (typeof window !== 'undefined') {
        const storedToken = localStorage.getItem(TOKEN_KEY);
        const storedUser = localStorage.getItem(USER_KEY);

        if (storedToken && storedUser) {
          try {
            setToken(storedToken);
            setUser(JSON.parse(storedUser));
          } catch {
            // ignore JSON parse error
          }
        }
      }

      if (isMounted) {
        setIsLoading(false);
      }
    };

    initAuth();

    // 3. Đăng ký Listener thay đổi Auth State từ Supabase (Đăng nhập, Đăng xuất, Token refresh)
    const { data: authListener } = supabase.auth.onAuthStateChange((event, session) => {
      if (session) {
        const sbUser = session.user;
        const meta = sbUser.user_metadata || {};
        const isAdm =
          meta.role === 'admin' ||
          sbUser.email?.toLowerCase().includes('admin') ||
          sbUser.email === 'kiennguyen300703@gmail.com';

        const profile: UserProfile = {
          user_id: sbUser.id,
          username: sbUser.email || sbUser.id,
          email: sbUser.email,
          display_name: meta.display_name || sbUser.email?.split('@')[0] || 'User',
          role: isAdm ? 'admin' : (meta.role || 'analyst'),
        };

        handleSetAuth(session.access_token, profile);
      } else if (event === 'SIGNED_OUT') {
        handleClearAuth();
      }
    });

    const handleUnauthorized = () => {
      handleClearAuth();
      router.push('/login');
    };

    window.addEventListener('auth_unauthorized', handleUnauthorized);

    return () => {
      isMounted = false;
      authListener?.subscription.unsubscribe();
      window.removeEventListener('auth_unauthorized', handleUnauthorized);
    };
  }, [router]);

  // Đăng nhập: Hỗ trợ cả Supabase Auth và backend API proxy
  const login = async (usernameOrEmail: string, password: string): Promise<void> => {
    // 1. Thử đăng nhập trực tiếp qua Supabase Auth nếu là Email
    if (usernameOrEmail.includes('@')) {
      try {
        const { data, error } = await supabase.auth.signInWithPassword({
          email: usernameOrEmail,
          password: password,
        });

        if (!error && data.session) {
          const sbUser = data.session.user;
          const meta = sbUser.user_metadata || {};
          const isAdm =
            meta.role === 'admin' ||
            sbUser.email?.toLowerCase().includes('admin') ||
            sbUser.email === 'kiennguyen300703@gmail.com';

          const profile: UserProfile = {
            user_id: sbUser.id,
            username: sbUser.email || sbUser.id,
            email: sbUser.email,
            display_name: meta.display_name || sbUser.email?.split('@')[0] || 'User',
            role: isAdm ? 'admin' : (meta.role || 'analyst'),
          };

          handleSetAuth(data.session.access_token, profile);
          return;
        }
      } catch (err) {
        console.warn('Supabase direct login error, trying backend API:', err);
      }
    }

    // 2. Gọi backend API endpoint /api/auth/token (Hỗ trợ proxy Supabase + fallback dev user)
    const res = await fetch('/api/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: usernameOrEmail, password }),
    });

    const data: AuthResponse & { detail?: string } = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || 'Tên đăng nhập hoặc mật khẩu không chính xác.');
    }

    const profile: UserProfile = {
      user_id: data.user_id,
      username: data.username || usernameOrEmail,
      email: data.email,
      display_name: data.display_name || usernameOrEmail,
      role: data.role || 'analyst',
    };

    handleSetAuth(data.access_token, profile);
  };

  // Đăng ký tài khoản
  const register = async (
    usernameOrEmail: string,
    password: string,
    displayName?: string,
    email?: string
  ): Promise<void> => {
    const targetEmail = email || (usernameOrEmail.includes('@') ? usernameOrEmail : undefined);
    // 1. Thử đăng ký trực tiếp với Supabase nếu có Email
    if (targetEmail) {
      try {
        const { data, error } = await supabase.auth.signUp({
          email: targetEmail,
          password,
          options: {
            data: {
              username: usernameOrEmail,
              display_name: displayName || usernameOrEmail.split('@')[0],
              role: 'analyst',
            },
          },
        });

        if (!error && data.session) {
          const sbUser = data.session.user;
          const meta = sbUser.user_metadata || {};
          const profile: UserProfile = {
            user_id: sbUser.id,
            username: meta.username || sbUser.email || sbUser.id,
            email: sbUser.email,
            display_name: displayName || meta.display_name || sbUser.email?.split('@')[0] || 'User',
            role: 'analyst',
          };
          handleSetAuth(data.session.access_token, profile);
          return;
        }
      } catch (err) {
        console.warn('Supabase direct signup error, trying backend API:', err);
      }
    }

    // 2. Gọi backend API /api/auth/register
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: usernameOrEmail,
        password,
        display_name: displayName,
        email: targetEmail,
      }),
    });

    const data: AuthResponse & { detail?: string } = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || 'Không thể tạo tài khoản. Vui lòng thử lại.');
    }

    const profile: UserProfile = {
      user_id: data.user_id,
      username: data.username || usernameOrEmail,
      email: data.email,
      display_name: data.display_name || usernameOrEmail,
      role: data.role || 'analyst',
    };

    handleSetAuth(data.access_token, profile);
  };

  // Đăng nhập qua OAuth (Google / GitHub)
  const loginWithOAuth = async (provider: 'google' | 'github') => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: typeof window !== 'undefined' ? `${window.location.origin}/` : undefined,
      },
    });
    if (error) {
      throw new Error(error.message);
    }
  };

  const logout = async () => {
    try {
      await supabase.auth.signOut();
    } catch (err) {
      console.warn('Lỗi khi sign out Supabase:', err);
    }
    handleClearAuth();
    router.replace('/login');
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        login,
        register,
        loginWithOAuth,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
