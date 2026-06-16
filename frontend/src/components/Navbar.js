import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { getToken, logout } from '../api/authApi';
import { usePremium } from './PremiumGate';
import './Navbar.css';

const Navbar = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [toolsOpen, setToolsOpen] = useState(false);
    const [isLoggedIn, setIsLoggedIn] = useState(false);
    const navigate = useNavigate();
    const location = useLocation();
    const { premium } = usePremium();

    useEffect(() => {
        const handleLogin = () => setIsLoggedIn(true);
        window.addEventListener('login', handleLogin);

        setIsLoggedIn(!!getToken());

        return () => {
            window.removeEventListener('login', handleLogin);
        };
    }, []);

    // Close the mobile drawer + Tools dropdown on every navigation.
    useEffect(() => {
        setIsOpen(false);
        setToolsOpen(false);
    }, [location.pathname]);

    // Lock background scroll while the drawer is open.
    useEffect(() => {
        document.body.style.overflow = isOpen ? 'hidden' : '';
        return () => {
            document.body.style.overflow = '';
        };
    }, [isOpen]);

    const toggleMenu = () => setIsOpen((v) => !v);
    const closeMenu = () => setIsOpen(false);

    const handleLogout = () => {
        logout();
        setIsLoggedIn(false);
        navigate('/login');
    };

    return (
        <nav className="navbar">
            <Link to="/" className="navbar-brand">NutriTech</Link>
            <button
                className="menu-icon"
                onClick={toggleMenu}
                aria-label={isOpen ? 'Close menu' : 'Open menu'}
                aria-expanded={isOpen}
            >
                {isOpen ? '✕' : '☰'}
            </button>
            <div
                className={`nav-backdrop ${isOpen ? 'active' : ''}`}
                onClick={closeMenu}
            />
            <ul className={`navbar-nav ${isOpen ? 'active' : ''}`}>
                {isLoggedIn && (
                    <li className="nav-item">
                        <Link
                            to="/pricing"
                            className={`nav-link premium-link ${premium ? 'is-premium' : ''}`}
                            onClick={closeMenu}
                        >
                            {premium ? '★ Premium' : '✨ Get Premium'}
                        </Link>
                    </li>
                )}

                {/* ---- Features ---- */}
                <li className="nav-section">Features</li>
                <li className="nav-item">
                    <Link to="/meal-planner" className="nav-link" onClick={closeMenu}>Meal Planner</Link>
                </li>
                <li className="nav-item">
                    <Link to="/image-recognition" className="nav-link" onClick={closeMenu}>Image Recognition</Link>
                </li>
                <li className="nav-item">
                    <Link to="/chatbot" className="nav-link" onClick={closeMenu}>Chatbot</Link>
                </li>

                {/* ---- Tools (dropdown on desktop, inline-expand in drawer) ---- */}
                <li className={`nav-item nav-dropdown ${toolsOpen ? 'open' : ''}`}>
                    <button
                        className="nav-link tools-toggle"
                        onClick={() => setToolsOpen((v) => !v)}
                        aria-expanded={toolsOpen}
                    >
                        Tools <span className="tools-caret">▾</span>
                    </button>
                    {toolsOpen && (
                        <ul className="nav-submenu">
                            <li>
                                <Link to="/macros-calculator" className="nav-link" onClick={closeMenu}>Macros Calculator</Link>
                            </li>
                            <li>
                                <Link to="/food-search" className="nav-link" onClick={closeMenu}>Food Search</Link>
                            </li>
                        </ul>
                    )}
                </li>

                

                {/* ---- Account ---- */}
                <li className="nav-section">Account</li>
                {isLoggedIn ? (
                    <>
                        <li className="nav-item">
                            <Link to="/profile" className="nav-link" onClick={closeMenu}>Profile</Link>
                        </li>
                        <li className="nav-item">
                            <button onClick={handleLogout} className="nav-link logout-btn">Logout</button>
                        </li>
                    </>
                ) : (
                    <>
                        <li className="nav-item">
                            <Link to="/login" className="nav-link" onClick={closeMenu}>Login</Link>
                        </li>
                        <li className="nav-item">
                            <Link to="/register" className="nav-link" onClick={closeMenu}>Register</Link>
                        </li>
                    </>
                )}
            </ul>
        </nav>
    );
};

export default Navbar;
