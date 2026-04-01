import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import Dashboard from './pages/Dashboard';
import Trends from './pages/Trends';
import TrendDetails from './pages/TrendDetails';
import Recommendations from './pages/Recommendations';
import Alerts from './pages/Alerts';
import Sources from './pages/Sources';
import Digests from './pages/Digests';
import Demo from './pages/Demo';
import AdaptationOverview from './pages/adaptation/AdaptationOverview';
import QualityPage from './pages/adaptation/QualityPage';
import ProposalsPage from './pages/adaptation/ProposalsPage';
import GoalsPage from './pages/adaptation/GoalsPage';
import ExperimentsPage from './pages/adaptation/ExperimentsPage';
import SourceTrustPage from './pages/adaptation/SourceTrustPage';

export default function App() {
  return (
    <ErrorBoundary>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/trends" element={<Trends />} />
          <Route path="/trends/:id" element={<TrendDetails />} />
          <Route path="/recommendations" element={<Recommendations />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="/digests" element={<Digests />} />
          <Route path="/demo" element={<Demo />} />
          <Route path="/adaptation" element={<AdaptationOverview />} />
          <Route path="/adaptation/quality" element={<QualityPage />} />
          <Route path="/adaptation/proposals" element={<ProposalsPage />} />
          <Route path="/adaptation/goals" element={<GoalsPage />} />
          <Route path="/adaptation/experiments" element={<ExperimentsPage />} />
          <Route path="/adaptation/sources" element={<SourceTrustPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </ErrorBoundary>
  );
}
