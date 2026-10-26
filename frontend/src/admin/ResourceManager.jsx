/* Generic list + edit drawer for simple admin tables (room types, spa
   treatments, content cards, gallery, job openings). Editing controls appear
   only with `managePermission`; the API enforces it regardless.
   Columns: { label, key?, render?, money?, sort? } - a column with `key` (or
   `sort`, the field name for render-only columns) gets a sortable header. */
import { useState } from 'react';
import { api, ApiError } from '../services/api';
import { rupees } from '../utils/format';
import { useAuth } from './auth';
import { ConfirmDialog, Drawer, ExportButton, Notice, Pager, SearchBox, SortHeader, StateRow, useAdminList, useTableState, useToast } from './ui';

function toForm(fields, item) {
  const v = {};
  fields.forEach((f) => {
    const raw = item ? item[f.name] : f.default;
    if (f.type === 'money') v[f.name] = raw === undefined || raw === null ? '' : String(raw / 100);
    else if (f.type === 'checkbox') v[f.name] = !!raw;
    else v[f.name] = raw ?? '';
  });
  return v;
}

function fromForm(fields, values, isNew) {
  const out = {};
  fields.forEach((f) => {
    if (f.createOnly && !isNew) return;
    let v = values[f.name];
    if (f.type === 'money') v = v === '' ? null : Math.round(Number(v) * 100);
    else if (f.type === 'number') v = v === '' ? null : Number(v);
    else if (f.type === 'checkbox') v = !!v;
    else if (typeof v === 'string') { v = v.trim(); if (v === '' && f.nullable) v = null; }
    out[f.name] = v;
  });
  return out;
}

function ImageInput({ value, onChange, id, disabled }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const upload = async (file) => {
    if (!file) return;
    setBusy(true); setErr(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.upload('/api/v1/admin/uploads/image', fd);
      onChange(res.url);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="adm-image">
      {value && <img src={value} alt="" />}
      <input id={id} className="adm-input" value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} placeholder="/assets/img/… or upload" />
      {!disabled && (
        <label className="adm-btn adm-btn--ghost adm-btn--sm">
          {busy ? 'Uploading…' : 'Upload image'}
          <input type="file" accept=".jpg,.jpeg,.png,.webp" hidden onChange={(e) => upload(e.target.files?.[0])} />
        </label>
      )}
      {err && <span className="adm-error" role="alert">{err}</span>}
    </div>
  );
}

export function FieldInput({ field: f, value, onChange, error, disabled }) {
  const id = `fld-${f.name}`;
  const errId = error ? `${id}-err` : undefined;
  const common = { id, disabled, 'aria-invalid': error ? true : undefined, 'aria-describedby': errId };
  let control;
  if (f.type === 'textarea') control = <textarea {...common} className="adm-input" rows={f.rows || 4} value={value} onChange={(e) => onChange(e.target.value)} />;
  else if (f.type === 'select') {
    control = (
      <select {...common} className="adm-input" value={value} onChange={(e) => onChange(e.target.value)}>
        {f.options.map((o) => <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>)}
      </select>
    );
  } else if (f.type === 'checkbox') {
    control = <input {...common} type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)} />;
  } else if (f.type === 'image') control = <ImageInput id={id} value={value} onChange={onChange} disabled={disabled} />;
  else {
    control = <input {...common} className="adm-input" type={f.type === 'money' || f.type === 'number' ? 'number' : 'text'}
      step={f.type === 'money' ? '1' : undefined} min={f.min} value={value} onChange={(e) => onChange(e.target.value)} />;
  }
  return (
    <div className={'adm-field' + (f.type === 'checkbox' ? ' adm-field--check' : '') + (f.wide ? ' adm-field--wide' : '')}>
      <label htmlFor={id}>{f.label}{f.type === 'money' ? ' (₹)' : ''}</label>
      {control}
      {f.help && <small className="adm-muted">{f.help}</small>}
      {error && <small className="adm-error" id={errId}>{error}</small>}
    </div>
  );
}

