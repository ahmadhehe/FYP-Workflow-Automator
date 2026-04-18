import React, { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { Sidebar, Dashboard, FlowHistory, Settings, Costs, Onboarding, Login, FilesPage } from './components';
import { useWebSocket } from './hooks/useWebSocket';
import { useAuth } from './hooks/useAuth';
import api from './services/api';

function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const { session, loading: authLoading } = useAuth();
  const {
    isConnected,
    events,
    taskStatus,
    currentIteration,
    clearEvents,
  } = useWebSocket();

  const [browserRunning, setBrowserRunning] = useState(false);
  const [initialTask, setInitialTask] = useState(null);

  // Redirect to /login if not authenticated
  useEffect(() => {
    if (authLoading) return;
    if (!session && location.pathname !== '/login') {
      navigate('/login');
    }
  }, [session, authLoading, navigate, location.pathname]);

  // Once authenticated, check onboarding completion
  useEffect(() => {
    if (!session || location.pathname === '/login' || location.pathname === '/onboarding') return;
    const checkOnboarding = async () => {
      try {
        const { completed } = await api.getOnboardingStatus();
        if (!completed) navigate('/onboarding');
      } catch {
        // Supabase not configured — skip redirect
      }
    };
    checkOnboarding();
  }, [session, navigate, location.pathname]);

  // Check browser status on mount (only when logged in)
  useEffect(() => {
    if (!session) return;
    const checkStatus = async () => {
      try {
        const status = await api.getStatus();
        setBrowserRunning(status.browser_running);
      } catch (error) {
        console.error('Failed to check status:', error);
      }
    };
    checkStatus();
    const interval = setInterval(checkStatus, 10000);
    return () => clearInterval(interval);
  }, [session]);

  const handleRerunFlow = (task) => {
    setInitialTask(task);
    clearEvents();
    navigate('/');
    setTimeout(() => setInitialTask(null), 100);
  };

  // Show nothing while auth state is resolving
  if (authLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-400 text-sm">Loading…</div>
      </div>
    );
  }

  const isFullscreenRoute = ['/login', '/onboarding'].includes(location.pathname);

  return (
    <div className="min-h-screen bg-gray-50">
      {!isFullscreenRoute && (
        <Sidebar isConnected={isConnected} browserRunning={browserRunning} />
      )}

      <main className={isFullscreenRoute ? '' : 'pl-64'}>
        <div className={isFullscreenRoute ? '' : 'p-8'}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/onboarding" element={<Onboarding />} />
            <Route
              path="/"
              element={
                <Dashboard
                  events={events}
                  taskStatus={taskStatus}
                  currentIteration={currentIteration}
                  isConnected={isConnected}
                  clearEvents={clearEvents}
                  browserRunning={browserRunning}
                  initialTask={initialTask}
                />
              }
            />
            <Route path="/files" element={<FilesPage />} />
            <Route path="/history" element={<FlowHistory onRerun={handleRerunFlow} />} />
            <Route path="/costs" element={<Costs />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </div>
      </main>

      {/* Background gradient effects */}
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-maroon-500/5 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-gold-500/5 rounded-full blur-3xl" />
      </div>
    </div>
  );
}

export default App;
