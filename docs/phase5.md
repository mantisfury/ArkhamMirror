# Phase 5: Multi-tenancy Frontend Implementation Plan

**Status: COMPLETE**

## Overview

Implement the frontend UI for multi-tenant user management, allowing tenant admins to manage users within their organization.

## Scope

Based on the security plan, Phase 5 includes:
1. **User Management Page** (`/settings/users`) - List, create, edit, deactivate users
2. **Role Assignment UI** - Admin, analyst, viewer role selection
3. **User Deactivation** - Disable user accounts (soft delete)
4. **(Deferred) Tenant Selector** - For superusers with multi-tenant access
5. **(Deferred) Invite User Flow** - Email invitation system

## Backend API Available

All required endpoints exist in `arkham_frame/auth/router.py`:

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/api/auth/tenant/users` | GET | List users in tenant | Admin |
| `/api/auth/tenant/users` | POST | Create user | Admin |
| `/api/auth/tenant/users/{id}` | PATCH | Update user | Admin |
| `/api/auth/tenant/users/{id}` | DELETE | Delete user | Admin |
| `/api/auth/me/tenant` | GET | Get tenant info | Any |

## Implementation Plan

### File Structure

```
packages/arkham-shard-shell/src/
├── pages/settings/
│   ├── UsersPage.tsx          # NEW - User management page
│   └── UsersPage.css          # NEW - Styles
├── components/users/
│   ├── UserModal.tsx          # NEW - Create/Edit user modal
│   ├── UserModal.css          # NEW - Modal styles
│   └── UserCard.tsx           # NEW - User list item
```

### Step 1: Add Route to App.tsx

Add protected route for user management:

```tsx
// In App.tsx routes
<Route
  path="/settings/users"
  element={
    <AdminRoute>
      <UsersPage />
    </AdminRoute>
  }
/>
```

**File:** `src/App.tsx`

### Step 2: Create UsersPage Component

Main page with:
- Header with title + "Add User" button
- Search/filter bar (by name, email, role, status)
- User list with cards showing:
  - Avatar (initials)
  - Display name + email
  - Role badge (admin/analyst/viewer)
  - Status indicator (active/inactive)
  - Last login date
  - Action buttons (Edit, Deactivate/Activate, Delete)
- Empty state when no users

**File:** `src/pages/settings/UsersPage.tsx`

### Step 3: Create UserModal Component

Modal for create/edit with:
- Email input (required, validated)
- Display name input (optional)
- Password input (required for create, optional for edit)
- Role dropdown (admin/analyst/viewer)
- Active toggle (edit mode only)
- Cancel/Save buttons

**File:** `src/components/users/UserModal.tsx`

### Step 4: Create UserCard Component

Reusable card component:
- Avatar with initials (same pattern as UserMenu)
- User info (name, email)
- Role badge with color coding
- Status badge (active/inactive)
- Metadata (created, last login)
- Action buttons

**File:** `src/components/users/UserCard.tsx`

### Step 5: Add CSS Styles

Follow existing patterns from:
- `AuthPages.css` - Form groups, buttons
- `UserMenu.css` - Role badges, avatars
- `SettingsPage.css` - Layout, cards

**Files:** `UsersPage.css`, `UserModal.css`

### Step 6: Update Navigation

UserMenu already has "Manage Users" link for admins pointing to `/settings/users`.
No changes needed.

## UI Patterns to Follow

### From AuthContext
```typescript
interface User {
  id: string;
  email: string;
  display_name: string | null;
  role: 'admin' | 'analyst' | 'viewer';
  tenant_id: string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}
```

### Role Badge Colors (from UserMenu.css)
```css
.role-admin { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
.role-analyst { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }
.role-viewer { background: rgba(107, 114, 128, 0.15); color: #6b7280; }
```

### Modal Pattern (from ProjectsPage)
```tsx
<div className="modal-overlay" onClick={onClose}>
  <div className="modal" onClick={e => e.stopPropagation()}>
    <div className="modal-header">...</div>
    <form className="modal-content">...</form>
    <div className="modal-actions">...</div>
  </div>
</div>
```

### API Calls (from api.ts)
```typescript
import { apiGet, apiPost, apiPatch, apiDelete } from '../../utils/api';

// List users
const users = await apiGet<User[]>('/api/auth/tenant/users');

// Create user
await apiPost('/api/auth/tenant/users', { email, password, display_name, role });

// Update user
await apiPatch(`/api/auth/tenant/users/${id}`, { display_name, role, is_active });

// Delete user
await apiDelete(`/api/auth/tenant/users/${id}`);
```

## Business Rules

1. **Admin Only** - Page requires admin role (use `<AdminRoute>`)
2. **Cannot Delete Self** - Backend prevents, frontend should hide delete button for current user
3. **User Limits** - Show warning when approaching `tenant.max_users`
4. **Role Hierarchy** - Admins can assign any role
5. **Deactivation** - Preferred over deletion, sets `is_active: false`

## Implementation Order

1. Create `UsersPage.tsx` with basic structure and API fetch
2. Create `UserCard.tsx` for list display
3. Add route to `App.tsx`
4. Create `UserModal.tsx` for create functionality
5. Add edit functionality to modal
6. Add delete/deactivate with confirmation
7. Add search and filters
8. Add CSS styling
9. Test all flows

## Testing Checklist

- [x] Admin can view user list
- [x] Admin can create new user
- [x] Admin can edit user (name, role)
- [x] Admin can deactivate user
- [x] Admin can reactivate user
- [x] Admin can delete user
- [x] Admin cannot delete themselves
- [x] Non-admin cannot access page (AdminRoute protection)
- [x] Search filters work
- [x] Role badges display correctly
- [x] Form validation works
- [x] Error messages display properly
- [x] Loading states work

## Deferred Items

These will be implemented in a future iteration:

1. **Tenant Selector** - For superusers to switch between tenants
2. **Email Invitations** - Send invite emails to new users
3. **Password Reset** - Admin-triggered password reset
4. **Bulk Operations** - Select multiple users for actions
