import { useEffect, useState } from 'react';
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import '../styles/site.css';
import '../styles/app.css';
import './admin.css';
import { api } from '../services/api';
import { AuthProvider, RequireAuth, useAuth } from './auth';
import {
  IconBed, IconCalendar, IconCard, IconClose, IconDashboard, IconImage, IconInbox, IconKey, IconLogout, IconMenu, IconShield,
  IconSliders, IconTag, IconUser, IconUsers,
} from './icons';
import Account from './pages/Account';
import AuditLog from './pages/AuditLog';
import Bookings from './pages/Bookings';
import Content from './pages/Content';
import Dashboard from './pages/Dashboard';
import Occupancy from './pages/Occupancy';
import Payments from './pages/Payments';
import PaymentSettings from './pages/PaymentSettings';
import RoomTypes from './pages/RoomTypes';
import Settings from './pages/Settings';
import Submissions from './pages/Submissions';
import Users from './pages/Users';
import { ToastProvider } from './ui';

// [path, label, icon, permission needed to see it]
const NAV = [
  { group: 'Operations', items: [
    ['/admin', 'Dashboard', IconDashboard, 'dashboard.view', true],
    ['/admin/occupancy', 'Occupancy', IconCalendar, 'bookings.view'],
    ['/admin/bookings', 'Bookings', IconTag, 'bookings.view'],
    ['/admin/payments', 'Payments', IconCard, 'payments.view'],
    ['/admin/submissions', 'Guest requests', IconInbox, 'submissions.view'],
  ] },
  { group: 'Property', items: [
    ['/admin/rooms', 'Rooms & rates', IconBed, 'catalog.view'],
    ['/admin/content', 'Content', IconImage, 'catalog.view'],
    ['/admin/settings', 'Site settings', IconSliders, 'catalog.view'],
  ] },
  { group: 'Administration', items: [
    ['/admin/payment-gateway', 'Payment gateway', IconKey, 'payments.settings'],
    ['/admin/users', 'Staff users', IconUsers, 'users.manage'],
    ['/admin/audit', 'Audit log', IconShield, 'audit.view'],
  ] },
];

function AuthScreen({ title, children }) {
  useEffect(() => { document.title = `${title} — Admin — The Tycoons Hotel`; }, [title]);
  return (
    <div className="adm-login">
      <div className="adm-login__card">
        <img src="/assets/logo/logo-on-light.png" alt="The Tycoons Hotel" />
        <h1>{title}</h1>
        {children}
      </div>
    </div>
  );
}

function Login() {
  const { user, login, notice } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to={location.state?.from?.startsWith('/admin') ? location.state.from : '/admin'} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try { await login(email.trim(), password); } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  return (
    <AuthScreen title="Staff sign in">
      <form onSubmit={submit} className="adm-stack">
        {(error || notice) && <div className={`adm-notice adm-notice--${error ? 'error' : 'info'}`} role="alert">{error || notice}</div>}
        <div className="adm-field"><label htmlFor="l-email">Email</label>
          <input id="l-email" className="adm-input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
        <div className="adm-field"><label htmlFor="l-pw">Password</label>
          <input id="l-pw" className="adm-input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></div>
        <button className="adm-btn adm-btn--block" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <div className="adm-login__links">
          <Link to="/admin/forgot-password">Forgot password?</Link>
          <button type="button" className="adm-link" onClick={() => navigate('/')}>Back to the website</button>
        </div>
      </form>
    </AuthScreen>
  );
}

function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [state, setState] = useState({ busy: false, msg: null, error: null });
  const submit = async (e) => {
    e.preventDefault();
    setState({ busy: true, msg: null, error: null });
    try {
      const r = await api.post('/api/v1/admin/auth/password-reset/request', { email: email.trim() });
      setState({ busy: false, msg: r.message, error: null });
    } catch (err) { setState({ busy: false, msg: null, error: err.message }); }
  };
  return (
    <AuthScreen title="Reset your password">
      <form onSubmit={submit} className="adm-stack">
        <p className="adm-muted">Enter your staff email. If it matches an account, we'll email a link that works for 30 minutes.</p>
        {state.msg && <div className="adm-notice adm-notice--success" role="status">{state.msg}</div>}
        {state.error && <div className="adm-notice adm-notice--error" role="alert">{state.error}</div>}
        <div className="adm-field"><label htmlFor="f-email">Email</label>
          <input id="f-email" className="adm-input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
        <button className="adm-btn adm-btn--block" type="submit" disabled={state.busy}>{state.busy ? 'Sending…' : 'Email me a reset link'}</button>
        <div className="adm-login__links"><Link to="/admin/login">Back to sign in</Link></div>
      </form>
    </AuthScreen>
  );
}

