import { useSearchParams } from 'react-router-dom';
import ResourceManager from '../ResourceManager';
import { Badge, PageTitle } from '../ui';

const active = { label: 'Shown', sort: 'is_active', render: (r) => <Badge value={r.is_active ? 'active' : 'hidden'} /> };
const thumb = (key = 'image_url') => ({ label: 'Photo', render: (r) => <img src={r[key]} alt="" style={{ height: 44, width: 66, objectFit: 'cover' }} /> });

const TABS = {
  treatments: {
    label: 'Spa treatments', endpoint: '/api/v1/admin/spa-treatments', noun: 'Treatment',
    defaults: { duration_label: '', price_label: '', is_active: true },
    fields: [
      { name: 'name', label: 'Card title', help: 'e.g. Soothing Massages' },
      { name: 'form_label', label: 'Name in appointment form', help: 'e.g. Soothing Massage' },
      { name: 'slug', label: 'Slug', createOnly: true },
      { name: 'description', label: 'Description', type: 'textarea', wide: true },
      { name: 'duration_label', label: 'Duration', help: 'e.g. 60 min' },
      { name: 'price_label', label: 'Price text', help: 'e.g. From ₹3,500' },
      { name: 'image_url', label: 'Photo', type: 'image', wide: true },
      { name: 'image_alt', label: 'Photo description', wide: true },
      { name: 'sort_order', label: 'Order', type: 'number' },
      { name: 'is_active', label: 'Shown on the site', type: 'checkbox' },
    ],
    columns: [thumb(), { label: 'Treatment', key: 'name' }, { label: 'Duration', key: 'duration_label' }, { label: 'Price', key: 'price_label' }, active],
  },
  cards: {
    label: 'Page cards', endpoint: '/api/v1/admin/content-cards', noun: 'Card',
    defaults: { section: 'dining_menu', is_active: true },
    fields: [
      { name: 'section', label: 'Where it appears', type: 'select', options: [
        { value: 'dining_menu', label: 'Fishy Tales — Three ways to dine' },
        { value: 'lounge_spaces', label: 'Business Lounge — Work, meet, host' },
        { value: 'career_teams', label: 'Careers — Our teams' }] , wide: true },
      { name: 'title', label: 'Title' },
      { name: 'meta', label: 'Small print line', nullable: true },
      { name: 'body', label: 'Text', type: 'textarea', wide: true },
      { name: 'image_url', label: 'Photo', type: 'image', wide: true },
      { name: 'image_alt', label: 'Photo description', wide: true },
      { name: 'sort_order', label: 'Order', type: 'number' },
      { name: 'is_active', label: 'Shown on the site', type: 'checkbox' },
    ],
    columns: [thumb(), { label: 'Section', sort: 'section', render: (r) => r.section.replace(/_/g, ' ') }, { label: 'Title', key: 'title' }, { label: 'Order', key: 'sort_order' }, active],
  },
  gallery: {
    label: 'Gallery', endpoint: '/api/v1/admin/gallery', noun: 'Photo',
    defaults: { category: 'rooms', layout: 'normal', is_active: true, on_home: false },
    fields: [
      { name: 'image_url', label: 'Photo', type: 'image', wide: true },
      { name: 'alt', label: 'Caption / description', wide: true },
      { name: 'category', label: 'Filter', type: 'select', options: ['rooms', 'dining', 'wellness', 'spaces'] },
      { name: 'layout', label: 'Tile size', type: 'select', options: [{ value: 'normal', label: 'Normal' }, { value: 'large', label: 'Large (2×2)' }, { value: 'wide', label: 'Wide (2×1)' }] },
      { name: 'width', label: 'Width (px)', type: 'number', nullable: true },
      { name: 'height', label: 'Height (px)', type: 'number', nullable: true },
      { name: 'sort_order', label: 'Gallery order', type: 'number' },
      { name: 'home_order', label: 'Homepage order', type: 'number' },
      { name: 'on_home', label: 'Show on the homepage', type: 'checkbox' },
      { name: 'is_active', label: 'Shown on the site', type: 'checkbox' },
    ],
    columns: [thumb(), { label: 'Caption', key: 'alt' }, { label: 'Filter', key: 'category' }, { label: 'Tile', key: 'layout' },
      { label: 'Homepage', sort: 'home_order', render: (r) => (r.on_home ? `#${r.home_order}` : '—') }, active],
  },
  openings: {
    label: 'Job openings', endpoint: '/api/v1/admin/job-openings', noun: 'Opening',
    defaults: { employment_type: 'Full-time', is_active: true },
    fields: [
      { name: 'title', label: 'Role title' },
      { name: 'department', label: 'Department' },
      { name: 'employment_type', label: 'Type', help: 'e.g. Full-time' },
      { name: 'sort_order', label: 'Order', type: 'number' },
      { name: 'description', label: 'Notes (internal)', type: 'textarea', wide: true, nullable: true },
      { name: 'is_active', label: 'Listed on the Careers page', type: 'checkbox' },
    ],
    columns: [{ label: 'Role', key: 'title' }, { label: 'Department', key: 'department' }, { label: 'Type', key: 'employment_type' }, active],
  },
};

export default function Content() {
  const [params, setParams] = useSearchParams();
  const tab = TABS[params.get('tab')] ? params.get('tab') : 'treatments';
  const t = TABS[tab];
  return (
    <>
      <PageTitle title="Content" />
      <div className="adm-tabs" role="tablist">
        {Object.entries(TABS).map(([k, v]) => (
          <button key={k} type="button" role="tab" aria-selected={k === tab} onClick={() => setParams({ tab: k })}>{v.label}</button>
        ))}
      </div>
      <ResourceManager key={tab} {...t} managePermission="content.manage" />
    </>
  );
}
