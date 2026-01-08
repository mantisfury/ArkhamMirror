/**
 * SetupPage - Initial setup wizard
 *
 * First-time setup flow to create the initial tenant and admin user.
 * This page is shown when no tenants exist in the system.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import './AuthPages.css';

interface SetupData {
  tenant_name: string;
  tenant_slug: string;
  admin_email: string;
  admin_password: string;
  admin_password_confirm: string;
  admin_display_name: string;
}

export function SetupPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [setupComplete, setSetupComplete] = useState(false);

  const [data, setData] = useState<SetupData>({
    tenant_name: '',
    tenant_slug: '',
    admin_email: '',
    admin_password: '',
    admin_password_confirm: '',
    admin_display_name: '',
  });

  const updateData = (field: keyof SetupData, value: string) => {
    setData(prev => ({ ...prev, [field]: value }));
    setError('');

    // Auto-generate slug from organization name
    if (field === 'tenant_name') {
      const slug = value
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '');
      setData(prev => ({ ...prev, tenant_slug: slug }));
    }
  };

  const validateStep1 = (): boolean => {
    if (!data.tenant_name.trim()) {
      setError('Organization name is required');
      return false;
    }
    if (data.tenant_name.length > 255) {
      setError('Organization name is too long');
      return false;
    }
    if (!data.tenant_slug.match(/^[a-z0-9-]+$/)) {
      setError('Slug must contain only lowercase letters, numbers, and hyphens');
      return false;
    }
    if (data.tenant_slug.length > 100) {
      setError('Slug is too long');
      return false;
    }
    return true;
  };

  const validateStep2 = (): boolean => {
    if (!data.admin_email.includes('@')) {
      setError('Please enter a valid email address');
      return false;
    }
    if (data.admin_password.length < 8) {
      setError('Password must be at least 8 characters');
      return false;
    }
    if (data.admin_password !== data.admin_password_confirm) {
      setError('Passwords do not match');
      return false;
    }
    return true;
  };

  const handleNext = () => {
    setError('');
    if (step === 1 && validateStep1()) {
      setStep(2);
    } else if (step === 2 && validateStep2()) {
      setStep(3);
    }
  };

  const handleBack = () => {
    setError('');
    setStep(step - 1);
  };

  const handleSubmit = async () => {
    setError('');
    setIsSubmitting(true);

    try {
      const res = await fetch('/api/auth/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tenant_name: data.tenant_name,
          tenant_slug: data.tenant_slug,
          admin_email: data.admin_email,
          admin_password: data.admin_password,
          admin_display_name: data.admin_display_name || 'Admin',
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Setup failed' }));
        throw new Error(err.detail || 'Setup failed');
      }

      setSetupComplete(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Setup failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const goToLogin = () => {
    navigate('/login');
    window.location.reload(); // Refresh to clear setupRequired state
  };

  // Setup complete screen
  if (setupComplete) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <div className="auth-header">
            <div className="auth-logo success">
              <Icon name="CheckCircle" size={48} />
            </div>
            <h1>Setup Complete!</h1>
            <p>Your organization is ready to use.</p>
          </div>

          <div className="setup-summary">
            <div className="summary-item">
              <Icon name="Building2" size={20} />
              <div>
                <span className="label">Organization</span>
                <span className="value">{data.tenant_name}</span>
              </div>
            </div>
            <div className="summary-item">
              <Icon name="User" size={20} />
              <div>
                <span className="label">Admin Email</span>
                <span className="value">{data.admin_email}</span>
              </div>
            </div>
          </div>

          <button className="auth-submit" onClick={goToLogin}>
            <Icon name="LogIn" size={18} />
            Sign In
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card setup-card">
        <div className="auth-header">
          <div className="auth-logo">
            <Icon name="Settings" size={40} />
          </div>
          <h1>Initial Setup</h1>
          <p>Configure your SHATTERED instance</p>
        </div>

        {/* Progress indicator */}
        <div className="setup-progress">
          <div className={`progress-step ${step >= 1 ? 'active' : ''}`}>
            <div className="step-icon">
              <Icon name="Building2" size={16} />
            </div>
            <span>Organization</span>
          </div>
          <div className="progress-line" />
          <div className={`progress-step ${step >= 2 ? 'active' : ''}`}>
            <div className="step-icon">
              <Icon name="User" size={16} />
            </div>
            <span>Admin User</span>
          </div>
          <div className="progress-line" />
          <div className={`progress-step ${step >= 3 ? 'active' : ''}`}>
            <div className="step-icon">
              <Icon name="Check" size={16} />
            </div>
            <span>Confirm</span>
          </div>
        </div>

        {error && (
          <div className="auth-error">
            <Icon name="AlertCircle" size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Step 1: Organization */}
        {step === 1 && (
          <div className="setup-step">
            <h2>
              <Icon name="Building2" size={24} />
              Organization Details
            </h2>
            <p>Enter the name of your organization or team.</p>

            <div className="form-group">
              <label htmlFor="tenant_name">Organization Name</label>
              <input
                id="tenant_name"
                type="text"
                value={data.tenant_name}
                onChange={(e) => updateData('tenant_name', e.target.value)}
                placeholder="e.g., Acme Research Group"
                required
                autoFocus
              />
            </div>

            <div className="form-group">
              <label htmlFor="tenant_slug">URL Slug</label>
              <input
                id="tenant_slug"
                type="text"
                value={data.tenant_slug}
                onChange={(e) => updateData('tenant_slug', e.target.value.toLowerCase())}
                placeholder="e.g., acme-research"
                pattern="[a-z0-9-]+"
                required
              />
              <span className="form-hint">
                Used in URLs. Lowercase letters, numbers, and hyphens only.
              </span>
            </div>

            <div className="setup-actions">
              <button
                type="button"
                className="auth-submit"
                onClick={handleNext}
                disabled={!data.tenant_name || !data.tenant_slug}
              >
                Next
                <Icon name="ArrowRight" size={18} />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Admin User */}
        {step === 2 && (
          <div className="setup-step">
            <h2>
              <Icon name="User" size={24} />
              Administrator Account
            </h2>
            <p>Create the first admin user for your organization.</p>

            <div className="form-group">
              <label htmlFor="admin_display_name">Display Name</label>
              <input
                id="admin_display_name"
                type="text"
                value={data.admin_display_name}
                onChange={(e) => updateData('admin_display_name', e.target.value)}
                placeholder="e.g., John Smith"
                autoFocus
              />
            </div>

            <div className="form-group">
              <label htmlFor="admin_email">Email Address</label>
              <input
                id="admin_email"
                type="email"
                value={data.admin_email}
                onChange={(e) => updateData('admin_email', e.target.value)}
                placeholder="admin@example.com"
                required
                autoComplete="email"
              />
            </div>

            <div className="form-group">
              <label htmlFor="admin_password">Password</label>
              <input
                id="admin_password"
                type="password"
                value={data.admin_password}
                onChange={(e) => updateData('admin_password', e.target.value)}
                placeholder="At least 8 characters"
                required
                minLength={8}
                autoComplete="new-password"
              />
            </div>

            <div className="form-group">
              <label htmlFor="admin_password_confirm">Confirm Password</label>
              <input
                id="admin_password_confirm"
                type="password"
                value={data.admin_password_confirm}
                onChange={(e) => updateData('admin_password_confirm', e.target.value)}
                placeholder="Confirm your password"
                required
                autoComplete="new-password"
              />
            </div>

            <div className="setup-actions">
              <button
                type="button"
                className="auth-secondary"
                onClick={handleBack}
              >
                <Icon name="ArrowLeft" size={18} />
                Back
              </button>
              <button
                type="button"
                className="auth-submit"
                onClick={handleNext}
                disabled={!data.admin_email || !data.admin_password}
              >
                Next
                <Icon name="ArrowRight" size={18} />
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Confirm */}
        {step === 3 && (
          <div className="setup-step">
            <h2>
              <Icon name="Check" size={24} />
              Confirm Setup
            </h2>
            <p>Review your settings before completing setup.</p>

            <div className="setup-summary">
              <div className="summary-item">
                <Icon name="Building2" size={20} />
                <div>
                  <span className="label">Organization</span>
                  <span className="value">{data.tenant_name}</span>
                  <span className="hint">/{data.tenant_slug}</span>
                </div>
              </div>
              <div className="summary-item">
                <Icon name="User" size={20} />
                <div>
                  <span className="label">Admin User</span>
                  <span className="value">{data.admin_display_name || 'Admin'}</span>
                  <span className="hint">{data.admin_email}</span>
                </div>
              </div>
            </div>

            <div className="setup-actions">
              <button
                type="button"
                className="auth-secondary"
                onClick={handleBack}
                disabled={isSubmitting}
              >
                <Icon name="ArrowLeft" size={18} />
                Back
              </button>
              <button
                type="button"
                className="auth-submit"
                onClick={handleSubmit}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <Icon name="Loader2" size={18} className="spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Icon name="Check" size={18} />
                    Complete Setup
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
