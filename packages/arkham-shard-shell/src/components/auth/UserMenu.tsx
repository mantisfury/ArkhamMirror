/**
 * UserMenu - User profile dropdown in the top bar
 *
 * Displays current user info, role badge, and logout option.
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Icon } from '../common/Icon';
import './UserMenu.css';

export function UserMenu() {
  const { user, tenant, logout, hasRole } = useAuth();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Close menu on escape key
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  if (!user) {
    return null;
  }

  const displayName = user.display_name || user.email.split('@')[0];
  const initials = displayName
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  const getRoleBadgeClass = () => {
    switch (user.role) {
      case 'admin':
        return 'role-admin';
      case 'analyst':
        return 'role-analyst';
      case 'viewer':
        return 'role-viewer';
      default:
        return '';
    }
  };

  return (
    <div className="user-menu" ref={menuRef}>
      <button
        className="user-menu-trigger"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        <div className="user-avatar">
          {initials}
        </div>
        <div className="user-info">
          <span className="user-name">{displayName}</span>
          <span className={`user-role ${getRoleBadgeClass()}`}>
            {user.role}
          </span>
        </div>
        <Icon name={isOpen ? 'ChevronUp' : 'ChevronDown'} size={16} />
      </button>

      {isOpen && (
        <div className="user-menu-dropdown">
          <div className="user-menu-header">
            <div className="user-avatar large">
              {initials}
            </div>
            <div className="user-details">
              <span className="user-name">{displayName}</span>
              <span className="user-email">{user.email}</span>
              {tenant && (
                <span className="user-tenant">
                  <Icon name="Building2" size={12} />
                  {tenant.name}
                </span>
              )}
            </div>
          </div>

          <div className="user-menu-divider" />

          <div className="user-menu-items">
            {hasRole('admin') && (
              <button
                className="user-menu-item"
                onClick={() => {
                  setIsOpen(false);
                  navigate('/settings/users');
                }}
              >
                <Icon name="Users" size={16} />
                Manage Users
              </button>
            )}

            <button
              className="user-menu-item"
              onClick={() => {
                setIsOpen(false);
                navigate('/settings');
              }}
            >
              <Icon name="Settings" size={16} />
              Settings
            </button>
          </div>

          <div className="user-menu-divider" />

          <button
            className="user-menu-item logout"
            onClick={handleLogout}
          >
            <Icon name="LogOut" size={16} />
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
}
