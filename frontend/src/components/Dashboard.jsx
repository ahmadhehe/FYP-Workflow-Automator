import React, { useState, useCallback } from 'react';
import { TaskInput } from './TaskInput';
import { StatusBar } from './StatusBar';
import { ActionTimeline } from './ActionTimeline';
import { ResultPanel } from './ResultPanel';
import api from '../services/api';

export function Dashboard({ 
  events, 
  taskStatus, 
  currentIteration, 
  isConnected, 
  clearEvents,
  browserRunning,
  initialTask
}) {
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = useCallback(async ({ instruction, initialUrl, provider, fileContent, fileName }) => {
    // Clear previous state
    clearEvents();
    setResult(null);
    setError(null);
    setIsRunning(true);

    try {
      const response = await api.runTask(instruction, initialUrl, provider, fileContent, fileName);
      
      if (response.success) {
        setResult(response.result);
      } else {
        setError(response.error || 'Task failed');
      }
    } catch (err) {
      setError(err.message || 'An error occurred');
    } finally {
      setIsRunning(false);
    }
  }, [clearEvents]);

  const handleStop = useCallback(async () => {
    try {
      await api.stopBrowser();
    } catch (err) {
      console.error('Failed to stop:', err);
    }
  }, []);

  // Handle initial task from history re-run
  React.useEffect(() => {
    if (initialTask) {
      handleSubmit(initialTask);
    }
  }, [initialTask, handleSubmit]);

  const effectiveStatus = isRunning ? 'running' : taskStatus;

  return (
    <div className="space-y-6 h-full">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 mt-1">Create and monitor browser automation tasks</p>
      </div>

      {/* Status Bar */}
      <StatusBar 
        status={effectiveStatus} 
        currentIteration={currentIteration}
        isConnected={isConnected}
      />

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" style={{ minHeight: 'calc(100vh - 320px)' }}>
        {/* Left Column */}
        <div className="space-y-6">
          <TaskInput 
            onSubmit={handleSubmit}
            isRunning={isRunning}
            onStop={handleStop}
          />
          
          {(result || error) && (
            <ResultPanel 
              result={result}
              status={effectiveStatus}
              error={error}
            />
          )}
        </div>

        {/* Right Column - Action Timeline */}
        <div className="lg:row-span-2">
          <ActionTimeline 
            events={events}
            taskStatus={effectiveStatus}
          />
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
