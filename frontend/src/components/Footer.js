import React from 'react';
import { Link } from 'react-router-dom';
import './Footer.css';

const Footer = () => {
    return (
        <footer className="footer">
            <div className="footer-inner">
                <div className="footer-brand-col">
                    <Link to="/" className="footer-brand">NutriTech</Link>
                    <p className="footer-tagline">AI-powered nutrition, personalized.</p>
                </div>

                <div className="footer-col">
                    <h4>Features</h4>
                    <Link to="/meal-planner">Meal Planner</Link>
                    <Link to="/image-recognition">Image Recognition</Link>
                    <Link to="/chatbot">Chatbot</Link>
                </div>

                <div className="footer-col">
                    <h4>Tools</h4>
                    <Link to="/macros-calculator">Macros Calculator</Link>
                    <Link to="/food-search">Food Search</Link>
                </div>

                <div className="footer-col">
                    <h4>Account</h4>
                    <Link to="/">Home</Link>
                    <Link to="/pricing">Pricing</Link>
                    <Link to="/profile">Profile</Link>
                </div>
            </div>
            <p className="footer-copy">&copy; 2026 NutriTech. All rights reserved.</p>
        </footer>
    );
};

export default Footer;
