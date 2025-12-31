/**
 * App - Main application component
 *
 * Provider nesting order (from UI_SHELL_IMPL_REF):
 * <BrowserRouter>
 *   <ThemeProvider>
 *     <ShellProvider>
 *       <ToastProvider>
 *         <ConfirmProvider>
 *           <BadgeProvider>
 *             <Routes>
 *               <Shell>
 *                 <Outlet />
 *               </Shell>
 *             </Routes>
 *           </BadgeProvider>
 *         </ConfirmProvider>
 *       </ToastProvider>
 *     </ShellProvider>
 *   </ThemeProvider>
 * </BrowserRouter>
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { ShellProvider } from './context/ShellContext';
import { ToastProvider } from './context/ToastContext';
import { ConfirmProvider } from './context/ConfirmContext';
import { BadgeProvider } from './context/BadgeContext';
import { Shell } from './components/layout/Shell';
import { GenericShardPage } from './pages/generic';
import { useStartPage } from './hooks';

/**
 * StartPageRedirect - Redirects to the user's configured start page.
 * Must be used inside providers so settings can be loaded.
 */
function StartPageRedirect() {
  const startPage = useStartPage();
  return <Navigate to={startPage} replace />;
}

// Page imports
import { DashboardPage } from './pages/dashboard';
import { ACHPage, ACHListPage, ACHNewPage } from './pages/ach';
import { IngestPage, IngestQueuePage } from './pages/ingest';
import { OCRPage } from './pages/ocr';
import { SearchPage } from './pages/search';
import { ParsePage, ChunksPage } from './pages/parse';
import { EmbedPage } from './pages/embed';
import { ContradictionsPage } from './pages/contradictions';
import { AnomaliesPage } from './pages/anomalies';
import { SettingsPage } from './pages/settings';

// Wave 1 shard imports
import { GraphPage } from './pages/graph';
import { TimelinePage } from './pages/timeline';
import { DocumentsPage } from './pages/documents';

// Wave 2 shard imports
import { EntitiesPage } from './pages/entities';
import { ProjectsPage } from './pages/projects';
import { ClaimsPage } from './pages/claims';

// Wave 3 shard imports
import { CredibilityPage } from './pages/credibility';
import { PatternsPage } from './pages/patterns';
import { ProvenancePage } from './pages/provenance';

// Wave 4 shard imports
import { ExportPage } from './pages/export';
import { ReportsPage } from './pages/reports';
import { LettersPage } from './pages/letters';

// Wave 5 shard imports
import { PacketsPage } from './pages/packets';
import { TemplatesPage } from './pages/templates';
import { SummaryPage } from './pages/summary';

export function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <ShellProvider>
          <ToastProvider>
            <ConfirmProvider>
              <BadgeProvider>
                <Routes>
                {/* Shell layout wrapper */}
                <Route element={<Shell />}>
                  {/* Default redirect to user's configured start page */}
                  <Route path="/" element={<StartPageRedirect />} />

                  {/* Dashboard shard with sub-routes */}
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/dashboard/llm" element={<DashboardPage />} />
                  <Route path="/dashboard/database" element={<DashboardPage />} />
                  <Route path="/dashboard/workers" element={<DashboardPage />} />
                  <Route path="/dashboard/events" element={<DashboardPage />} />

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
                  <Route path="/parse/chunks" element={<ChunksPage />} />

                  {/* Embed shard */}
                  <Route path="/embed" element={<EmbedPage />} />

                  {/* Contradictions shard */}
                  <Route path="/contradictions" element={<ContradictionsPage />} />

                  {/* Anomalies shard */}
                  <Route path="/anomalies" element={<AnomaliesPage />} />

                  {/* Settings shard with sub-routes */}
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="/settings/appearance" element={<SettingsPage />} />
                  <Route path="/settings/notifications" element={<SettingsPage />} />
                  <Route path="/settings/performance" element={<SettingsPage />} />
                  <Route path="/settings/data" element={<SettingsPage />} />
                  <Route path="/settings/advanced" element={<SettingsPage />} />
                  <Route path="/settings/shards" element={<SettingsPage />} />

                  {/* Wave 1 shards */}
                  {/* Graph shard */}
                  <Route path="/graph" element={<GraphPage />} />

                  {/* Timeline shard */}
                  <Route path="/timeline" element={<TimelinePage />} />

                  {/* Documents shard */}
                  <Route path="/documents" element={<DocumentsPage />} />

                  {/* Wave 2 shards */}
                  {/* Entities shard with sub-routes */}
                  <Route path="/entities" element={<EntitiesPage />} />
                  <Route path="/entities/merge" element={<EntitiesPage />} />
                  <Route path="/entities/relationships" element={<EntitiesPage />} />

                  {/* Projects shard */}
                  <Route path="/projects" element={<ProjectsPage />} />

                  {/* Claims shard */}
                  <Route path="/claims" element={<ClaimsPage />} />

                  {/* Wave 3 shards */}
                  {/* Credibility shard */}
                  <Route path="/credibility" element={<CredibilityPage />} />

                  {/* Patterns shard */}
                  <Route path="/patterns" element={<PatternsPage />} />

                  {/* Provenance shard */}
                  <Route path="/provenance" element={<ProvenancePage />} />

                  {/* Wave 4 shards */}
                  {/* Export shard */}
                  <Route path="/export" element={<ExportPage />} />

                  {/* Reports shard */}
                  <Route path="/reports" element={<ReportsPage />} />

                  {/* Letters shard */}
                  <Route path="/letters" element={<LettersPage />} />

                  {/* Wave 5 shards */}
                  {/* Packets shard */}
                  <Route path="/packets" element={<PacketsPage />} />

                  {/* Templates shard */}
                  <Route path="/templates" element={<TemplatesPage />} />

                  {/* Summary shard */}
                  <Route path="/summary" element={<SummaryPage />} />

                  {/* Catch-all: try to render shard with generic UI */}
                  <Route path="*" element={<GenericShardPage />} />
                </Route>
                </Routes>
              </BadgeProvider>
            </ConfirmProvider>
          </ToastProvider>
        </ShellProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
