import { rupees } from '../../utils/format';
import ResourceManager from '../ResourceManager';
import { Badge, PageTitle } from '../ui';

const FIELDS = [
  { name: 'name', label: 'Name' },
  { name: 'slug', label: 'Slug (URL id)', createOnly: true, help: 'Lowercase letters, numbers and hyphens, e.g. junior-suite' },
  { name: 'base_rate_paise', label: 'Rate per night, before tax', type: 'money', min: 1 },
  { name: 'total_rooms', label: 'Rooms available to sell', type: 'number', min: 0 },
  { name: 'max_adults', label: 'Max adults', type: 'number', min: 1 },
  { name: 'max_children', label: 'Max children', type: 'number', min: 0 },
  { name: 'summary', label: 'Homepage carousel text', type: 'textarea', rows: 2, wide: true },
  { name: 'description', label: 'Rooms page description', type: 'textarea', wide: true },
  { name: 'size_label', label: 'Fact: room size' },
  { name: 'bed_label', label: 'Fact: bed type' },
  { name: 'view_label', label: 'Fact: view' },
  { name: 'occupancy_label', label: 'Fact: occupancy' },
  { name: 'image_url', label: 'Photo', type: 'image', wide: true },
  { name: 'image_alt', label: 'Photo description (alt text)', wide: true },
  { name: 'sort_order', label: 'Order', type: 'number' },
  { name: 'is_signature', label: 'Signature styling (gold frame)', type: 'checkbox' },
  { name: 'is_active', label: 'Bookable and shown on the site', type: 'checkbox' },
];

export default function RoomTypes() {
  return (
    <>
      <PageTitle title="Rooms & rates" />
      <p className="adm-muted">Rates apply to new bookings only; existing bookings keep the price they were made at.</p>
      <ResourceManager endpoint="/api/admin/room-types" noun="Room type" fields={FIELDS}
        defaults={{ max_adults: 2, max_children: 1, total_rooms: 1, is_active: true, sort_order: 10 }}
        columns={[
          { label: 'Order', key: 'sort_order' },
          { label: 'Room', key: 'name' },
          { label: 'Rate / night', render: (r) => rupees(r.base_rate_paise) },
          { label: 'Inventory', key: 'total_rooms' },
          { label: 'Sleeps', render: (r) => `${r.max_adults} + ${r.max_children}` },
          { label: 'Status', render: (r) => <Badge value={r.is_active ? 'active' : 'hidden'} /> },
        ]} />
    </>
  );
}
