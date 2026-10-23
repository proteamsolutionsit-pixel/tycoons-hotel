import { lazy, Suspense, useLayoutEffect } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { SiteProvider } from './context/SiteContext';
import SiteLayout from './layouts/SiteLayout';
import Book from './pages/Book';
import BookingStatus from './pages/BookingStatus';
import Careers from './pages/Careers';
import Contact from './pages/Contact';
import Dining from './pages/Dining';
import FindBooking from './pages/FindBooking';
import Gallery from './pages/Gallery';
import Home from './pages/Home';
import Meetings from './pages/Meetings';
import NotFound from './pages/NotFound';
import Rooms from './pages/Rooms';
import Wellness from './pages/Wellness';

// The staff admin is its own chunk; guests never download it.
const AdminApp = lazy(() => import('./admin/AdminApp'));

const LEGACY_VIEWS = new Set(['home', 'rooms', 'dining', 'wellness', 'meetings', 'gallery', 'careers', 'contact']);

/* Old links from the standalone HTML used hash routes (#rooms/book).
   Translate them to real URLs (/rooms#book). */
function LegacyHashRedirect() {
  const location = useLocation();
  const navigate = useNavigate();
  useLayoutEffect(() => {
    if (location.pathname !== '/' || !location.hash) return;
    const [view, anchor] = decodeURIComponent(location.hash.slice(1)).split('/');
    if (!LEGACY_VIEWS.has(view)) return;
    const path = view === 'home' ? '/' : `/${view}`;
    navigate(path + (anchor ? `#${anchor}` : ''), { replace: true });
  }, [location, navigate]);
  return null;
}

export default function App() {
  return (
    <SiteProvider>
      <LegacyHashRedirect />
      <Routes>
        <Route path="/admin/*" element={<Suspense fallback={null}><AdminApp /></Suspense>} />
        <Route element={<SiteLayout />}>
          <Route index element={<Home />} />
          <Route path="rooms" element={<Rooms />} />
          <Route path="dining" element={<Dining />} />
          <Route path="wellness" element={<Wellness />} />
          <Route path="meetings" element={<Meetings />} />
          <Route path="lounge" element={<Navigate to="/meetings" replace />} />
          <Route path="gallery" element={<Gallery />} />
          <Route path="careers" element={<Careers />} />
          <Route path="contact" element={<Contact />} />
          <Route path="book" element={<Book />} />
          <Route path="booking/find" element={<FindBooking />} />
          <Route path="booking/:reference" element={<BookingStatus />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </SiteProvider>
  );
}
