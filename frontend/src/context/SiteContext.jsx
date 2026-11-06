/* Site-wide settings (address, phones, hours, detail strips...) loaded once
   from GET /api/site and shared by the header, footer and pages. */
import { createContext, useContext, useMemo } from 'react';
import { siteApi } from '../services/api';
import { useApi } from '../hooks/useApi';

const SiteContext = createContext({ settings: {}, loading: true, error: null });

export function SiteProvider({ children }) {
  const { data, loading, error, reload } = useApi(siteApi.site, []);
  const value = useMemo(() => ({ settings: data?.settings || {}, loading, error, reload }), [data, loading, error, reload]);
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
    tel: s.phone_tel ? 'tel:' + String(s.phone_tel).replace(/[^\d+]/g, '') : undefined,
    // Extra landlines: rows with a real number (placeholders like "[Landline number]" have no tel: link)
    landlines: (Array.isArray(s.landline_numbers) ? s.landline_numbers : [])
      .filter((r) => r && r.value)
      .map((r) => ({ label: r.label, number: r.value, tel: /\d/.test(r.value) ? 'tel:' + r.value.replace(/[^\d+]/g, '') : undefined })),
    email: s.reservations_email_display || '',
    mailto: s.reservations_email ? 'mailto:' + s.reservations_email : undefined,
  };
}
