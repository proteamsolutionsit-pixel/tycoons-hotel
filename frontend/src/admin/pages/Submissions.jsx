import { Fragment, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../../services/api';
import { dateTime, longDate } from '../../utils/format';
import { useAuth } from '../auth';
import { Badge, Drawer, Notice, PageTitle, Pager, SearchBox, StateRow, useAdminList } from '../ui';

const TABS = {
  'table-reservations': {
    label: 'Table reservations',
    cols: [['Guest', (r) => <>{r.name}<br /><span className="adm-muted">{r.phone}</span></>],
      ['When', (r) => `${longDate(r.reservation_date)} ${r.reservation_time.slice(0, 5)}`], ['Guests', (r) => r.party_size],
      ['Occasion', (r) => r.occasion]],
    detail: (r) => [['Name', r.name], ['Phone', <a href={`tel:${r.phone}`}>{r.phone}</a>], ['Date', longDate(r.reservation_date)],
      ['Time', r.reservation_time.slice(0, 5)], ['Guests', r.party_size], ['Occasion', r.occasion], ['Requests', r.special_requests]],
  },
  'spa-appointments': {
    label: 'Spa appointments',
    cols: [['Guest', (r) => <>{r.name}<br /><span className="adm-muted">{r.phone}</span></>], ['Treatment', (r) => r.treatment_name],
      ['When', (r) => `${longDate(r.preferred_date)} ${r.preferred_time.slice(0, 5)}`], ['Type', (r) => r.guest_type.replace('_', ' ')]],
    detail: (r) => [['Name', r.name], ['Phone', <a href={`tel:${r.phone}`}>{r.phone}</a>], ['Treatment', r.treatment_name],
      ['Guest type', r.guest_type.replace('_', ' ')], ['Date', longDate(r.preferred_date)], ['Time', r.preferred_time.slice(0, 5)]],
  },
  enquiries: {
    label: 'Enquiries',
    cols: [['From', (r) => <>{r.name}<br /><span className="adm-muted">{r.email}</span></>], ['Type', (r) => (r.kind === 'business' ? `Business · ${r.company}` : r.topic)],
      ['Message', (r) => (r.message || '').slice(0, 80)]],
    detail: (r) => [['Type', r.kind], ['Name', r.name], ['Email', <a href={`mailto:${r.email}`}>{r.email}</a>], ['Phone', r.phone],
      ['Topic', r.topic], ['Company', r.company], ['Arrival', r.arrival_date && longDate(r.arrival_date)], ['Guests', r.guests], ['Message', r.message]],
  },
  applications: {
    label: 'Job applications',
    cols: [['Applicant', (r) => <>{r.name}<br /><span className="adm-muted">{r.email}</span></>], ['Position', (r) => r.position], ['CV', (r) => (r.has_cv ? 'Yes' : '—')]],
    detail: (r) => [['Name', r.name], ['Email', <a href={`mailto:${r.email}`}>{r.email}</a>], ['Phone', r.phone], ['Position', r.position],
      ['Message', r.message], ['CV', r.has_cv ? <a href={`/api/admin/submissions/applications/${r.id}/cv`}>Download {r.cv_original_name}</a> : 'None']],
  },
};

export default function Submissions() {
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'newsletter' ? 'newsletter' : TABS[params.get('tab')] ? params.get('tab') : 'table-reservations';
  return (
    <>
      <PageTitle title="Guest requests" />
      <div className="adm-tabs" role="tablist">
        {[...Object.entries(TABS).map(([k, v]) => [k, v.label]), ['newsletter', 'Newsletter']].map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={k === tab} onClick={() => setParams({ tab: k })}>{label}</button>
        ))}
      </div>
      {tab === 'newsletter' ? <Newsletter /> : <SubmissionList key={tab} kind={tab} />}
    </>
  );
}

