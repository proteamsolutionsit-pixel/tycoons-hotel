import { useState } from 'react';
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import '../styles/site.css';
import '../styles/app.css';
import './admin.css';
import { AuthProvider, RequireAuth, useAuth } from './auth';
import Account from './pages/Account';
import Bookings from './pages/Bookings';
import Content from './pages/Content';
import Dashboard from './pages/Dashboard';
import Payments from './pages/Payments';
import RoomTypes from './pages/RoomTypes';
import Settings from './pages/Settings';
import Submissions from './pages/Submissions';
import Users from './pages/Users';

function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to={location.state?.from || '/admin'} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await login(email.trim(), password);
      navigate(location.state?.from || '/admin', { replace: true });
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  return (
    <div className="adm adm-login" style={{ display: 'grid' }}>
      <form onSubmit={submit}>
        <img src="/assets/logo/logo-on-light.png" alt="The Tycoons Hotel" />
        <h1>Staff sign in</h1>
        {error && <div className="adm-notice adm-notice--error" role="alert">{error}</div>}
        <div className="adm-field"><label htmlFor="l-email">Email</label>
          <input id="l-email" className="adm-input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
        <div className="adm-field"><label htmlFor="l-pw">Password</label>
          <input id="l-pw" className="adm-input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></div>
        <button className="adm-btn" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <Link to="/" className="adm-muted" style={{ textAlign: 'center' }}>Back to the website</Link>
      </form>
    </div>
  );
}

function Shell() {
  const { user, logout, isAdmin } = useAuth();
  const nav = (to, label, end) => <NavLink to={to} end={end}>{label}</NavLink>;
  return (
    <div className="adm">
      <aside className="adm-side" aria-label="Admin navigation">
        <img src="/assets/logo/logo-on-dark.png" alt="The Tycoons Hotel" />
        {nav('/admin', 'Dashboard', true)}
        {nav('/admin/bookings', 'Bookings')}
        {nav('/admin/payments', 'Payments')}
        {nav('/admin/submissions', 'Requests')}
        {nav('/admin/rooms', 'Rooms & rates')}
        {nav('/admin/content', 'Content')}
        {nav('/admin/settings', 'Site settings')}
        {isAdmin && nav('/admin/users', 'Staff users')}
        {nav('/admin/account', 'My account')}
        <button type="button" className="adm-side__link" onClick={logout}>Sign out</button>
        <div className="adm-side__foot">{user.full_name}<br />{user.role}</div>
      </aside>
      <main className="adm-main" id="main" tabIndex={-1}>
        <Routes>
          <Route index element={<Dashboard />} />
          <Route path="bookings" element={<Bookings />} />
          <Route path="bookings/:id" element={<Bookings />} />
          <Route path="payments" element={<Payments />} />
          <Route path="submissions" element={<Submissions />} />
          <Route path="rooms" element={<RoomTypes />} />
          <Route path="content" element={<Content />} />
          <Route path="settings" element={<Settings />} />
          <Route path="users" element={isAdmin ? <Users /> : <Navigate to="/admin" replace />} />
          <Route path="account" element={<Account />} />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function AdminApp() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="login" element={<Login />} />
        <Route path="*" element={<RequireAuth><Shell /></RequireAuth>} />
      </Routes>
    </AuthProvider>
  );
}
