/**
 * LoginPage - User authentication page
 *
 * Provides email/password login form with error handling and redirect support.
 */

import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { useAuth } from '../../context/AuthContext';
import './AuthPages.css';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isLoading } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Get the page user was trying to access before being redirected to login
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="auth-page">
        <div className="auth-loading">
          <Icon name="Loader2" size={32} className="spin" />
          <span>Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-logo">
            <Icon name="Shield" size={40} />
          </div>
          <h1>Sign In</h1>
          <p>Welcome back to SHATTERED</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && (
            <div className="auth-error">
              <Icon name="AlertCircle" size={16} />
              <span>{error}</span>
            </div>
          )}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoFocus
              autoComplete="email"
              disabled={isSubmitting}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <div className="password-input">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
                autoComplete="current-password"
                disabled={isSubmitting}
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
              >
                <Icon name={showPassword ? 'EyeOff' : 'Eye'} size={18} />
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="auth-submit"
            disabled={isSubmitting || !email || !password}
          >
            {isSubmitting ? (
              <>
                <Icon name="Loader2" size={18} className="spin" />
                Signing in...
              </>
            ) : (
              <>
                <Icon name="LogIn" size={18} />
                Sign In
              </>
            )}
          </button>
        </form>

        <div className="auth-footer">
          <p className="auth-help">
            Contact your administrator if you need access or forgot your password.
          </p>
        </div>
      </div>
    </div>
  );
}
