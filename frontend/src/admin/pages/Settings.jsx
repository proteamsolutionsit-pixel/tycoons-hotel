/* Site settings: one editor per setting, shaped by its current value
   (text, number, list of lines, or label/value rows). */
import { useEffect, useState } from 'react';
import { api } from '../../services/api';
import { useAuth } from '../auth';
import { Notice, PageTitle, useAdminList, useToast } from '../ui';

// Settings edited as label/value rows even when they currently hold no rows
const PAIR_KEYS = new Set(['landline_numbers', 'stay_details', 'getting_here', 'dining_details', 'spa_details']);
const PAIR_LABELS = { landline_numbers: ['Label (e.g. Reception)', 'Number (with STD code)'] };

const GROUPS = { contact: 'Contact details', social: 'Social links', home: 'Homepage', rooms: 'Rooms & booking',
  dining: 'Fishy Tales', wellness: 'Kai Wellness Spa', lounge: 'Business Lounge', general: 'General' };

export default function Settings() {
  const list = useAdminList('/api/v1/admin/settings');
  const groups = {};
  (list.data || []).forEach((s) => { (groups[s.group] ||= []).push(s); });
  return (
    <>
      <PageTitle title="Site settings" />
      <p className="adm-notice adm-notice--info">Values in [brackets] are the design’s placeholders. Replace them with the hotel’s real details. Every change is recorded in the audit log.</p>
      {list.error && <p className="adm-error">{list.error.message}</p>}
      {Object.entries(groups).map(([g, items]) => (
        <section key={g} className="adm-section">
          <h2>{GROUPS[g] || g}</h2>
          <div className="adm-settings">{items.map((s) => <SettingEditor key={s.key} setting={s} />)}</div>
        </section>
      ))}
    </>
  );
}

function SettingEditor({ setting }) {
  const { can, handleError } = useAuth();
  const toast = useToast();
  const isAdmin = can('settings.manage');
  const [value, setValue] = useState(setting.value);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => setValue(setting.value), [setting.value]);
  const isPairs = Array.isArray(setting.value) && (PAIR_KEYS.has(setting.key)
    || (setting.value.length > 0 && typeof setting.value[0] === 'object'));
  const [labelHint, valueHint] = PAIR_LABELS[setting.key] || ['Label', 'Value'];
  const isList = Array.isArray(setting.value) && !isPairs;
  const isNumber = typeof setting.value === 'number';
  const dirty = JSON.stringify(value) !== JSON.stringify(setting.value);

  const save = async () => {
    setBusy(true); setNotice(null);
    try {
      let v = value;
      if (isList) v = value.map((x) => x.trim()).filter(Boolean);
      if (isNumber) v = Number(value);
      const saved = await api.put(`/api/v1/admin/settings/${setting.key}`, { value: v });
      setting.value = saved.value;
      setValue(saved.value);
      toast(`Saved: ${setting.label}`);
    } catch (err) { handleError(err); setNotice({ type: 'error', message: err.message }); } finally { setBusy(false); }
  };

  const id = `set-${setting.key}`;
  let editor;
  if (isPairs) {
    editor = (
      <div className="adm-pairs">
        {value.map((row, i) => (
          <div className="adm-pair" key={i}>
            <input className="adm-input" aria-label={labelHint} placeholder={labelHint} value={row.label} disabled={!isAdmin}
              onChange={(e) => setValue(value.map((r, j) => (j === i ? { ...r, label: e.target.value } : r)))} />
            <input className="adm-input" aria-label={valueHint} placeholder={valueHint} value={row.value} disabled={!isAdmin}
              inputMode={setting.key === 'landline_numbers' ? 'tel' : undefined}
              onChange={(e) => setValue(value.map((r, j) => (j === i ? { ...r, value: e.target.value } : r)))} />
            {isAdmin && <button type="button" className="adm-btn adm-btn--ghost" onClick={() => setValue(value.filter((_, j) => j !== i))}>Remove</button>}
          </div>
        ))}
        {isAdmin && <button type="button" className="adm-btn adm-btn--ghost" style={{ justifySelf: 'start' }} onClick={() => setValue([...value, { label: '', value: '' }])}>{setting.key === 'landline_numbers' ? 'Add number' : 'Add row'}</button>}
      </div>
    );
  } else if (isList) {
    editor = <textarea id={id} className="adm-input" rows={Math.max(3, value.length + 1)} disabled={!isAdmin}
      value={value.join('\n')} onChange={(e) => setValue(e.target.value.split('\n'))} />;
  } else {
    editor = <input id={id} className="adm-input" type={isNumber ? 'number' : 'text'} step={isNumber ? '0.01' : undefined}
      disabled={!isAdmin} value={value ?? ''} onChange={(e) => setValue(e.target.value)} />;
  }
  return (
    <div className="adm-setting">
      <h3><label htmlFor={id}>{setting.label}</label></h3>
      {setting.help_text && <small className="adm-muted">{setting.help_text}</small>}
      {isList && <small className="adm-muted">One item per line.</small>}
      {editor}
      <Notice notice={notice} />
      {isAdmin && dirty && <div><button type="button" className="adm-btn" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save'}</button></div>}
    </div>
  );
}
