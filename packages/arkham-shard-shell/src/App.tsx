/**
 * App - Main application component
 *
 * Provider nesting order (from UI_SHELL_IMPL_REF):
 * <BrowserRouter>
 *   <ShellProvider>
 *     <ToastProvider>
 *       <ConfirmProvider>
 *         <BadgeProvider>
 *           <Routes>
 *             <Shell>
 *               <Outlet />
 *             </Shell>
 *           </Routes>
 *         </BadgeProvider>
 *       </ConfirmProvider>
 *     </ToastProvider>
 *   </ShellProvider>
 * </BrowserRouter>
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ShellProvider } from './context/ShellContext';
import { ToastProvider } from './context/ToastContext';
import { ConfirmProvider } from './context/ConfirmContext';
import { BadgeProvider } from './context/BadgeContext';
import { Shell } from './components/layout/Shell';
import { ShardUnavailable } from './components/common/ShardUnavailable';

// Page imports
import { DashboardPage } from './pages/dashboard';
import { ACHPage, ACHListPage, ACHNewPage } from './pages/ach';

export function App() {
  return (
    <BrowserRouter>
      <ShellProvider>
        <ToastProvider>
          <ConfirmProvider>
            <BadgeProvider>
              <Routes>
                {/* Shell layout wrapper */}
                <Route element={<Shell />}>
                  {/* Default redirect */}
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />

                  {/* Dashboard shard */}
                  <Route path="/dashboard" element={<DashboardPage />} />

                  {/* ACH shard with sub-routes */}
                  <Route path="/ach" element={<ACHPage />} />
                  <Route path="/ach/matrices" element={<ACHListPage />} />
                  <Route path="/ach/new" element={<ACHNewPage />} />

                  {/* Catch-all for unknown shard routes */}
                  <Route path="*" element={<ShardUnavailable />} />
                </Route>
              </Routes>
            </BadgeProvider>
          </ConfirmProvider>
        </ToastProvider>
      </ShellProvider>
    </BrowserRouter>
  );
}
