/* Site-wide settings (address, phones, hours, detail strips...) loaded once
   from GET /api/site and shared by the header, footer and pages. */
import { createContext, useContext, useMemo } from 'react';
import { siteApi } from '../services/api';
import { useApi } from '../hooks/useApi';
import { withoutPlaceholders } from '../utils/format';

// Settings used as-is (links and machine values, never shown as text)
const RAW_KEYS = new Set(['phone_tel', 'reservations_email', 'map_embed_url', 'dining_menu_pdf_url',
  'instagram_url', 'facebook_url', 'linkedin_url', 'booking_terms_version', 'room_tax_percent']);

/** Only what the hotel has filled in reaches the pages: [placeholders] are removed
    from text, and list items / label-value rows that were only placeholders are dropped. */
export function cleanSettings(settings) {
  const out = {};
  Object.entries(settings || {}).forEach(([key, value]) => {
    if (RAW_KEYS.has(key) || value === null || typeof value !== 'string' && !Array.isArray(value)) {
      out[key] = value;
    } else if (typeof value === 'string') {
      out[key] = withoutPlaceholders(value);
    } else {
      out[key] = value
        .map((item) => (typeof item === 'string' ? withoutPlaceholders(item)
          : item && typeof item === 'object'
            ? { ...item, label: withoutPlaceholders(item.label), value: withoutPlaceholders(item.value) } : item))
        .filter((item) => (typeof item === 'string' ? item : item && item.value));
    }
  });
  return out;
}

const SiteContext = createContext({ settings: {}, loading: true, error: null });

export function SiteProvider({ children }) {
  const { data, loading, error, reload } = useApi(siteApi.site, []);
  const value = useMemo(() => ({ settings: cleanSettings(data?.settings), loading, error, reload }), [data, loading, error, reload]);
  return <SiteContext.Provider value={value}>{children}</SiteContext.Provider>;
}

export function useSite() {
  return useContext(SiteContext);
}

/** Convenience accessors used across components */
export function useContact() {
  const { settings: s } = useSite();
  return {
    street: s.address_street || '',
    city: s.address_city || '',
    regionPin: s.address_region_pin || '',
    phone: s.phone_display || '',
    tel: s.phone_display && s.phone_tel ? 'tel:' + String(s.phone_tel).replace(/[^\d+]/g, '') : undefined,
    // Extra landlines: rows with a real number (placeholders like "[Landline number]" have no tel: link)
    landlines: (Array.isArray(s.landline_numbers) ? s.landline_numbers : [])
      .filter((r) => r && r.value)
      .map((r) => ({ label: r.label, number: r.value, tel: /\d/.test(r.value) ? 'tel:' + r.value.replace(/[^\d+]/g, '') : undefined })),
    email: s.reservations_email_display || '',
    mailto: s.reservations_email_display && s.reservations_email ? 'mailto:' + s.reservations_email : undefined,
  };
}
