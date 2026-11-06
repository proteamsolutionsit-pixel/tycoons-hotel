import { Link } from 'react-router-dom';
import { useContact, useSite } from '../context/SiteContext';

export default function Footer() {
  const c = useContact();
  const { settings: s } = useSite();
  return (
    <footer className="site-footer on-brand">
      <div className="wrap">
        <div className="site-footer__grid">
          <div className="site-footer__brand">
            <Link to="/" aria-label="The Tycoons Hotel, home">
              <img className="site-footer__logo" src="/assets/logo/logo-on-dark.png" alt="" width="361" height="208" loading="lazy" />
            </Link>
          </div>
          <nav aria-labelledby="f-explore">
            <h2 id="f-explore">Explore</h2>
            <ul>
              <li><Link className="u-draw" to="/rooms">Rooms &amp; Suites</Link></li>
              <li><Link className="u-draw" to="/dining">Fishy Tales</Link></li>
              <li><Link className="u-draw" to="/wellness">Kai Wellness Spa</Link></li>
              <li><Link className="u-draw" to="/meetings">Business Lounge</Link></li>
              <li><Link className="u-draw" to="/gallery">Gallery</Link></li>
              <li><Link className="u-draw" to="/careers">Careers</Link></li>
            </ul>
          </nav>
          <div>
            <h2>Contact</h2>
            <address>{c.street}<br />{c.city}{c.city && c.regionPin ? ', ' : ''}{c.regionPin}</address>
            <ul>
              <li><a className="u-draw" href={c.tel}>{c.phone}</a></li>
              {c.landlines.map((l, i) => (
                <li key={i}><a className="u-draw" href={l.tel}>{l.label ? `${l.label} · ` : ''}{l.number}</a></li>
              ))}
              <li><a className="u-draw" href={c.mailto}>{c.email}</a></li>
            </ul>
          </div>
          <div>
            <h2>Follow</h2>
            <ul>
              <li><a className="u-draw" href={s.instagram_url} rel="noopener noreferrer">Instagram</a></li>
              <li><a className="u-draw" href={s.facebook_url} rel="noopener noreferrer">Facebook</a></li>
              <li><a className="u-draw" href={s.linkedin_url} rel="noopener noreferrer">LinkedIn</a></li>
            </ul>
          </div>
        </div>
        <div className="site-footer__legal">
          <span>© {new Date().getFullYear()} The Tycoons Hotel. All rights reserved.</span>
          <div><Link className="u-draw" to="/contact">Terms &amp; Conditions</Link><Link className="u-draw" to="/contact">Privacy Policy</Link></div>
        </div>
      </div>
    </footer>
  );
}
