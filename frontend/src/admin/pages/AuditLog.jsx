/* Read-only audit trail (append-only in the database). */
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { dateTime } from '../../utils/format';
import { Badge, Drawer, PageTitle, Pager, SearchBox, StateRow, useAdminList } from '../ui';

const PRESETS = [['', 'All actions'], ['auth.', 'Sign-ins & passwords'], ['security.', 'Security events'],
  ['booking.', 'Bookings'], ['payment.', 'Payments & refunds'], ['room_type.', 'Rooms & rates'],
  ['setting.', 'Site settings'], ['user.', 'Staff users']];

export default function AuditLog() {
  const [params, setParams] = useSearchParams();
  const action = params.get('action') || '';
  const outcome = params.get('outcome') || '';
  const offset = Number(params.get('offset') || 0);
  const list = useAdminList('/api/v1/admin/audit-logs', { action, outcome, offset, limit: 50 });
  const [open, setOpen] = useState(null);
  const update = (changes) => {
    const p = new URLSearchParams(params);
    Object.entries(changes).forEach(([k, v]) => (v ? p.set(k, v) : p.delete(k)));
    if (!('offset' in changes)) p.delete('offset');
    setParams(p);
  };

  return (
    <>
      <PageTitle title="Audit log" subtitle="Who did what, when. Entries cannot be edited or deleted." />
      <div className="adm-toolbar" role="search">
        <select className="adm-input" value={PRESETS.some(([v]) => v === action) ? action : ''} onChange={(e) => update({ action: e.target.value })} aria-label="Action type">
          {PRESETS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <SearchBox value={action} onChange={(v) => update({ action: v })} placeholder="Action starts with… e.g. booking.cancel" />
        <select className="adm-input" value={outcome} onChange={(e) => update({ outcome: e.target.value })} aria-label="Outcome">
          <option value="">Any outcome</option><option value="success">Success</option><option value="failure">Failure</option><option value="denied">Denied</option>
        </select>
      </div>
      <div className="adm-table-wrap">
        <table className="adm-table">
          <thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Resource</th><th>Outcome</th><th>IP</th></tr></thead>
          <tbody>
            <StateRow state={list} cols={6} empty="No audit entries match." />
            {list.data?.items.map((e) => (
              <tr key={e.id} className="adm-row-link" tabIndex={0} onClick={() => setOpen(e)} onKeyDown={(ev) => { if (ev.key === 'Enter') setOpen(e); }}>
                <td className="adm-muted">{dateTime(e.occurred_at)}</td>
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
      <Pager page={list.data} onChange={(o) => update({ offset: String(o) })} />
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
