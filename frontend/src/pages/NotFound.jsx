import { Link } from 'react-router-dom';
import { usePageMotion } from '../motion/usePageMotion';

export default function NotFound() {
  usePageMotion(true);
  return (
    <section className="page-head not-found" aria-labelledby="page-title">
      <div className="wrap stack">
        <p className="kicker">Page not found</p>
        <h1 id="page-title">We couldn’t find that page.</h1>
        <p className="intro__body">It may have moved. Everything at the hotel is a short walk from the homepage.</p>
        <div className="actions"><Link className="btn" to="/">Return home</Link><Link className="link" to="/contact">Contact us</Link></div>
      </div>
    </section>
  );
}
