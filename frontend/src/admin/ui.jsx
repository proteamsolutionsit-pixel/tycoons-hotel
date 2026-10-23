/* UI kit for the admin: data loading, page header, badges, sortable table
   headers, pagination, toasts, drawers and an accessible confirm dialog. */
import { createContext, useCallback, useContext, useEffect, useId, useRef, useState } from 'react';
import { api } from '../services/api';
import { useAuth } from './auth';
import { IconAlert, IconArrowDown, IconArrowUp, IconCheck, IconClose, IconInfo, IconRefresh, IconSort } from './icons';

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

export function PageTitle({ title, subtitle, children }) {
  useEffect(() => { document.title = `${title} — Admin — The Tycoons Hotel`; }, [title]);
  return (
    <div className="adm-head">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="adm-head__sub">{subtitle}</p>}
      </div>
      {children && <div className="adm-head__actions">{children}</div>}
    </div>
  );
}

const BADGE_TONE = {
  confirmed: 'good', captured: 'good', active: 'good', admin: 'brand', success: 'good', closed: 'neutral',
  pending_payment: 'warn', created: 'warn', authorized: 'warn', new: 'info', in_progress: 'info', refund_pending: 'warn',
  payment_review: 'bad', failed: 'bad', denied: 'bad', failure: 'bad',
  cancelled: 'neutral', expired: 'neutral', refunded: 'neutral', hidden: 'neutral', disabled: 'neutral',
  unsubscribed: 'neutral', staff: 'neutral',
};

/** Status chip: text label always present (colour is never the only signal). */
export function Badge({ value }) {
  if (!value) return <span className="adm-badge adm-badge--neutral">—</span>;
  const tone = BADGE_TONE[value] || 'neutral';
  return <span className={`adm-badge adm-badge--${tone}`}><span className="adm-badge__dot" aria-hidden="true" />{String(value).replace(/_/g, ' ')}</span>;
}

/** <th> that toggles server-side sorting; announces state via aria-sort. */
export function SortHeader({ label, field, sort, order, onSort }) {
  const active = sort === field;
  const next = active && order === 'desc' ? 'asc' : 'desc';
  const Icon = !active ? IconSort : order === 'asc' ? IconArrowUp : IconArrowDown;
  return (
    <th aria-sort={active ? (order === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className="adm-sort" onClick={() => onSort(field, active ? next : 'desc')}>
        {label}<Icon width={14} height={14} />
      </button>
    </th>
  );
}

export function Pager({ page, onChange }) {
  if (!page || page.total <= page.limit) return page && page.total ? <div className="adm-pager"><span>{page.total} total</span></div> : null;
  const { total, limit, offset } = page;
  return (
    <nav className="adm-pager" aria-label="Pagination">
      <span>{offset + 1}–{Math.min(offset + limit, total)} of {total}</span>
      <button type="button" className="adm-btn adm-btn--ghost adm-btn--sm" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Previous</button>
      <button type="button" className="adm-btn adm-btn--ghost adm-btn--sm" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Next</button>
    </nav>
  );
}

/** Loading / error / empty rows for a table body. */
export function StateRow({ state, cols, empty = 'Nothing here yet.' }) {
  if (state.loading && !state.data) {
    return [0, 1, 2, 3].map((i) => (
      <tr key={i} className="adm-skeleton-row" aria-hidden="true">
        {Array.from({ length: cols }, (_, j) => <td key={j}><span className="adm-skeleton" /></td>)}
      </tr>
    ));
  }
  if (state.error) {
    return (
      <tr><td colSpan={cols}>
        <div className="adm-empty adm-empty--error" role="alert">
          <IconAlert /><span>{state.error.message}</span>
          <button type="button" className="adm-btn adm-btn--ghost adm-btn--sm" onClick={state.reload}><IconRefresh width={16} height={16} />Retry</button>
        </div>
      </td></tr>
    );
  }
  const items = state.data?.items ?? state.data;
  if (Array.isArray(items) && !items.length) return <tr><td colSpan={cols}><div className="adm-empty"><IconInfo /><span>{empty}</span></div></td></tr>;
  return null;
}

export function SearchBox({ value, onChange, placeholder = 'Search' }) {
  const [v, setV] = useState(value || '');
  useEffect(() => {
    const t = setTimeout(() => { if (v !== (value || '')) onChange(v); }, 350);
    return () => clearTimeout(t);
  }, [v]); // eslint-disable-line react-hooks/exhaustive-deps
  return <input className="adm-input adm-input--search" type="search" placeholder={placeholder} value={v} onChange={(e) => setV(e.target.value)} aria-label={placeholder} />;
}

/** Inline notice inside forms/drawers. */
export function Notice({ notice, onClose }) {
  if (!notice) return null;
  const Icon = notice.type === 'error' ? IconAlert : IconCheck;
  return (
    <div className={`adm-notice adm-notice--${notice.type}`} role={notice.type === 'error' ? 'alert' : 'status'}>
      <Icon /><span>{notice.message}</span>
      {onClose && <button type="button" className="adm-x" aria-label="Dismiss" onClick={onClose}><IconClose width={16} height={16} /></button>}
    </div>
  );
}

/* -- Toasts --------------------------------------------------------------- */
const ToastContext = createContext(() => {});
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((message, type = 'success') => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, message, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), type === 'error' ? 8000 : 4500);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="adm-toasts" role="region" aria-label="Notifications" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`adm-toast adm-toast--${t.type}`} role={t.type === 'error' ? 'alert' : 'status'}>
            {t.type === 'error' ? <IconAlert /> : <IconCheck />}<span>{t.message}</span>
            <button type="button" className="adm-x" aria-label="Dismiss" onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))}><IconClose width={16} height={16} /></button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/* -- Focus-trapped modal surfaces ------------------------------------------- */
