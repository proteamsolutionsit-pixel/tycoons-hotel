/* Admin icon set: 20px stroke icons, decorative (aria-hidden); every use sits
   beside a visible text label. */
const base = { width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.6,
  strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true, focusable: 'false' };
const I = (paths) => function Icon(props) { return <svg {...base} {...props}>{paths}</svg>; };

export const IconDashboard = I(<><rect x="3" y="3" width="7" height="9" rx="1" /><rect x="14" y="3" width="7" height="5" rx="1" /><rect x="14" y="12" width="7" height="9" rx="1" /><rect x="3" y="16" width="7" height="5" rx="1" /></>);
export const IconCalendar = I(<><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></>);
export const IconBed = I(<><path d="M3 18V7M3 13h18v5M21 18v-3a3 3 0 0 0-3-3h-8v1" /><circle cx="7" cy="10" r="1.6" /></>);
export const IconCard = I(<><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 10h18M7 15h4" /></>);
export const IconInbox = I(<><path d="M4 13l2-8h12l2 8v6H4z" /><path d="M4 13h5l1 2h4l1-2h5" /></>);
export const IconTag = I(<><path d="M3 12V4h8l10 10-8 8z" /><circle cx="7.5" cy="7.5" r="1.4" /></>);
export const IconImage = I(<><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="9" cy="10" r="2" /><path d="M21 17l-5-5-9 8" /></>);
export const IconSliders = I(<><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0" /><circle cx="16" cy="6" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="18" r="2" /></>);
export const IconUsers = I(<><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0" /><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6" /></>);
export const IconShield = I(<><path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z" /><path d="M9 12l2 2 4-4" /></>);
export const IconLock = I(<><rect x="4" y="10" width="16" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>);
export const IconKey = I(<><circle cx="8" cy="15" r="4" /><path d="M10.8 12.2L20 3M16 7l3 3M14 9l2 2" /></>);
export const IconUser = I(<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>);
export const IconLogout = I(<><path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h11" /></>);
export const IconMenu = I(<path d="M4 7h16M4 12h16M4 17h16" />);
export const IconClose = I(<path d="M6 6l12 12M18 6L6 18" />);
export const IconAlert = I(<><path d="M12 3l9.5 17h-19z" /><path d="M12 10v4M12 17.5v.01" /></>);
export const IconCheck = I(<path d="M5 12.5l4.5 4.5L19 7" />);
export const IconInfo = I(<><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.01" /></>);
export const IconArrowUp = I(<path d="M12 19V5M6 11l6-6 6 6" />);
export const IconArrowDown = I(<path d="M12 5v14M6 13l6 6 6-6" />);
export const IconSort = I(<path d="M8 9l4-4 4 4M8 15l4 4 4-4" />);
export const IconExternal = I(<><path d="M14 4h6v6M20 4l-9 9" /><path d="M18 14v5H5V6h5" /></>);
export const IconRefresh = I(<><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 5v6h-6" /></>);
