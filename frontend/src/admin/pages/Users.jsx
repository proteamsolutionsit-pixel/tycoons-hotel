import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../services/api';
import { downloadCsv } from '../../utils/csv';
import { dateTime } from '../../utils/format';
import { useAuth } from '../auth';
import { Badge, Drawer, Notice, PageTitle, Pager, SearchBox, SortHeader, StateRow, useAdminList, useTableState } from '../ui';

const SORT_VALUE = {
  full_name: (u) => u.full_name.toLowerCase(), email: (u) => u.email.toLowerCase(), role: (u) => u.role_name.toLowerCase(),
  is_active: (u) => (u.is_active ? 1 : 0), last_login_at: (u) => u.last_login_at || '',
};

export default function Users() {
  const { user: me, handleError, can } = useAuth();
  const list = useAdminList('/api/v1/admin/users');
  const roles = useAdminList('/api/v1/admin/roles');
  // The staff list is small and loaded whole, so search/sort/paging happen here
  const table = useTableState({ sort: 'full_name', order: 'asc' });
  const { q, sort, order, limit, offset } = table.state;
  const needle = q.trim().toLowerCase();
  const rows = (list.data || [])
    .filter((u) => !needle || [u.full_name, u.email, u.role_name].some((v) => String(v).toLowerCase().includes(needle)))
    .sort((a, b) => {
      const x = SORT_VALUE[sort](a);
      const y = SORT_VALUE[sort](b);
      return (x < y ? -1 : x > y ? 1 : a.id - b.id) * (order === 'asc' ? 1 : -1);
    });
  const page = list.data ? { items: rows.slice(offset, offset + limit), total: rows.length, limit, offset } : null;
  const exportCsv = () => downloadCsv('staff-users', ['name', 'email', 'role', 'active', 'last_sign_in_utc', 'created_at_utc'],
    rows.map((u) => [u.full_name, u.email, u.role_name, u.is_active, u.last_login_at, u.created_at]));
  const [open, setOpen] = useState(null); // 'new' | user
  const [notice, setNotice] = useState(null);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);

  const start = (u) => {
    setOpen(u);
    setNotice(null);
    const fallback = (roles.data || []).find((r) => r.key === 'front_desk')?.id ?? '';
    setForm(u === 'new' ? { email: '', full_name: '', role_id: String(fallback), password: '' }
      : { email: u.email, full_name: u.full_name, role_id: String(u.role_id ?? ''), is_active: u.is_active, new_password: '' });
  };

  const run = async (fn, msg, close = true) => {
    setBusy(true); setNotice(null);
    try { await fn(); list.reload(); if (close) setOpen(null); setNotice({ type: 'success', message: msg }); }
    catch (err) { handleError(err); setNotice({ type: 'error', message: err.message }); } finally { setBusy(false); }
  };
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));

  return (
    <>
      <PageTitle title="Staff users">
        {can('data.export') && <button type="button" className="adm-btn adm-btn--ghost" onClick={exportCsv} disabled={!rows.length}>Export CSV</button>}
        <button type="button" className="adm-btn" onClick={() => start('new')}>New user</button>
      </PageTitle>
      {!open && <Notice notice={notice} onClose={() => setNotice(null)} />}
      <p className="adm-muted">What each user can see and do comes from their role.{can('roles.manage') && <> Define roles under <Link to="/admin/roles">Roles &amp; access</Link>.</>}</p>
      <div className="adm-toolbar"><SearchBox value={q} onChange={(v) => table.set({ q: v })} placeholder="Name, email or role" /></div>
      <div className="adm-table-wrap">
        <table className="adm-table">
          <thead><tr>
            <SortHeader label="Name" field="full_name" {...table.sortProps} />
            <SortHeader label="Email" field="email" {...table.sortProps} />
            <SortHeader label="Role" field="role" {...table.sortProps} />
            <SortHeader label="Status" field="is_active" {...table.sortProps} />
            <SortHeader label="Last sign-in" field="last_login_at" {...table.sortProps} />
          </tr></thead>
          <tbody>
            <StateRow state={list} cols={5} />
            {list.data && !rows.length && needle && <tr><td colSpan={5} className="adm-muted">No staff match “{q}”.</td></tr>}
            {(page?.items || []).map((u) => (
              <tr key={u.id} className="adm-row-link" tabIndex={0} onClick={() => start(u)} onKeyDown={(e) => { if (e.key === 'Enter') start(u); }}>
                <td>{u.full_name}{u.id === me.id && <span className="adm-muted"> (you)</span>}</td><td>{u.email}</td>
                <td><span className={`adm-badge adm-badge--${u.role === 'admin' ? 'brand' : 'neutral'}`} style={{ textTransform: 'none' }}>{u.role_name}</span></td><td><Badge value={u.is_active ? 'active' : 'disabled'} /></td>
                <td className="adm-muted">{dateTime(u.last_login_at) || 'Never'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={page} {...table.pagerProps} />

      {open && (
        <Drawer title={open === 'new' ? 'New staff user' : open.email} onClose={() => setOpen(null)}>
          <Notice notice={notice} />
          {open === 'new' ? (
            <form className="adm-form" onSubmit={(e) => { e.preventDefault(); run(() => api.post('/api/v1/admin/users', { ...form, role_id: Number(form.role_id) }), 'User created.'); }}>
              <div className="adm-field adm-field--wide"><label htmlFor="u-email">Email</label><input id="u-email" className="adm-input" type="email" required value={form.email} onChange={set('email')} /></div>
              <div className="adm-field"><label htmlFor="u-name">Full name</label><input id="u-name" className="adm-input" required value={form.full_name} onChange={set('full_name')} /></div>
              <div className="adm-field"><label htmlFor="u-role">Role</label><select id="u-role" className="adm-input" required value={form.role_id} onChange={set('role_id')}>
                {(roles.data || []).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select></div>
              <div className="adm-field adm-field--wide"><label htmlFor="u-pw">Initial password</label><input id="u-pw" className="adm-input" type="password" autoComplete="new-password" required value={form.password} onChange={set('password')} />
                <small className="adm-muted">At least 12 characters with upper- and lowercase letters and a number.</small></div>
              <div className="adm-form__actions"><button className="adm-btn" type="submit" disabled={busy}>Create user</button></div>
            </form>
          ) : (
            <>
              <form className="adm-form" onSubmit={(e) => { e.preventDefault(); run(() => api.patch(`/api/v1/admin/users/${open.id}`, { email: form.email, full_name: form.full_name, role_id: Number(form.role_id), is_active: form.is_active }), 'User updated.'); }}>
                <div className="adm-field adm-field--wide"><label htmlFor="u-email2">Email (used to sign in)</label><input id="u-email2" className="adm-input" type="email" required value={form.email} onChange={set('email')} /></div>
                <div className="adm-field adm-field--wide"><label htmlFor="u-name2">Full name</label><input id="u-name2" className="adm-input" required value={form.full_name} onChange={set('full_name')} /></div>
                <div className="adm-field"><label htmlFor="u-role2">Role</label><select id="u-role2" className="adm-input" required value={form.role_id} onChange={set('role_id')}>
                {(roles.data || []).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select></div>
                <div className="adm-field adm-field--check"><label htmlFor="u-active">Account active</label><input id="u-active" type="checkbox" checked={form.is_active} onChange={set('is_active')} /></div>
                <div className="adm-form__actions"><button className="adm-btn" type="submit" disabled={busy}>Save</button></div>
              </form>
              <form className="adm-form adm-section" onSubmit={(e) => { e.preventDefault(); run(() => api.post(`/api/v1/admin/users/${open.id}/reset-password`, { new_password: form.new_password }), 'Password reset; their sessions were signed out.'); }}>
                <div className="adm-field adm-field--wide"><label htmlFor="u-npw">Set a new password</label><input id="u-npw" className="adm-input" type="password" autoComplete="new-password" required minLength={12} value={form.new_password} onChange={set('new_password')} /></div>
                <div className="adm-form__actions"><button className="adm-btn adm-btn--ghost" type="submit" disabled={busy}>Reset password</button></div>
              </form>
              <p className="adm-muted">Created {dateTime(open.created_at)}</p>
            </>
          )}
        </Drawer>
      )}
    </>
  );
}