function SubmissionList({ kind }) {
  const cfg = TABS[kind];
  const [status, setStatus] = useState('');
  const [q, setQ] = useState('');
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(null);
  const list = useAdminList(`/api/admin/submissions/${kind}`, { status, q, offset, limit: 25 });

  return (
    <>
      <div className="adm-toolbar">
        <SearchBox value={q} onChange={(v) => { setQ(v); setOffset(0); }} />
        <select className="adm-input" value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }} aria-label="Status">
          <option value="">All statuses</option>
          {['new', 'in_progress', 'confirmed', 'closed'].map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
        </select>
      </div>
      <div className="adm-table-wrap">
        <table className="adm-table">
          <thead><tr>{cfg.cols.map(([l]) => <th key={l}>{l}</th>)}<th>Status</th><th>Received</th></tr></thead>
          <tbody>
            <StateRow state={list} cols={cfg.cols.length + 2} empty="No requests yet." />
            {list.data?.items.map((r) => (
              <tr key={r.id} className="adm-row-link" tabIndex={0} onClick={() => setOpen(r)} onKeyDown={(e) => { if (e.key === 'Enter') setOpen(r); }}>
                {cfg.cols.map(([l, fn]) => <td key={l}>{fn(r)}</td>)}
                <td><Badge value={r.status} /></td>
                <td className="adm-muted">{dateTime(r.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={list.data} onChange={setOffset} />
      {open && <SubmissionDetail kind={kind} item={open} cfg={cfg} onClose={() => setOpen(null)} onSaved={(r) => { setOpen(r); list.reload(); }} />}
    </>
  );
}

function SubmissionDetail({ kind, item, cfg, onClose, onSaved }) {
  const { handleError } = useAuth();
  const [status, setStatus] = useState(item.status);
  const [notes, setNotes] = useState(item.staff_notes || '');
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.patch(`/api/admin/submissions/${kind}/${item.id}`, { status, staff_notes: notes || null });
      setNotice({ type: 'success', message: 'Saved.' });
      onSaved(r);
    } catch (err) { handleError(err); setNotice({ type: 'error', message: err.message }); } finally { setBusy(false); }
  };
  return (
    <Drawer title={`${cfg.label.replace(/s$/, '')} #${item.id}`} onClose={onClose}>
      <Notice notice={notice} />
      <dl className="adm-dl">
        {cfg.detail(item).filter(([, v]) => v !== null && v !== undefined && v !== '').map(([k, v]) => (
          <Fragment key={k}><dt>{k}</dt><dd style={{ whiteSpace: 'pre-wrap' }}>{v}</dd></Fragment>
        ))}
        <dt>Received</dt><dd>{dateTime(item.created_at)}</dd>
      </dl>
      <form className="adm-form" onSubmit={save}>
        <div className="adm-field"><label htmlFor="s-status">Status</label>
          <select id="s-status" className="adm-input" value={status} onChange={(e) => setStatus(e.target.value)}>
            {['new', 'in_progress', 'confirmed', 'closed'].map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
          </select></div>
        <div className="adm-field adm-field--wide"><label htmlFor="s-notes">Staff notes</label>
          <textarea id="s-notes" className="adm-input" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={4000} /></div>
        <div className="adm-form__actions"><button className="adm-btn" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save'}</button></div>
      </form>
    </Drawer>
  );
}

function Newsletter() {
  const { handleError } = useAuth();
  const [q, setQ] = useState('');
  const [offset, setOffset] = useState(0);
  const list = useAdminList('/api/admin/submissions/newsletter', { q, offset, limit: 50 });
  const toggle = async (s) => {
    try { await api.patch(`/api/admin/submissions/newsletter/${s.id}`, { is_active: !s.is_active }); list.reload(); }
    catch (err) { handleError(err); window.alert(err.message); }
  };
  return (
    <>
      <div className="adm-toolbar"><SearchBox value={q} onChange={(v) => { setQ(v); setOffset(0); }} placeholder="Email" /></div>
      <div className="adm-table-wrap">
        <table className="adm-table">
          <thead><tr><th>Email</th><th>Subscribed</th><th>Status</th><th /></tr></thead>
          <tbody>
            <StateRow state={list} cols={4} empty="No subscribers yet." />
            {list.data?.items.map((s) => (
              <tr key={s.id}>
                <td>{s.email}</td><td className="adm-muted">{dateTime(s.consent_at)}</td>
                <td><Badge value={s.is_active ? 'active' : 'unsubscribed'} /></td>
                <td><button type="button" className="adm-btn adm-btn--ghost" onClick={() => toggle(s)}>{s.is_active ? 'Unsubscribe' : 'Resubscribe'}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={list.data} onChange={setOffset} />
    </>
  );
}
