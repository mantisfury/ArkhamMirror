/**
 * UsersPage - User management for tenant admins
 *
 * Allows admins to list, create, edit, and deactivate users within their tenant.
 * Part of Phase 5: Multi-tenancy Frontend Implementation.
 */

import { useState, useCallback, useEffect } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';
import { useConfirm } from '../../context/ConfirmContext';
import { apiGet, apiPost, apiPatch, apiDelete } from '../../utils/api';
import { UserModal } from '../../components/users/UserModal';
import './UsersPage.css';

// Types
interface TenantUser {
  id: string;
  email: string;
  display_name: string | null;
  role: 'admin' | 'analyst' | 'viewer';
  tenant_id: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  last_login: string | null;
}

const ROLE_LABELS: Record<string, string> = {
  admin: 'Admin',
  analyst: 'Analyst',
  viewer: 'Viewer',
};

export function UsersPage() {
  const { toast } = useToast();
  const { user: currentUser, tenant } = useAuth();
  const confirm = useConfirm();

  const [users, setUsers] = useState<TenantUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState<TenantUser | null>(null);

  // Fetch users
  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGet<TenantUser[]>('/api/auth/tenant/users');
      setUsers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // Filter users
  const filteredUsers = users.filter(user => {
    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      const matchesEmail = user.email.toLowerCase().includes(query);
      const matchesName = user.display_name?.toLowerCase().includes(query);
      if (!matchesEmail && !matchesName) return false;
    }
    // Role filter
    if (roleFilter && user.role !== roleFilter) return false;
    // Status filter
    if (statusFilter === 'active' && !user.is_active) return false;
    if (statusFilter === 'inactive' && user.is_active) return false;
    return true;
  });

  // User data types for modal
  type CreateUserData = {
    email: string;
    password: string;
    display_name?: string;
    role: string;
  };

  type UpdateUserData = {
    display_name?: string;
    role?: string;
    is_active?: boolean;
  };

  // Handlers
  const handleCreateUser = useCallback(async (data: CreateUserData | UpdateUserData) => {
    try {
      await apiPost('/api/auth/tenant/users', data);
      toast.success('User created successfully');
      setShowModal(false);
      fetchUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create user');
    }
  }, [toast, fetchUsers]);

  const handleUpdateUser = useCallback(async (
    userId: string,
    data: CreateUserData | UpdateUserData
  ) => {
    try {
      await apiPatch(`/api/auth/tenant/users/${userId}`, data);
      toast.success('User updated successfully');
      setShowModal(false);
      setEditingUser(null);
      fetchUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update user');
    }
  }, [toast, fetchUsers]);

  const handleToggleActive = useCallback(async (user: TenantUser) => {
    const action = user.is_active ? 'deactivate' : 'reactivate';
    const confirmed = await confirm({
      title: `${user.is_active ? 'Deactivate' : 'Reactivate'} User`,
      message: `Are you sure you want to ${action} ${user.email}?`,
      confirmLabel: user.is_active ? 'Deactivate' : 'Reactivate',
      variant: user.is_active ? 'danger' : 'default',
    });

    if (!confirmed) return;

    try {
      await apiPatch(`/api/auth/tenant/users/${user.id}`, {
        is_active: !user.is_active,
      });
      toast.success(`User ${action}d successfully`);
      fetchUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `Failed to ${action} user`);
    }
  }, [confirm, toast, fetchUsers]);

  const handleDeleteUser = useCallback(async (user: TenantUser) => {
    const confirmed = await confirm({
      title: 'Delete User',
      message: `Are you sure you want to permanently delete ${user.email}? This action cannot be undone.`,
      confirmLabel: 'Delete',
      variant: 'danger',
    });

    if (!confirmed) return;

    try {
      await apiDelete(`/api/auth/tenant/users/${user.id}`);
      toast.success('User deleted successfully');
      fetchUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete user');
    }
  }, [confirm, toast, fetchUsers]);

  const openEditModal = (user: TenantUser) => {
    setEditingUser(user);
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditingUser(null);
  };

  // Helper to get user initials
  const getInitials = (user: TenantUser) => {
    const name = user.display_name || user.email.split('@')[0];
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  // Helper to format date
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="users-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Users" size={28} />
          <div>
            <h1>User Management</h1>
            <p className="page-description">
              Manage users in {tenant?.name || 'your organization'}
            </p>
          </div>
        </div>

        <button
          className="btn btn-primary"
          onClick={() => setShowModal(true)}
        >
          <Icon name="UserPlus" size={16} />
          Add User
        </button>
      </header>

      {/* Filters */}
      <div className="users-filters">
        <div className="search-box">
          <Icon name="Search" size={16} />
          <input
            type="text"
            placeholder="Search by name or email..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <select
          className="filter-select"
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
        >
          <option value="">All Roles</option>
          <option value="admin">Admin</option>
          <option value="analyst">Analyst</option>
          <option value="viewer">Viewer</option>
        </select>

        <select
          className="filter-select"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      {/* User limit warning */}
      {tenant && users.length >= tenant.max_users * 0.8 && (
        <div className="user-limit-warning">
          <Icon name="AlertTriangle" size={16} />
          <span>
            {users.length} of {tenant.max_users} users ({Math.round(users.length / tenant.max_users * 100)}% of limit)
          </span>
        </div>
      )}

      {/* Users List */}
      <main className="users-content">
        {loading ? (
          <div className="users-loading">
            <Icon name="Loader2" size={32} className="spin" />
            <span>Loading users...</span>
          </div>
        ) : error ? (
          <div className="users-error">
            <Icon name="AlertCircle" size={32} />
            <span>{error}</span>
            <button className="btn btn-secondary" onClick={fetchUsers}>
              Retry
            </button>
          </div>
        ) : filteredUsers.length > 0 ? (
          <div className="users-list">
            {filteredUsers.map((user) => (
              <div
                key={user.id}
                className={`user-card ${!user.is_active ? 'inactive' : ''}`}
              >
                <div className="user-avatar">
                  {getInitials(user)}
                </div>

                <div className="user-info">
                  <div className="user-name-row">
                    <span className="user-name">
                      {user.display_name || user.email.split('@')[0]}
                    </span>
                    <span className={`role-badge role-${user.role}`}>
                      {ROLE_LABELS[user.role]}
                    </span>
                    {!user.is_active && (
                      <span className="status-badge inactive">Inactive</span>
                    )}
                    {user.id === currentUser?.id && (
                      <span className="you-badge">You</span>
                    )}
                  </div>
                  <span className="user-email">{user.email}</span>
                  <div className="user-meta">
                    <span>
                      <Icon name="Calendar" size={12} />
                      Joined {formatDate(user.created_at)}
                    </span>
                    <span>
                      <Icon name="Clock" size={12} />
                      Last login {formatDate(user.last_login)}
                    </span>
                  </div>
                </div>

                <div className="user-actions">
                  <button
                    className="icon-btn"
                    onClick={() => openEditModal(user)}
                    title="Edit user"
                  >
                    <Icon name="Edit2" size={16} />
                  </button>

                  {user.id !== currentUser?.id && (
                    <>
                      <button
                        className="icon-btn"
                        onClick={() => handleToggleActive(user)}
                        title={user.is_active ? 'Deactivate user' : 'Reactivate user'}
                      >
                        <Icon name={user.is_active ? 'UserX' : 'UserCheck'} size={16} />
                      </button>

                      <button
                        className="icon-btn danger"
                        onClick={() => handleDeleteUser(user)}
                        title="Delete user"
                      >
                        <Icon name="Trash2" size={16} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="users-empty">
            <Icon name="Users" size={48} />
            <h3>No users found</h3>
            <p>
              {searchQuery || roleFilter || statusFilter
                ? 'Try adjusting your filters'
                : 'Add your first team member to get started'}
            </p>
            {!searchQuery && !roleFilter && !statusFilter && (
              <button
                className="btn btn-primary"
                onClick={() => setShowModal(true)}
              >
                <Icon name="UserPlus" size={16} />
                Add User
              </button>
            )}
          </div>
        )}

        {filteredUsers.length > 0 && (
          <div className="users-stats">
            <span>
              Showing {filteredUsers.length} of {users.length} users
            </span>
          </div>
        )}
      </main>

      {/* User Modal */}
      {showModal && (
        <UserModal
          user={editingUser}
          onClose={closeModal}
          onSave={editingUser
            ? (data) => handleUpdateUser(editingUser.id, data)
            : handleCreateUser
          }
        />
      )}
    </div>
  );
}
