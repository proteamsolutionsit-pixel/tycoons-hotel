/* Staff session. The session token lives in an HttpOnly cookie the browser
   sends automatically; this context holds only who is signed in and their
   permissions. Every permission is enforced by the API - hiding UI here is
   a convenience, never the control. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { api, ApiError } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined); // undefined = checking, null = signed out
  const [notice, setNotice] = useState(null);   // shown on the sign-in screen

  useEffect(() => {
    api.get('/api/v1/admin/auth/me').then(setUser).catch(() => setUser(null));
  }, []);

  const login = useCallback(async (email, password) => {
    const u = await api.post('/api/v1/admin/auth/login', { email, password });
    setNotice(null);
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(async () => {
    try { await api.post('/api/v1/admin/auth/logout'); } catch { /* already signed out */ }
    setUser(null);
  }, []);

  // A 401 on any admin call means the session ended (idle, expired or revoked)
  const handleError = useCallback((err) => {
    if (err instanceof ApiError && err.status === 401) {
      setNotice(err.code === 'not_authenticated' ? 'Your session has ended. Please sign in again.' : err.message);
      setUser(null);
    }
  }, []);

  const value = useMemo(() => {
    const perms = new Set(user?.permissions || []);
    return {
      user, login, logout, handleError, notice,
      can: (permission) => perms.has(permission),
      isAdmin: user?.role === 'admin',
    };
  }, [user, login, logout, handleError, notice]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);

export function RequireAuth({ children }) {
  const { user } = useAuth();
  const location = useLocation();
  if (user === undefined) return <div className="adm-center"><span className="spinner" role="status" aria-label="Loading" /></div>;
  if (!user) return <Navigate to="/admin/login" replace state={{ from: location.pathname + location.search }} />;
  return children;
}

/** Render children only for users holding `permission`. */
export function Can({ permission, children, fallback = null }) {
  const { can } = useAuth();
  return can(permission) ? children : fallback;
}
