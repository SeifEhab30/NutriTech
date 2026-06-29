import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { login, getCurrentUser } from '../api/authApi';
import './Login.css';

const Login = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState(null);
    const [welcome, setWelcome] = useState(null);
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);

        try {
            await login(email, password);
            window.dispatchEvent(new Event('login'));
            const user = await getCurrentUser();
            setWelcome(user?.name || '');
            setTimeout(() => {
                navigate('/');
            }, 2000);
        } catch (error) {
            setError(error.message);
        }
    };

    return (
        <div className="login-container">
            <form className="login-form" onSubmit={handleSubmit}>
                <div className="auth-head">
                    <h2>Welcome back</h2>
                    <p className="auth-sub">Log in to continue to NutriTech</p>
                </div>
                {error && <p className="error">{error}</p>}
                {welcome !== null && <p className="success">Welcome {welcome}!</p>}
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
                </div>
                <button type="submit">Log In</button>
                <p className="auth-switch">
                    Don't have an account? <Link to="/register">Create one</Link>
                </p>
            </form>
        </div>
    );
};

export default Login;
