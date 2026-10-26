/* Read-only audit trail (append-only in the database): search, filters,
   sortable columns, paging and CSV export - all done by the server. */
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { dateTime } from '../../utils/format';
import { Badge, Drawer, PageTitle, Pager, SearchBox, SortHeader, StateRow, useAdminList } from '../ui';

const PRESETS = [['', 'All actions'], ['auth.', 'Sign-ins & passwords'], ['security.', 'Security events'],
  ['booking.', 'Bookings'], ['payment.', 'Payments & refunds'], ['payment_settings.', 'Payment gateway'],
  ['room_type.', 'Rooms & rates'], ['setting.', 'Site settings'], ['user.', 'Staff users'], ['audit.', 'Audit exports']];
const LIMITS = [25, 50, 100, 200];
const FILTER_KEYS = ['q', 'action', 'outcome', 'date_from', 'date_to', 'sort', 'order'];

export default function AuditLog() {
  const [params, setParams] = useSearchParams();
  const get = (k, d = '') => params.get(k) || d;
  const filters = {
    q: get('q'), action: get('action'), outcome: get('outcome'), date_from: get('date_from'), date_to: get('date_to'),
    sort: get('sort', 'occurred_at'), order: get('order', 'desc'),
  };
  const limit = LIMITS.includes(Number(get('limit'))) ? Number(get('limit')) : 50;
  const offset = Number(get('offset', '0'));
  const list = useAdminList('/api/v1/admin/audit-logs', { ...filters, limit, offset });
  const [open, setOpen] = useState(null);

  const update = (changes) => {
    const p = new URLSearchParams(params);
    Object.entries(changes).forEach(([k, v]) => (v ? p.set(k, v) : p.delete(k)));
    if (!('offset' in changes)) p.delete('offset');
    setParams(p);
  };
  const sortProps = { sort: filters.sort, order: filters.order, onSort: (sort, order) => update({ sort, order }) };
  const active = FILTER_KEYS.some((k) => k !== 'sort' && k !== 'order' && filters[k]);
  const exportQuery = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString();

  return (
    <>
      <PageTitle title="Audit log" subtitle="Who did what, when. Entries cannot be edited or deleted.">
        <a className="adm-btn adm-btn--ghost" href={`/api/v1/admin/audit-logs/export${exportQuery ? `?${exportQuery}` : ''}`}
          download title="Download the entries matching the current filters (up to 10,000)">Export CSV</a>
      </PageTitle>
      <div className="adm-toolbar" role="search">
        <SearchBox value={filters.q} onChange={(v) => update({ q: v })} placeholder="Search actor, action, resource, IP" />
        <select className="adm-input" value={PRESETS.some(([v]) => v === filters.action) ? filters.action : ''}
          onChange={(e) => update({ action: e.target.value })} aria-label="Action type">
          {PRESETS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <select className="adm-input" value={filters.outcome} onChange={(e) => update({ outcome: e.target.value })} aria-label="Outcome">
          <option value="">Any outcome</option><option value="success">Success</option><option value="failure">Failure</option><option value="denied">Denied</option>
        </select>
        <span className="adm-toolbar__dates">
          <label htmlFor="al-from">From</label>
          <input id="al-from" className="adm-input" type="date" value={filters.date_from} max={filters.date_to || undefined}
            onChange={(e) => update({ date_from: e.target.value })} />
          <label htmlFor="al-to">to</label>
          <input id="al-to" className="adm-input" type="date" value={filters.date_to} min={filters.date_from || undefined}
            onChange={(e) => update({ date_to: e.target.value })} />
        </span>
        {active && (
          <button type="button" className="adm-btn adm-btn--ghost adm-btn--sm"
            onClick={() => update({ q: '', action: '', outcome: '', date_from: '', date_to: '' })}>Clear filters</button>
        )}
      </div>
      <div className="adm-table-wrap">
        <table className="adm-table">
          <thead>
            <tr>
              <SortHeader label="When" field="occurred_at" {...sortProps} />
              <SortHeader label="Actor" field="actor" {...sortProps} />
              <SortHeader label="Action" field="action" {...sortProps} />
              <SortHeader label="Resource" field="resource" {...sortProps} />
              <SortHeader label="Outcome" field="outcome" {...sortProps} />
              <SortHeader label="IP" field="ip" {...sortProps} />
            </tr>
          </thead>
          <tbody>
            <StateRow state={list} cols={6} empty="No audit entries match." />
            {list.data?.items.map((e) => (
              <tr key={e.id} className="adm-row-link" tabIndex={0} onClick={() => setOpen(e)} onKeyDown={(ev) => { if (ev.key === 'Enter') setOpen(e); }}>
                <td className="adm-muted adm-nowrap">{dateTime(e.occurred_at)}</td>
                <td>{e.actor_email || e.actor_type}</td>
                <td className="adm-mono">{e.action}</td>
                <td>{e.resource_type ? `${e.resource_type} ${e.resource_id || ''}` : '—'}</td>
                <td><Badge value={e.outcome} /></td>
                <td className="adm-mono">{e.ip || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={list.data} limits={LIMITS} onChange={(o) => update({ offset: String(o) })}
        onLimit={(n) => update({ limit: String(n) })} />
      {open && (
        <Drawer title={open.action} onClose={() => setOpen(null)}>
          <dl className="adm-dl">
            <dt>When</dt><dd>{dateTime(open.occurred_at)}</dd>
            <dt>Actor</dt><dd>{open.actor_email || '—'} ({open.actor_type}{open.actor_id ? ` #${open.actor_id}` : ''})</dd>
            <dt>Outcome</dt><dd><Badge value={open.outcome} /></dd>
            <dt>Resource</dt><dd>{open.resource_type || '—'} {open.resource_id || ''}</dd>
            <dt>IP</dt><dd>{open.ip || '—'}</dd>
            <dt>Request id</dt><dd className="adm-mono">{open.request_id || '—'}</dd>
          </dl>
          <h3>Details</h3>
          <pre className="adm-json">{open.details ? JSON.stringify(open.details, null, 2) : '—'}</pre>
        </Drawer>
      )}
    </>
  );
}
