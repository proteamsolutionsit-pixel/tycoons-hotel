/* Small UI kit for the admin. */
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { useAuth } from './auth';

/** Load an admin endpoint; re-runs when `query` changes. */
export function useAdminList(path, query) {
  const { handleError } = useAuth();
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const key = JSON.stringify(query || {});
  const seq = useRef(0);
  const reload = useCallback(() => {
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    api.get(path, query).then(
      (data) => id === seq.current && setState({ data, error: null, loading: false }),
      (error) => { handleError(error); if (id === seq.current) setState({ data: null, error, loading: false }); },
    );
  }, [path, key]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { reload(); }, [reload]);
  return { ...state, reload };
}

export function PageTitle({ title, children }) {
  useEffect(() => { document.title = `${title} — Admin — The Tycoons Hotel`; }, [title]);
  return (
    <div className="adm-head">
      <h1>{title}</h1>
      <div className="adm-head__actions">{children}</div>
    </div>
  );
}

export function Badge({ value }) {
  if (!value) return <span className="adm-badge">—</span>;
  return <span className={`adm-badge adm-badge--${value}`}>{String(value).replace(/_/g, ' ')}</span>;
}

export function Pager({ page, onChange }) {
  if (!page || page.total <= page.limit) return null;
  const { total, limit, offset } = page;
  return (
    <div className="adm-pager">
      <span>{offset + 1}–{Math.min(offset + limit, total)} of {total}</span>
      <button type="button" className="adm-btn adm-btn--ghost" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Previous</button>
      <button type="button" className="adm-btn adm-btn--ghost" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Next</button>
    </div>
  );
}

export function Notice({ notice, onClose }) {
  if (!notice) return null;
  return (
    <div className={`adm-notice adm-notice--${notice.type}`} role={notice.type === 'error' ? 'alert' : 'status'}>
      <span>{notice.message}</span>
      {onClose && <button type="button" className="adm-x" aria-label="Dismiss" onClick={onClose}>×</button>}
    </div>
  );
}

export function Drawer({ title, onClose, children, wide }) {
  const ref = useRef(null);
  useEffect(() => {
    const prev = document.activeElement;
    ref.current?.focus();
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); prev?.focus?.(); };
  }, [onClose]);
  return (
    <div className="adm-drawer" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={'adm-drawer__panel' + (wide ? ' adm-drawer__panel--wide' : '')} role="dialog" aria-modal="true"
        aria-label={title} tabIndex={-1} ref={ref}>
        <div className="adm-drawer__head">
          <h2>{title}</h2>
          <button type="button" className="adm-x" aria-label="Close" onClick={onClose}>×</button>
        </div>
        <div className="adm-drawer__body">{children}</div>
      </div>
    </div>
  );
}

export function StateRow({ state, cols, empty = 'Nothing here yet.' }) {
  if (state.loading && !state.data) return <tr><td colSpan={cols} className="adm-muted">Loading…</td></tr>;
  if (state.error) return <tr><td colSpan={cols} className="adm-error">{state.error.message}</td></tr>;
  const items = state.data?.items ?? state.data;
  if (Array.isArray(items) && !items.length) return <tr><td colSpan={cols} className="adm-muted">{empty}</td></tr>;
  return null;
}

export function SearchBox({ value, onChange, placeholder = 'Search' }) {
  const [v, setV] = useState(value || '');
  useEffect(() => {
    const t = setTimeout(() => { if (v !== (value || '')) onChange(v); }, 350);
    return () => clearTimeout(t);
  }, [v]); // eslint-disable-line react-hooks/exhaustive-deps
  return <input className="adm-input" type="search" placeholder={placeholder} value={v} onChange={(e) => setV(e.target.value)} aria-label={placeholder} />;
}
