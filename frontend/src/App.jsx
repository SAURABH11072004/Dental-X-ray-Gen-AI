import React, { Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import LoadingState from "./components/LoadingState";
import Overview from "./pages/Overview";
import Analysis from "./pages/Analysis";
import Segmentation from "./pages/Segmentation";
import Uncertainty from "./pages/Uncertainty";
import ActiveLearning from "./pages/ActiveLearning";
import Annotations from "./pages/Annotations";
import Reports from "./pages/Reports";
import Training from "./pages/Training";
import Experiments from "./pages/Experiments";
import Models from "./pages/Models";
import SettingsPage from "./pages/Settings";
import About from "./pages/About";
import ReviewFindings from "./pages/ReviewFindings";
import ResearchBanner from "./components/ResearchBanner";

export default function App() {
  return (
    <div className="flex h-full">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-white focus:p-2">Skip to content</a>
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main id="main" className="flex-1 overflow-y-auto px-3 py-4 sm:px-6 sm:py-6 xl:px-8">
          <div className="page">
          <ResearchBanner />
          <Suspense fallback={<LoadingState />}>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/analysis" element={<Analysis />} />
              <Route path="/segmentation" element={<Segmentation />} />
              <Route path="/uncertainty" element={<Uncertainty />} />
              <Route path="/active-learning" element={<ActiveLearning />} />
              <Route path="/annotations" element={<Annotations />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/review" element={<ReviewFindings />} />
              <Route path="/training" element={<Training />} />
              <Route path="/experiments" element={<Experiments />} />
              <Route path="/models" element={<Models />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/about" element={<About />} />
              <Route path="*" element={<div className="card card-pad">Page not found.</div>} />
            </Routes>
          </Suspense>
          </div>
        </main>
      </div>
    </div>
  );
}
