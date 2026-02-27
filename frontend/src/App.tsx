import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import LandingPage from './pages/LandingPage';
import DashboardPage from './pages/DashboardPage';
import CompetitorsPage from './pages/CompetitorsPage';
import CompetitorDetailPage from './pages/CompetitorDetailPage';
import SourcesPage from './pages/SourcesPage';
import ChangesPage from './pages/ChangesPage';
import AnalysesPage from './pages/AnalysesPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Landing page — full width, no sidebar */}
        <Route path="/" element={<LandingPage />} />

        {/* Dashboard pages — with sidebar layout */}
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/competitors" element={<CompetitorsPage />} />
          <Route path="/competitors/:slug" element={<CompetitorDetailPage />} />
          <Route path="/sources" element={<SourcesPage />} />
          <Route path="/changes" element={<ChangesPage />} />
          <Route path="/analyses" element={<AnalysesPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
