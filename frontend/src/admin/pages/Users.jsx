import { useState } from 'react';
import { api } from '../../services/api';
import { dateTime } from '../../utils/format';
import { useAuth } from '../auth';
import { Badge, Drawer, Notice, PageTitle, StateRow, useAdminList } from '../ui';

export default function Users() {
  const { user: me, handleError } = useAuth();
  const list = useAdminList('/api/v1/admin/users');
  const [open, setOpen] = useState(null); // 'new' | user
  const [notice, setNotice] = useState(null);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);

  const start = (u) => {
    setOpen(u);
    setNotice(null);
    setForm(u === 'new' ? { email: '', full_name: '', role: 'staff', password: '' }
      : { full_name: u.full_name, role: u.role, is_active: u.is_active, new_password: '' });
  };

  const run = async (fn, msg, close = true) => {
    setBusy(true); setNotice(null);
    try { await fn(); list.reload(); if (close) setOpen(null); setNotice({ type: 'success', message: msg }); }
    catch (err) { handleError(err); setNotice({ type: 'error', message: err.message }); } finally { setBusy(false); }
  };
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));

  return (
    <>
      <PageTitle title="Staff users"><button type="button" className="adm-btn" onClick={() => start('new')}>New user</button></PageTitle>
      {!open && <Notice notice={notice} onClose={() => setNotice(null)} />}
      <p className="adm-muted"><strong>Admin</strong>: everything. <strong>Staff</strong>: read bookings and payments, handle guest requests.</p>
      <div className="adm-table-wrap">
        <table className="adm-table">
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Last sign-in</th></tr></thead>
          <tbody>
            <StateRow state={list} cols={5} />
            {(list.data || []).map((u) => (
              <tr key={u.id} className="adm-row-link" tabIndex={0} onClick={() => start(u)} onKeyDown={(e) => { if (e.key === 'Enter') start(u); }}>
                <td>{u.full_name}{u.id === me.id && <span className="adm-muted"> (you)</span>}</td><td>{u.email}</td>
                <td><Badge value={u.role} /></td><td><Badge value={u.is_active ? 'active' : 'disabled'} /></td>
                <td className="adm-muted">{dateTime(u.last_login_at) || 'Never'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {open && (
        <Drawer title={open === 'new' ? 'New staff user' : open.email} onClose={() => setOpen(null)}>
          <Notice notice={notice} />
          {open === 'new' ? (
            <form className="adm-form" onSubmit={(e) => { e.preventDefault(); run(() => api.post('/api/v1/admin/users', form), 'User created.'); }}>
              <div className="adm-field adm-field--wide"><label htmlFor="u-email">Email</label><input id="u-email" className="adm-input" type="email" required value={form.email} onChange={set('email')} /></div>
              <div className="adm-field"><label htmlFor="u-name">Full name</label><input id="u-name" className="adm-input" required value={form.full_name} onChange={set('full_name')} /></div>
              <div className="adm-field"><label htmlFor="u-role">Role</label><select id="u-role" className="adm-input" value={form.role} onChange={set('role')}><option value="staff">Staff</option><option value="admin">Admin</option></select></div>
              <div className="adm-field adm-field--wide"><label htmlFor="u-pw">Initial password</label><input id="u-pw" className="adm-input" type="password" autoComplete="new-password" required value={form.password} onChange={set('password')} />
                <small className="adm-muted">At least 12 characters with upper- and lowercase letters and a number.</small></div>
              <div className="adm-form__actions"><button className="adm-btn" type="submit" disabled={busy}>Create user</button></div>
            </form>
          ) : (
            <>
              <form className="adm-form" onSubmit={(e) => { e.preventDefault(); run(() => api.patch(`/api/v1/admin/users/${open.id}`, { full_name: form.full_name, role: form.role, is_active: form.is_active }), 'User updated.'); }}>
                <div className="adm-field adm-field--wide"><label htmlFor="u-name2">Full name</label><input id="u-name2" className="adm-input" required value={form.full_name} onChange={set('full_name')} /></div>
                <div className="adm-field"><label htmlFor="u-role2">Role</label><select id="u-role2" className="adm-input" value={form.role} onChange={set('role')}><option value="staff">Staff</option><option value="admin">Admin</option></select></div>
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