export default function ResourceManager({ endpoint, fields, columns, noun, query, defaults = {}, managePermission }) {
  const { can, handleError } = useAuth();
  const toast = useToast();
  const canManage = can(managePermission);
  const table = useTableState({ sort: '', order: 'asc', limit: 50 });
  const { q, sort, order, limit, offset } = table.state;
  const filters = { ...query, q, sort, order };
  const list = useAdminList(endpoint, { ...filters, limit, offset });
  const [editing, setEditing] = useState(null); // {item|null}
  const [values, setValues] = useState({});
  const [errors, setErrors] = useState({});
  const [notice, setNotice] = useState(null);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const open = (item) => {
    setEditing({ item });
    setValues(toForm(fields, item || defaults));
    setErrors({});
    setNotice(null);
  };

  const save = async (e) => {
    e.preventDefault();
    setSaving(true); setErrors({}); setNotice(null);
    const isNew = !editing.item;
    try {
      const body = fromForm(fields, values, isNew);
      if (isNew) await api.post(endpoint, body); else await api.patch(`${endpoint}/${editing.item.id}`, body);
      setEditing(null);
      toast(`${noun} ${isNew ? 'created' : 'saved'}.`);
      list.reload();
    } catch (err) {
      handleError(err);
      if (err instanceof ApiError) setErrors(err.fieldErrors);
      setNotice({ type: 'error', message: err.message });
    } finally { setSaving(false); }
  };

  const remove = async () => {
    setSaving(true);
    try {
      await api.del(`${endpoint}/${editing.item.id}`);
      setConfirmDelete(false);
      setEditing(null);
      toast(`${noun} deleted.`);
      list.reload();
    } catch (err) { handleError(err); setConfirmDelete(false); setNotice({ type: 'error', message: err.message }); }
    finally { setSaving(false); }
  };

  const items = list.data?.items || [];
  return (
    <>
      <div className="adm-toolbar">
        <SearchBox value={q} onChange={(v) => table.set({ q: v })} placeholder={`Search ${noun.toLowerCase()}s`} />
        <span className="adm-toolbar__end adm-btn-row">
          <ExportButton path={`${endpoint}/export`} query={filters} />
          {canManage && <button type="button" className="adm-btn" onClick={() => open(null)}>New {noun.toLowerCase()}</button>}
        </span>
      </div>
      <div className="adm-table-wrap">
        <table className="adm-table">
          <thead><tr>{columns.map((c) => (c.sort || c.key
            ? <SortHeader key={c.label} label={c.label} field={c.sort || c.key} {...table.sortProps} />
            : <th key={c.label}>{c.label}</th>))}</tr></thead>
          <tbody>
            <StateRow state={list} cols={columns.length} empty={`No ${noun.toLowerCase()}s yet.`} />
            {items.map((it) => (
              <tr key={it.id} className="adm-row-link" tabIndex={0} onClick={() => open(it)}
                onKeyDown={(e) => { if (e.key === 'Enter') open(it); }}>
                {columns.map((c) => <td key={c.label} className={c.money ? 'adm-num' : undefined}>{c.render ? c.render(it) : c.money ? rupees(it[c.key]) : String(it[c.key] ?? '')}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={list.data} {...table.pagerProps} />

      {editing && (
        <Drawer title={editing.item ? (canManage ? `Edit ${noun.toLowerCase()}` : noun) : `New ${noun.toLowerCase()}`} onClose={() => setEditing(null)}>
          <form className="adm-form" onSubmit={save} noValidate>
            <Notice notice={notice} />
            {!canManage && <p className="adm-notice adm-notice--info adm-field--wide">Read only: your role can view but not change this.</p>}
            {fields.filter((f) => !(f.createOnly && editing.item)).map((f) => (
              <FieldInput key={f.name} field={f} value={values[f.name]} error={errors[f.name]} disabled={!canManage}
                onChange={(v) => setValues((s) => ({ ...s, [f.name]: v }))} />
            ))}
            {canManage && (
              <div className="adm-form__actions">
                <button className="adm-btn" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
                {editing.item && <button className="adm-btn adm-btn--danger" type="button" onClick={() => setConfirmDelete(true)}>Delete</button>}
              </div>
            )}
          </form>
        </Drawer>
      )}
      {confirmDelete && (
        <ConfirmDialog title={`Delete this ${noun.toLowerCase()}?`} danger confirmLabel="Delete" busy={saving}
          onCancel={() => setConfirmDelete(false)} onConfirm={remove}>
          <p>This cannot be undone. If it is in use (for example a room type with bookings) the system will refuse; set it inactive instead.</p>
        </ConfirmDialog>
      )}
    </>
  );
}
