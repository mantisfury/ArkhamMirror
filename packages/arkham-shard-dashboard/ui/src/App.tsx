import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import LLMConfig from './pages/LLMConfig'
import DatabaseControls from './pages/DatabaseControls'
import WorkerManager from './pages/WorkerManager'
import EventLog from './pages/EventLog'

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <aside className="sidebar">
          <div className="sidebar-header">
            <h1>ArkhamFrame</h1>
            <p>Dashboard Shard</p>
          </div>
          <nav>
            <NavLink to="/" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`} end>
              Overview
            </NavLink>
            <NavLink to="/llm" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
              LLM Config
            </NavLink>
            <NavLink to="/database" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
              Database
            </NavLink>
            <NavLink to="/workers" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
              Workers
            </NavLink>
            <NavLink to="/events" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
              Events
            </NavLink>
          </nav>
        </aside>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/llm" element={<LLMConfig />} />
            <Route path="/database" element={<DatabaseControls />} />
            <Route path="/workers" element={<WorkerManager />} />
            <Route path="/events" element={<EventLog />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
