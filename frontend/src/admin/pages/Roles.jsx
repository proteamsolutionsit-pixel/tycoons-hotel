/* Roles & access: define roles and tick what each may do; assign them on the
   Staff users page. Administrator always has full access. Ticking an action
   also ticks what it needs to see (e.g. "Issue refunds" needs "View payments"). */
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../services/api';
import { dateTime } from '../../utils/format';
import { useAuth } from '../auth';
import { ConfirmDialog, Drawer, Notice, PageTitle, SearchBox, SortHeader, StateRow, useAdminList, useTableState, useToast } from '../ui';

const SORT_VALUE = { name: (r) => r.name.toLowerCase(), users: (r) => r.user_count, access: (r) => r.permissions.length };

export default function Roles() {
  const list = useAdminList('/api/v1/admin/roles');
  const catalogue = useAdminList('/api/v1/admin/roles/permissions');
  const [editing, setEditing] = useState(null);      // 'new' | role
  const table = useTableState({ sort: 'name', order: 'asc' });
  const { q, sort, order } = table.state;
  const total = catalogue.data?.length || 0;

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (list.data || [])
      .filter((r) => !needle || `${r.name} ${r.description || ''}`.toLowerCase().includes(needle))
      .sort((a, b) => {
        if (a.is_system !== b.is_system) return a.is_system ? -1 : 1;      // Administrator first
        const x = SORT_VALUE[sort](a);
        const y = SORT_VALUE[sort](b);
        return (x < y ? -1 : x > y ? 1 : 0) * (order === 'asc' ? 1 : -1);
      });
  }, [list.data, q, sort, order]);

  return (
    <>
      <PageTitle title="Roles & access" subtitle="Decide what each role can see and do, then give users a role on the Staff users page.">
        <button type="button" className="adm-btn" onClick={() => setEditing('new')} disabled={!catalogue.data}>New role</button>
      </PageTitle>
      <div className="adm-toolbar"><SearchBox value={q} onChange={(v) => table.set({ q: v })} placeholder="Search roles" /></div>
      <div className="adm-table-wrap">
        <table className="adm-table">
          <thead><tr>
            <SortHeader label="Role" field="name" {...table.sortProps} />
            <th>Description</th>
            <SortHeader label="Access" field="access" {...table.sortProps} />
            <SortHeader label="Users" field="users" {...table.sortProps} />
          </tr></thead>
          <tbody>
            <StateRow state={list} cols={4} empty="No roles yet." />
            {rows.map((r) => (
              <tr key={r.id} className="adm-row-link" tabIndex={0} onClick={() => setEditing(r)} onKeyDown={(e) => { if (e.key === 'Enter') setEditing(r); }}>
                <td><strong>{r.name}</strong>{r.key && <span className="adm-muted"> · built-in</span>}</td>
                <td className="adm-muted">{r.description || '—'}</td>
                <td>{r.is_system ? <span className="adm-badge adm-badge--brand" style={{ textTransform: 'none' }}>Full access</span>
                  : `${r.permissions.length} of ${total}`}</td>
                <td className="adm-num">{r.user_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && catalogue.data && (
        <RoleEditor role={editing === 'new' ? null : editing} catalogue={catalogue.data}
          onClose={() => setEditing(null)} onSaved={() => { setEditing(null); list.reload(); }} />
      )}
    </>
  );
}

function RoleEditor({ role, catalogue, onClose, onSaved }) {
  const { handleError } = useAuth();
  const toast = useToast();
  const locked = !!role?.is_system;
  const [name, setName] = useState(role?.name || '');
  const [description, setDescription] = useState(role?.description || '');
  const [chosen, setChosen] = useState(() => new Set(role?.permissions || []));
  const [notice, setNotice] = useState(null);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const byKey = useMemo(() => Object.fromEntries(catalogue.map((p) => [p.key, p])), [catalogue]);
  // Permissions required by something ticked: shown ticked and locked, with the reason
  const requiredBy = useMemo(() => {
    const out = {};
    chosen.forEach((k) => (byKey[k]?.implies || []).forEach((i) => { (out[i] ||= []).push(byKey[k].label); }));
    return out;
  }, [chosen, byKey]);
  const effective = new Set([...chosen, ...Object.keys(requiredBy)]);
  const groups = catalogue.reduce((acc, p) => { (acc[p.group] ||= []).push(p); return acc; }, {});

  const toggle = (key) => setChosen((s) => { const n = new Set(s); n.has(key) ? n.delete(key) : n.add(key); return n; });
  const setGroup = (items, on) => setChosen((s) => { const n = new Set(s); items.forEach((p) => (on ? n.add(p.key) : n.delete(p.key))); return n; });

  const save = async (e) => {
    e.preventDefault();
    setBusy(true); setNotice(null); setErrors({});
    const body = { name: name.trim(), description: description.trim() || null, permissions: [...effective] };
    try {
      if (role) await api.patch(`/api/v1/admin/roles/${role.id}`, body); else await api.post('/api/v1/admin/roles', body);
      toast(role ? `Saved: ${body.name}` : `Created: ${body.name}`);
      onSaved();
    } catch (err) { handleError(err); setErrors(err.fieldErrors || {}); setNotice({ type: 'error', message: err.message }); } finally { setBusy(false); }
  };

  const remove = async () => {
    setBusy(true);
    try { await api.del(`/api/v1/admin/roles/${role.id}`); toast(`Deleted: ${role.name}`); onSaved(); }
    catch (err) { handleError(err); setConfirmDelete(false); setNotice({ type: 'error', message: err.message }); } finally { setBusy(false); }
  };

  return (
    <Drawer wide title={role ? role.name : 'New role'} onClose={onClose}>
      <form className="adm-form" onSubmit={save} noValidate>
        <Notice notice={notice} />
        {locked && <p className="adm-notice adm-notice--info adm-field--wide">The Administrator role always has full access, including roles and payment keys, and can’t be changed. Make sure at least one person keeps it.</p>}
        <div className="adm-field">
          <label htmlFor="r-name">Role name</label>
          <input id="r-name" className="adm-input" value={name} disabled={locked} maxLength={60} required
            aria-invalid={errors.name ? true : undefined} onChange={(e) => setName(e.target.value)} />
          {errors.name && <small className="adm-error" role="alert">{errors.name}</small>}
        </div>
        <div className="adm-field">
          <label htmlFor="r-desc">Description</label>
          <input id="r-desc" className="adm-input" value={description} disabled={locked} maxLength={255} onChange={(e) => setDescription(e.target.value)} />
        </div>
        {Object.entries(groups).map(([group, items]) => {
          const allOn = items.every((p) => effective.has(p.key));
          return (
            <fieldset key={group} className="adm-field adm-field--wide adm-perms">
              <legend>
                {group}
                {!locked && <button type="button" className="adm-link" onClick={() => setGroup(items, !allOn)}>{allOn ? 'Clear all' : 'Select all'}</button>}
              </legend>
              {items.map((p) => {
                const forced = !!requiredBy[p.key] && !chosen.has(p.key);
                return (
                  <label key={p.key} className={'adm-perm' + (locked || effective.has(p.key) ? ' is-on' : '')}>
                    <input type="checkbox" checked={locked || effective.has(p.key)} disabled={locked || forced} onChange={() => toggle(p.key)} />
                    <span>
                      <strong>{p.label}</strong>
                      <small className="adm-muted">{p.description}{forced && ` Needed for: ${requiredBy[p.key].join(', ')}.`}</small>
                    </span>
                  </label>
                );
              })}
            </fieldset>
          );
        })}
        {role && <p className="adm-muted adm-field--wide">{role.user_count} user(s) have this role. Changes apply to them straight away. Last changed {dateTime(role.updated_at)}. <Link to="/admin/users">Staff users</Link></p>}
        {!locked && (
          <div className="adm-form__actions">
            <button className="adm-btn" type="submit" disabled={busy}>{busy ? 'Saving…' : role ? 'Save role' : 'Create role'}</button>
            {role && !role.key && (
              <button type="button" className="adm-btn adm-btn--danger" disabled={busy || role.user_count > 0}
                title={role.user_count > 0 ? 'Give its users another role first' : undefined} onClick={() => setConfirmDelete(true)}>Delete role</button>
            )}
          </div>
        )}
      </form>
      {confirmDelete && (
        <ConfirmDialog title={`Delete “${role.name}”?`} confirmLabel="Delete role" danger busy={busy} onConfirm={remove} onCancel={() => setConfirmDelete(false)}>
          <p>The role is removed. Nobody holds it, so no one loses access.</p>
        </ConfirmDialog>
      )}
    </Drawer>
  );
}
