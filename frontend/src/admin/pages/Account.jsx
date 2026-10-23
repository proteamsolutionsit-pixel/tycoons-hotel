import { useState } from 'react';
import { api } from '../../services/api';
import { useAuth } from '../auth';
import { Notice, PageTitle } from '../ui';

export default function Account() {
  const { user, handleError } = useAuth();
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm: '' });
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    if (form.new_password !== form.confirm) { setNotice({ type: 'error', message: 'The new passwords do not match.' }); return; }
    setBusy(true); setNotice(null);
    try {
      await api.post('/api/admin/auth/change-password', { current_password: form.current_password, new_password: form.new_password });
      setForm({ current_password: '', new_password: '', confirm: '' });
      setNotice({ type: 'success', message: 'Password changed. Other devices have been signed out.' });
    } catch (err) { handleError(err); setNotice({ type: 'error', message: err.message }); } finally { setBusy(false); }
  };

  return (
    <>
      <PageTitle title="My account" />
      <dl className="adm-dl"><dt>Name</dt><dd>{user.full_name}</dd><dt>Email</dt><dd>{user.email}</dd><dt>Role</dt><dd>{user.role}</dd></dl>
      <h2>Change password</h2>
      <form className="adm-form" style={{ maxWidth: 560 }} onSubmit={submit}>
        <Notice notice={notice} />
        <div className="adm-field adm-field--wide"><label htmlFor="a-cur">Current password</label><input id="a-cur" className="adm-input" type="password" autoComplete="current-password" required value={form.current_password} onChange={set('current_password')} /></div>
        <div className="adm-field"><label htmlFor="a-new">New password</label><input id="a-new" className="adm-input" type="password" autoComplete="new-password" required minLength={12} value={form.new_password} onChange={set('new_password')} /></div>
        <div className="adm-field"><label htmlFor="a-conf">Repeat new password</label><input id="a-conf" className="adm-input" type="password" autoComplete="new-password" required value={form.confirm} onChange={set('confirm')} /></div>
        <small className="adm-muted adm-field--wide">At least 12 characters with upper- and lowercase letters and a number.</small>
        <div className="adm-form__actions"><button className="adm-btn" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Change password'}</button></div>
      </form>
    </>
  );
}