function ResetPassword() {
  // The token arrives in the URL fragment, so it never reaches server logs or Referer headers.
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('token') || '');
  const [pw, setPw] = useState('');
  const [pw2, setPw2] = useState('');
  const [state, setState] = useState({ busy: false, done: false, error: null });
  useEffect(() => { if (token) window.history.replaceState(null, '', window.location.pathname); }, [token]);
  const submit = async (e) => {
    e.preventDefault();
    if (pw !== pw2) { setState({ busy: false, done: false, error: 'The passwords do not match.' }); return; }
    setState({ busy: true, done: false, error: null });
    try {
      await api.post('/api/v1/admin/auth/password-reset/confirm', { token, new_password: pw });
      setState({ busy: false, done: true, error: null });
    } catch (err) { setState({ busy: false, done: false, error: err.message }); }
  };
  if (!token) return <AuthScreen title="Link not valid"><p>This reset link is incomplete. <Link to="/admin/forgot-password">Request a new one</Link>.</p></AuthScreen>;
  return (
    <AuthScreen title="Choose a new password">
      {state.done ? (
        <div className="adm-stack">
          <div className="adm-notice adm-notice--success" role="status">Password updated. Sign in with your new password.</div>
          <Link className="adm-btn adm-btn--block" to="/admin/login">Sign in</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="adm-stack">
          {state.error && <div className="adm-notice adm-notice--error" role="alert">{state.error}</div>}
          <div className="adm-field"><label htmlFor="r-pw">New password</label>
            <input id="r-pw" className="adm-input" type="password" autoComplete="new-password" required minLength={12} value={pw} onChange={(e) => setPw(e.target.value)} aria-describedby="r-help" />
            <small id="r-help" className="adm-muted">12+ characters, upper- and lowercase letters and a number; no common words or your name.</small></div>
          <div className="adm-field"><label htmlFor="r-pw2">Repeat new password</label>
            <input id="r-pw2" className="adm-input" type="password" autoComplete="new-password" required value={pw2} onChange={(e) => setPw2(e.target.value)} /></div>
          <button className="adm-btn adm-btn--block" type="submit" disabled={state.busy}>{state.busy ? 'Saving…' : 'Set password'}</button>
        </form>
      )}
    </AuthScreen>
  );
}

function Sidebar({ onNavigate }) {
  const { can } = useAuth();
  return (
    <nav className="adm-nav" aria-label="Admin">
      {NAV.map(({ group, items }) => {
        const visible = items.filter(([, , , perm]) => can(perm));
        if (!visible.length) return null;
        return (
          <div className="adm-nav__group" key={group}>
            <p className="adm-nav__title">{group}</p>
            {visible.map(([to, label, Icon, , end]) => (
              <NavLink key={to} to={to} end={end} onClick={onNavigate}><Icon />{label}</NavLink>
            ))}
          </div>
        );
      })}
    </nav>
  );
}

function Shell() {
  const { user, logout, can } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);
  const guard = (perm, el) => (can(perm) ? el : <Navigate to="/admin" replace />);

  return (
    <div className={'adm' + (open ? ' adm--nav-open' : '')}>
      <a className="adm-skip" href="#adm-main">Skip to content</a>
      <aside className="adm-side" id="adm-sidebar">
        <div className="adm-side__brand">
          <img src="/assets/logo/logo-on-dark.png" alt="The Tycoons Hotel" />
          <button type="button" className="adm-x adm-side__close" aria-label="Close menu" onClick={() => setOpen(false)}><IconClose /></button>
        </div>
        <Sidebar onNavigate={() => setOpen(false)} />
      </aside>
      <div className="adm-scrim" aria-hidden="true" onClick={() => setOpen(false)} />
      <div className="adm-body">
        <header className="adm-top">
          <button type="button" className="adm-top__menu" aria-label="Open menu" aria-controls="adm-sidebar" aria-expanded={open}
            onClick={() => setOpen(true)}><IconMenu /></button>
          <span className="adm-top__title">The Tycoons Hotel · Admin</span>
          <div className="adm-top__user">
            <NavLink to="/admin/account" className="adm-top__account"><IconUser /><span>{user.full_name}<small>{user.role}</small></span></NavLink>
            <button type="button" className="adm-btn adm-btn--ghost adm-btn--sm" onClick={logout}><IconLogout width={16} height={16} />Sign out</button>
          </div>
        </header>
        <main className="adm-main" id="adm-main" tabIndex={-1}>
          <Routes>
            <Route index element={guard('dashboard.view', <Dashboard />)} />
            <Route path="occupancy" element={guard('bookings.view', <Occupancy />)} />
            <Route path="bookings" element={guard('bookings.view', <Bookings />)} />
            <Route path="bookings/:id" element={guard('bookings.view', <Bookings />)} />
            <Route path="payments" element={guard('payments.view', <Payments />)} />
            <Route path="submissions" element={guard('submissions.view', <Submissions />)} />
            <Route path="rooms" element={guard('catalog.view', <RoomTypes />)} />
            <Route path="content" element={guard('catalog.view', <Content />)} />
            <Route path="settings" element={guard('catalog.view', <Settings />)} />
            <Route path="payment-gateway" element={guard('payments.settings', <PaymentSettings />)} />
            <Route path="users" element={guard('users.manage', <Users />)} />
            <Route path="audit" element={guard('audit.view', <AuditLog />)} />
            <Route path="account" element={<Account />} />
            <Route path="*" element={<Navigate to="/admin" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function AdminApp() {
  return (
    <AuthProvider>
      <ToastProvider>
        <Routes>
          <Route path="login" element={<Login />} />
          <Route path="forgot-password" element={<ForgotPassword />} />
          <Route path="reset-password" element={<ResetPassword />} />
          <Route path="*" element={<RequireAuth><Shell /></RequireAuth>} />
        </Routes>
      </ToastProvider>
    </AuthProvider>
  );
}
