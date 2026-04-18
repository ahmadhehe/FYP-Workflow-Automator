import React, { useState, useCallback } from 'react';
import { TaskInput } from './TaskInput';
import { StatusBar } from './StatusBar';
import { ActionTimeline } from './ActionTimeline';
import { ResultPanel } from './ResultPanel';
import { QuickActions } from './QuickActions';
import { useTeacherProfile } from '../hooks/useTeacherProfile';
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
  const [injectedPrompt, setInjectedPrompt] = useState(null);

  const { courses } = useTeacherProfile();

  const handleSubmit = useCallback(async ({ instruction, initialUrl, provider, files }) => {
    clearEvents();
    setResult(null);
    setError(null);
    setIsRunning(true);

    try {
      const response = await api.runTask(instruction, initialUrl, provider, files);
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

  const handleInjectPrompt = useCallback((promptText) => {
    setInjectedPrompt(promptText);
    setTimeout(() => setInjectedPrompt(null), 100);
  }, []);

  React.useEffect(() => {
    if (initialTask) {
      handleSubmit(initialTask);
    }
  }, [initialTask, handleSubmit]);

  const effectiveStatus = isRunning ? 'running' : taskStatus;

  return (
    <div className="space-y-6 h-full">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 mt-1">Create and monitor browser automation tasks</p>
      </div>

      <StatusBar
        status={effectiveStatus}
        currentIteration={currentIteration}
        isConnected={isConnected}
      />

      {/* 3-column layout: Left sidebar | Task Input + Result | Timeline */}
      <div
        className="grid grid-cols-1 lg:grid-cols-[220px_1fr_1fr] gap-6"
        style={{ minHeight: 'calc(100vh - 320px)' }}
      >
        {/* Left column: Quick Actions */}
        <div>
          <QuickActions
            courses={courses}
            onInjectPrompt={handleInjectPrompt}
            isRunning={isRunning}
          />
        </div>

        {/* Center column */}
        <div className="space-y-6">
          <TaskInput
            onSubmit={handleSubmit}
            isRunning={isRunning}
            onStop={handleStop}
            injectedPrompt={injectedPrompt}
          />
          {(result || error) && (
            <ResultPanel
              result={result}
              status={effectiveStatus}
              error={error}
            />
          )}
        </div>

        {/* Timeline */}
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
