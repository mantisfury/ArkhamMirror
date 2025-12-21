import { useACHStore } from './store/useACHStore';
import { AnalysisList } from './components/AnalysisList';
import { AnalysisView } from './components/AnalysisView';

function App() {
  const currentAnalysisId = useACHStore((state) => state.currentAnalysisId);

  return (
    <div className="min-h-screen bg-gray-900">
      {currentAnalysisId ? <AnalysisView /> : <AnalysisList />}
    </div>
  );
}

export default App;
