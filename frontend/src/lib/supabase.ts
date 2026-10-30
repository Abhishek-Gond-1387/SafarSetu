/**
 * Supabase Client & Authentication Helper for SafarSetu Frontend.
 *
 * Framework-agnostic: Works with Vite/React.
 * Safe credential rule: Uses SUPABASE_ANON_KEY only; NEVER expose the service role key.
 */

const SUPABASE_URL =
  (typeof (globalThis as any).process !== 'undefined' && (globalThis as any).process?.env?.NEXT_PUBLIC_SUPABASE_URL) ||
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_SUPABASE_URL) ||
  '';

const SUPABASE_ANON_KEY =
  (typeof (globalThis as any).process !== 'undefined' && (globalThis as any).process?.env?.NEXT_PUBLIC_SUPABASE_ANON_KEY) ||
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_SUPABASE_ANON_KEY) ||
  '';

export const getApiBase = () => {
  if (typeof (globalThis as any).process !== 'undefined' && (globalThis as any).process?.env?.NEXT_PUBLIC_API_BASE_URL) {
    return (globalThis as any).process.env.NEXT_PUBLIC_API_BASE_URL;
  }
  if (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE_URL) {
    return (import.meta as any).env.VITE_API_BASE_URL;
  }
  if (typeof window !== 'undefined' && (window.location.port === '5173' || window.location.port === '5174')) {
    return 'http://127.0.0.1:8000/api/v1';
  }
  return '/api/v1';
};

export interface UserSession {
  accessToken: string;
  user: {
    id: string;
    email?: string;
    display_name?: string;
    gender?: string;
  };
}

function base64UrlEncode(str: string): string {
  return btoa(unescape(encodeURIComponent(str)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

export function createDevDemoToken(userId: string, email: string): string {
  const header = base64UrlEncode(JSON.stringify({ alg: 'none', typ: 'JWT' }));
  const exp = Math.floor(Date.now() / 1000) + 7 * 86400; // 7 days
  const payload = base64UrlEncode(
    JSON.stringify({
      sub: userId,
      email,
      role: 'authenticated',
      aud: 'authenticated',
      exp,
      user_metadata: { full_name: 'Delhi Commuter' },
    })
  );
  return `${header}.${payload}.demo_sig`;
}

export class SupabaseAuthClient {
  private url: string;
  private anonKey: string;
  private session: UserSession | null = null;
  private listeners: Array<(session: UserSession | null) => void> = [];

  constructor(url: string = SUPABASE_URL, anonKey: string = SUPABASE_ANON_KEY) {
    this.url = url ? url.replace(/\/$/, '') : '';
    this.anonKey = anonKey;
    this.loadSessionFromStorage();
  }

  private loadSessionFromStorage() {
    if (typeof localStorage !== 'undefined') {
      const stored = localStorage.getItem('safarsetu_supabase_session');
      if (stored) {
        try {
          this.session = JSON.parse(stored);
        } catch {
          this.session = null;
        }
      }
    }
  }

  private saveSession(session: UserSession | null) {
    this.session = session;
    if (typeof localStorage !== 'undefined') {
      if (session) {
        localStorage.setItem('safarsetu_supabase_session', JSON.stringify(session));
      } else {
        localStorage.removeItem('safarsetu_supabase_session');
      }
    }
    this.listeners.forEach((cb) => cb(session));
  }

  public getSession(): UserSession | null {
    return this.session;
  }

  public isSupabaseConfigured(): boolean {
    return Boolean(this.url && this.anonKey && !this.url.includes('your-project'));
  }

  public onAuthStateChange(callback: (session: UserSession | null) => void) {
    this.listeners.push(callback);
    callback(this.session);
    return () => {
      this.listeners = this.listeners.filter((cb) => cb !== callback);
    };
  }

  public async signUp(email: string, password: string, displayName?: string, gender?: string): Promise<{ user: any; error: any }> {
    const apiBase = getApiBase();
    try {
      // 1. Register through SafarSetu backend which creates the user in Supabase auth with confirmed status
      // and records the profile in the PostgreSQL public.profiles table.
      const regRes = await fetch(`${apiBase}/users/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          display_name: displayName || undefined,
          gender: gender || undefined,
        }),
      });

      if (regRes.ok) {
        // 2. Immediately sign in with the exact same credentials to acquire the valid Supabase JWT session!
        const { session, error: signInErr } = await this.signIn(email, password);
        if (signInErr) {
          return { user: { email, display_name: displayName, gender }, error: null };
        }
        return { user: session?.user, error: null };
      }

      // If backend rejected (e.g. duplicate email, invalid password)
      const errorData = await regRes.json().catch(() => ({ detail: 'Registration failed' }));
      return { user: null, error: { message: errorData.detail || errorData.message || 'Registration failed' } };
    } catch (backendErr: any) {
      // Fallback: direct Supabase Auth signup if backend is temporarily unreachable
      if (this.isSupabaseConfigured()) {
        try {
          const res = await fetch(`${this.url}/auth/v1/signup`, {
            method: 'POST',
            headers: {
              'apikey': this.anonKey,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              email,
              password,
              data: {
                full_name: displayName || undefined,
                gender: gender || undefined,
              },
            }),
          });
          const data = await res.json();
          if (!res.ok) {
            return { user: null, error: data };
          }
          if (data.access_token) {
            this.saveSession({
              accessToken: data.access_token,
              user: data.user,
            });
          }
          return { user: data.user, error: null };
        } catch (err: any) {
          return { user: null, error: err };
        }
      }
      return { user: null, error: backendErr };
    }
  }

  public async signIn(email: string, password: string): Promise<{ session: UserSession | null; error: any }> {
    if (!this.isSupabaseConfigured()) {
      return {
        session: null,
        error: { message: 'Supabase URL/Key is not configured. Use "Demo Commuter" to test all authenticated features locally.' },
      };
    }
    try {
      const res = await fetch(`${this.url}/auth/v1/token?grant_type=password`, {
        method: 'POST',
        headers: {
          'apikey': this.anonKey,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        return { session: null, error: data };
      }
      const newSession: UserSession = {
        accessToken: data.access_token,
        user: data.user,
      };
      this.saveSession(newSession);
      return { session: newSession, error: null };
    } catch (err: any) {
      return { session: null, error: err };
    }
  }

  public signInDemo(email: string = 'commuter@delhitransit.gov.in', displayName: string = 'Delhi Commuter'): UserSession {
    const demoId = 'a0000000-0000-0000-0000-000000000001';
    const token = createDevDemoToken(demoId, email);
    const session: UserSession = {
      accessToken: token,
      user: {
        id: demoId,
        email,
        display_name: displayName,
      },
    };
    this.saveSession(session);
    return session;
  }

  public async signOut(): Promise<void> {
    if (this.session && this.isSupabaseConfigured()) {
      try {
        await fetch(`${this.url}/auth/v1/logout`, {
          method: 'POST',
          headers: {
            'apikey': this.anonKey,
            'Authorization': `Bearer ${this.session.accessToken}`,
          },
        });
      } catch (e) {
        // Local cleanup
      }
    }
    this.saveSession(null);
  }
}

export const supabaseAuth = new SupabaseAuthClient();
