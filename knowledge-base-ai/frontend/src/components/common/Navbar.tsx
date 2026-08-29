/**
 * Top navigation bar — displays app title and a link to Settings.
 */
import { Link } from 'react-router-dom';

export default function Navbar() {
  return (
    <header className="navbar" role="banner">
      <Link to="/" className="navbar__brand">
        Knowledge Base AI
      </Link>
      <nav aria-label="Header navigation" className="navbar__actions">
        <Link to="/settings" className="navbar__link">
          Settings
        </Link>
      </nav>
    </header>
  );
}