function useModal(ref, onClose) {
  useEffect(() => {
    const prev = document.activeElement;
    const el = ref.current;
    const focusables = () => Array.from(el.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'));
    (el.querySelector('[data-autofocus]') || focusables()[0] || el).focus();
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose(); return; }
      if (e.key !== 'Tab') return;
      const f = focusables();
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    };
    el.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => { el.removeEventListener('keydown', onKey); document.body.style.overflow = ''; prev?.focus?.(); };
  }, [ref, onClose]);
}

export function Drawer({ title, onClose, children, wide, footer }) {
  const ref = useRef(null);
  const titleId = useId();
  useModal(ref, onClose);
  return (
    <div className="adm-drawer" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={'adm-drawer__panel' + (wide ? ' adm-drawer__panel--wide' : '')} role="dialog" aria-modal="true"
        aria-labelledby={titleId} tabIndex={-1} ref={ref}>
        <div className="adm-drawer__head">
          <h2 id={titleId}>{title}</h2>
          <button type="button" className="adm-x" aria-label="Close" onClick={onClose}><IconClose /></button>
        </div>
        <div className="adm-drawer__body">{children}</div>
        {footer && <div className="adm-drawer__foot">{footer}</div>}
      </div>
    </div>
  );
}

/**
 * Confirmation for destructive or financial actions.
 *   confirmText: optional phrase the user must type (e.g. the amount) to enable the button.
 */
export function ConfirmDialog({ title, children, confirmLabel = 'Confirm', danger = false, confirmText, busy, onConfirm, onCancel }) {
  const ref = useRef(null);
  const titleId = useId();
  const [typed, setTyped] = useState('');
  useModal(ref, onCancel);
  const ready = !confirmText || typed.trim() === confirmText;
  return (
    <div className="adm-modal" role="presentation">
      <div className="adm-modal__panel" role="alertdialog" aria-modal="true" aria-labelledby={titleId} ref={ref} tabIndex={-1}>
        <h2 id={titleId}>{title}</h2>
        <div className="adm-modal__body">{children}</div>
        {confirmText && (
          <div className="adm-field">
            <label htmlFor={`${titleId}-type`}>Type <strong>{confirmText}</strong> to confirm</label>
            <input id={`${titleId}-type`} className="adm-input" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" data-autofocus />
          </div>
        )}
        <div className="adm-modal__actions">
          <button type="button" className="adm-btn adm-btn--ghost" onClick={onCancel} data-autofocus={confirmText ? undefined : true}>Cancel</button>
          <button type="button" className={'adm-btn' + (danger ? ' adm-btn--danger-solid' : '')} disabled={!ready || busy} onClick={onConfirm}>
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function StatCard({ label, value, hint, tone, to, LinkComp }) {
  const body = (
    <>
      <div className="adm-stat__label">{label}</div>
      <div className="adm-stat__value">{value}</div>
      {hint && <div className="adm-stat__hint">{hint}</div>}
    </>
  );
  const cls = 'adm-stat' + (tone ? ` adm-stat--${tone}` : '');
  return to && LinkComp ? <LinkComp to={to} className={cls}>{body}</LinkComp> : <div className={cls}>{body}</div>;
}
