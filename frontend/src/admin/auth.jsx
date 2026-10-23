/* Staff session. The token lives in an HttpOnly cookie the browser sends
   automatically; this context only holds who is signed in. Every admin
   permission is enforced by the API — hiding UI here is convenience only. */
import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { api, ApiError } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined); // undefined = checking, null = signed out

  useEffect(() => {
    api.get('/api/admin/auth/me').then(setUser).catch(() => setUser(null));
  }, []);

  const login = useCallback(async (email, password) => {
    const u = await api.post('/api/admin/auth/login', { email, password });
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(async () => {
    try { await api.post('/api/admin/auth/logout'); } catch { /* already signed out */ }
    setUser(null);
  }, []);

  // Any 401 from an admin call (expired session) drops back to sign-in
  const handleError = useCallback((err) => {
    if (err instanceof ApiError && err.status === 401) setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, login, logout, handleError, isAdmin: user?.role === 'admin' }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);

export function RequireAuth({ children }) {
  const { user } = useAuth();
  const location = useLocation();
  if (user === undefined) return <div className="adm-center"><span className="spinner" aria-label="Loading" /></div>;
  if (!user) return <Navigate to="/admin/login" replace state={{ from: location.pathname }} />;
  return children;
}
