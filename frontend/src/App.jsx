import React, { useState, useEffect } from 'react';
import { Routes, Route, useNavigate } from 'react-router-dom';
import { Sidebar, Dashboard, FlowHistory, Settings } from './components';
import { useWebSocket } from './hooks/useWebSocket';
import api from './services/api';

function App() {
  const navigate = useNavigate();
  const { 
    isConnected, 
    events, 
    taskStatus, 
    currentIteration, 
    clearEvents 
  } = useWebSocket();
  
  const [browserRunning, setBrowserRunning] = useState(false);
  const [initialTask, setInitialTask] = useState(null);

  // Check browser status on mount
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const status = await api.getStatus();
        setBrowserRunning(status.browser_running);
      } catch (error) {
        console.error('Failed to check status:', error);
      }
    };

    checkStatus();
    
    // Poll status periodically
    const interval = setInterval(checkStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  // Handle re-running flows from history
  const handleRerunFlow = (task) => {
    setInitialTask(task);
    clearEvents();
    navigate('/');
    
    // Clear the initial task after a short delay
    setTimeout(() => setInitialTask(null), 100);
  };

  return (
    <div className="min-h-screen bg-dark-950">
      {/* Sidebar */}
      <Sidebar 
        isConnected={isConnected} 
        browserRunning={browserRunning}
      />

      {/* Main Content */}
      <main className="pl-64">
        <div className="p-8">
          <Routes>
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
            <Route 
              path="/history" 
              element={
                <FlowHistory onRerun={handleRerunFlow} />
              } 
            />
            <Route 
              path="/settings" 
              element={<Settings />} 
            />
          </Routes>
        </div>
      </main>

      {/* Background Gradient Effects */}
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-500/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl" />
      </div>
    </div>
  );
}

export default App;
