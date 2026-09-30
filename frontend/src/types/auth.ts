export interface UserProfile {
  user_id: string;
  username: string;
  display_name: string;
  role: 'admin' | 'analyst';
  email?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
  role: 'admin' | 'analyst';
  username?: string;
  display_name?: string;
  email?: string;
}

export interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, displayName?: string, email?: string) => Promise<void>;
  loginWithOAuth: (provider: 'google' | 'github') => Promise<void>;
  logout: () => void;
}
