'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { UserProfile, AuthContextType, AuthResponse } from '@/types/auth';

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

  // Check auth state on load
  useEffect(() => {
    const verifyAuth = async () => {
      if (typeof window === 'undefined') {
        setIsLoading(false);
        return;
      }

      const storedToken = localStorage.getItem(TOKEN_KEY);
      const storedUser = localStorage.getItem(USER_KEY);

      if (!storedToken) {
        setIsLoading(false);
        return;
      }

      setToken(storedToken);
      if (storedUser) {
        try {
          setUser(JSON.parse(storedUser));
        } catch {
          // ignore parsing error
        }
      }

      // Ngay lập tức mở khóa UI, không bắt người dùng chờ network request
      setIsLoading(false);

      // Xác thực token ngầm trong nền (Stale-While-Revalidate)
      try {
        const res = await fetch('/api/auth/me', {
          headers: {
            Authorization: `Bearer ${storedToken}`,
          },
        });

        if (res.ok) {
          const userData = await res.json();
          const profile: UserProfile = {
            user_id: userData.user_id,
            username: userData.username || userData.user_id,
            display_name: userData.display_name || userData.username || 'User',
            role: userData.role || 'analyst',
          };
          setUser(profile);
          localStorage.setItem(USER_KEY, JSON.stringify(profile));
          syncTokenCookie(storedToken);
        } else if (res.status === 401 || res.status === 403) {
          handleClearAuth();
          router.replace('/login');
        }
      } catch (err) {
        console.warn('Không thể kiểm tra token với server:', err);
      }
    };

    verifyAuth();

    // Listen to 401 events from fetchWithAuth
    const handleUnauthorized = () => {
      handleClearAuth();
      router.push('/login');
    };

    window.addEventListener('auth_unauthorized', handleUnauthorized);
    return () => {
      window.removeEventListener('auth_unauthorized', handleUnauthorized);
    };
  }, [router]);

  const login = async (username: string, password: string): Promise<void> => {
    const res = await fetch('/api/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    const data: AuthResponse & { detail?: string } = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || 'Tên đăng nhập hoặc mật khẩu không chính xác.');
    }

    const profile: UserProfile = {
      user_id: data.user_id,
      username: data.username || username,
      display_name: data.display_name || username,
      role: data.role || 'analyst',
    };

    handleSetAuth(data.access_token, profile);
  };

  const register = async (username: string, password: string, displayName?: string): Promise<void> => {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username,
        password,
        display_name: displayName,
      }),
    });

    const data: AuthResponse & { detail?: string } = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || 'Không thể tạo tài khoản. Vui lòng thử lại.');
    }

    const profile: UserProfile = {
      user_id: data.user_id,
      username: data.username || username,
      display_name: data.display_name || username,
      role: data.role || 'analyst',
    };

    handleSetAuth(data.access_token, profile);
  };

  const logout = () => {
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
