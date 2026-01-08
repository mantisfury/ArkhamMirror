/**
 * UserModal - Create/Edit user modal
 *
 * Modal dialog for creating new users or editing existing users within a tenant.
 */

import { useState } from 'react';
import { Icon } from '../common/Icon';
import './UserModal.css';

type UserRole = 'admin' | 'analyst' | 'viewer';

interface TenantUser {
  id: string;
  email: string;
  display_name: string | null;
  role: UserRole;
  tenant_id: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  last_login: string | null;
}

interface CreateUserData {
  email: string;
  password: string;
  display_name?: string;
  role: string;
}

interface UpdateUserData {
  display_name?: string;
  role?: string;
  is_active?: boolean;
}

interface UserModalProps {
  user?: TenantUser | null;
  onClose: () => void;
  onSave: (data: CreateUserData | UpdateUserData) => Promise<void> | void;
}

export function UserModal({ user, onClose, onSave }: UserModalProps) {
  const isEdit = !!user;

  const [email, setEmail] = useState(user?.email || '');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState(user?.display_name || '');
  const [role, setRole] = useState<UserRole>(user?.role || 'analyst');
  const [isActive, setIsActive] = useState(user?.is_active ?? true);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = () => {
    const newErrors: Record<string, string> = {};

    if (!isEdit) {
      if (!email) {
        newErrors.email = 'Email is required';
      } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        newErrors.email = 'Invalid email format';
      }

      if (!password) {
        newErrors.password = 'Password is required';
      } else if (password.length < 8) {
        newErrors.password = 'Password must be at least 8 characters';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) return;

    setSaving(true);
    try {
      if (isEdit) {
        await onSave({
          display_name: displayName || undefined,
          role,
          is_active: isActive,
        });
      } else {
        await onSave({
          email,
          password,
          display_name: displayName || undefined,
          role,
        });
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="user-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>
            <Icon name={isEdit ? 'UserCog' : 'UserPlus'} size={20} />
            {isEdit ? 'Edit User' : 'Add New User'}
          </h2>
          <button className="icon-btn" onClick={onClose} type="button">
            <Icon name="X" size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-content">
          {/* Email - only for create */}
          {!isEdit && (
            <div className="form-group">
              <label htmlFor="user-email">
                Email Address <span className="required">*</span>
              </label>
              <input
                id="user-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
                autoFocus
                className={errors.email ? 'error' : ''}
              />
              {errors.email && (
                <span className="error-message">{errors.email}</span>
              )}
            </div>
          )}

          {/* Email display for edit */}
          {isEdit && (
            <div className="form-group">
              <label>Email Address</label>
              <div className="readonly-field">
                <Icon name="Mail" size={16} />
                {user.email}
              </div>
            </div>
          )}

          {/* Password - only for create */}
          {!isEdit && (
            <div className="form-group">
              <label htmlFor="user-password">
                Password <span className="required">*</span>
              </label>
              <input
                id="user-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Minimum 8 characters"
                className={errors.password ? 'error' : ''}
              />
              {errors.password && (
                <span className="error-message">{errors.password}</span>
              )}
            </div>
          )}

          {/* Display Name */}
          <div className="form-group">
            <label htmlFor="user-display-name">Display Name</label>
            <input
              id="user-display-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="John Doe"
            />
            <span className="form-hint">
              Optional. If not set, email username will be used.
            </span>
          </div>

          {/* Role */}
          <div className="form-group">
            <label htmlFor="user-role">Role</label>
            <select
              id="user-role"
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
            >
              <option value="admin">Admin - Full access, can manage users</option>
              <option value="analyst">Analyst - Read and write access</option>
              <option value="viewer">Viewer - Read-only access</option>
            </select>
            <div className="role-descriptions">
              <div className={`role-desc ${role === 'admin' ? 'active' : ''}`}>
                <Icon name="Shield" size={14} />
                <span>Can manage users, settings, and all data</span>
              </div>
              <div className={`role-desc ${role === 'analyst' ? 'active' : ''}`}>
                <Icon name="FileEdit" size={14} />
                <span>Can create, edit, and analyze data</span>
              </div>
              <div className={`role-desc ${role === 'viewer' ? 'active' : ''}`}>
                <Icon name="Eye" size={14} />
                <span>Can view and export data, but not modify</span>
              </div>
            </div>
          </div>

          {/* Active Status - only for edit */}
          {isEdit && (
            <div className="form-group">
              <label className="toggle-label">
                <span className="toggle-text">
                  Account Status
                </span>
                <div className="toggle-switch">
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </div>
                <span className={`toggle-status ${isActive ? 'active' : 'inactive'}`}>
                  {isActive ? 'Active' : 'Inactive'}
                </span>
              </label>
              <span className="form-hint">
                Inactive users cannot log in but their data is preserved.
              </span>
            </div>
          )}

          <div className="modal-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={saving}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={saving}
            >
              {saving ? (
                <>
                  <Icon name="Loader2" size={16} className="spin" />
                  Saving...
                </>
              ) : isEdit ? (
                <>
                  <Icon name="Check" size={16} />
                  Save Changes
                </>
              ) : (
                <>
                  <Icon name="UserPlus" size={16} />
                  Create User
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
