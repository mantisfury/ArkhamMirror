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
import { IngestPage, IngestQueuePage } from './pages/ingest';
import { OCRPage } from './pages/ocr';
import { SearchPage } from './pages/search';
import { ParsePage } from './pages/parse';
import { EmbedPage } from './pages/embed';
import { ContradictionsPage } from './pages/contradictions';
import { AnomaliesPage } from './pages/anomalies';

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

                  {/* Ingest shard */}
                  <Route path="/ingest" element={<IngestPage />} />
                  <Route path="/ingest/queue" element={<IngestQueuePage />} />

                  {/* OCR shard */}
                  <Route path="/ocr" element={<OCRPage />} />

                  {/* Search shard */}
                  <Route path="/search" element={<SearchPage />} />

                  {/* Parse shard */}
                  <Route path="/parse" element={<ParsePage />} />

                  {/* Embed shard */}
                  <Route path="/embed" element={<EmbedPage />} />

                  {/* Contradictions shard */}
                  <Route path="/contradictions" element={<ContradictionsPage />} />

                  {/* Anomalies shard */}
                  <Route path="/anomalies" element={<AnomaliesPage />} />

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
