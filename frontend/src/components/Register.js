import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { register } from '../api/authApi';
import './Register.css';

// Mirrors the backend complexity rules in app/schemas/auth.py
const PWD_RULES = [
    { test: (p) => p.length >= 8, label: 'At least 8 characters' },
    { test: (p) => /[a-z]/.test(p), label: 'One lowercase letter' },
    { test: (p) => /[A-Z]/.test(p), label: 'One uppercase letter' },
    { test: (p) => /\d/.test(p), label: 'One digit' },
    { test: (p) => /[^A-Za-z0-9]/.test(p), label: 'One symbol' },
];

const STRENGTH = ['Very weak', 'Weak', 'Fair', 'Good', 'Strong'];

const Register = () => {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);
    const navigate = useNavigate();

    const passed = PWD_RULES.filter((r) => r.test(password)).length;
    const allValid = passed === PWD_RULES.length;
    const strengthIdx = Math.max(0, passed - 1);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setSuccess(false);

        if (!allValid) {
            setError('Password does not meet the requirements.');
            return;
        }

        try {
            await register(name, email, password);
            setSuccess(true);
            setTimeout(() => {
                navigate('/login');
            }, 2000);
        } catch (error) {
            setError(error.message);
        }
    };

    return (
        <div className="register-container">
            <form className="register-form" onSubmit={handleSubmit}>
                <div className="auth-head">
                    <h2>Create your account</h2>
                    <p className="auth-sub">Start your journey with NutriTech</p>
                </div>
                {error && <p className="error">{error}</p>}
                {success && <p className="success">Registration successful! Redirecting to login...</p>}
                <div className="form-group">
                    <label htmlFor="name">Name</label>
                    <input
                        type="text"
                        id="name"
                        placeholder="Your name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        required
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="email">Email</label>
                    <input
                        type="email"
                        id="email"
                        placeholder="you@example.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="password">Password</label>
                    <input
                        type="password"
                        id="password"
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                    />
                    {password && (
                        <div className="pwd-strength">
                            <div className="pwd-bar">
                                <div
                                    className={`pwd-bar-fill lvl-${strengthIdx}`}
                                    style={{ width: `${(passed / PWD_RULES.length) * 100}%` }}
                                />
                            </div>
                            <span className={`pwd-label lvl-${strengthIdx}`}>{STRENGTH[strengthIdx]}</span>
                            <ul className="pwd-rules">
                                {PWD_RULES.map((r) => (
                                    <li key={r.label} className={r.test(password) ? 'ok' : ''}>
                                        {r.test(password) ? '✓' : '○'} {r.label}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
                <button type="submit">Create Account</button>
                <p className="auth-switch">
                    Already have an account? <Link to="/login">Log in</Link>
                </p>
            </form>
        </div>
    );
};

export default Register;
