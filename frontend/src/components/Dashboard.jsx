import React, { useState, useCallback, useEffect } from 'react';
import { TaskInput } from './TaskInput';
import { StatusBar } from './StatusBar';
import { ActionTimeline } from './ActionTimeline';
import { ResultPanel } from './ResultPanel';
import { QuickActions } from './QuickActions';
import { useTeacherProfile } from '../hooks/useTeacherProfile';
import api from '../services/api';

const REASON_ICONS = {
  captcha: '🤖',
  otp: '🔐',
  '2fa': '🔐',
  login: '🔑',
  cookie_consent: '🍪',
  manual: '👆',
  other: '❓',
};

function InterventionBanner({ data }) {
  const [value, setValue] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setValue('');
  }, [data?.message, data?.reason]);

  const submit = async (response) => {
    setSubmitting(true);
    try {
      await api.respondToIntervention(response);
    } catch (e) {
      console.error('Failed to respond to intervention:', e);
    } finally {
      setSubmitting(false);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      submit(value);
    }
  };

  const icon = REASON_ICONS[data?.reason] || '👆';

  return (
    <div className="card p-4 border-2 border-amber-400 bg-amber-50/60">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-amber-200 flex items-center justify-center text-xl">
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-amber-900">Action required in browser</div>
          <div className="text-sm text-amber-800 mt-0.5">
            {data?.message || 'Please complete the action.'}
          </div>
          <div className="flex gap-2 mt-3">
            <input
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Enter response (optional)…"
              disabled={submitting}
              className="flex-1 px-3 py-2 text-sm rounded-lg border border-amber-300 bg-white/80 focus:outline-none focus:ring-2 focus:ring-amber-400"
            />
            <button
              onClick={() => submit(value)}
              disabled={submitting}
              className="px-4 py-2 text-sm font-semibold rounded-lg bg-maroon-600 text-white hover:bg-maroon-700 disabled:opacity-60"
            >
              Submit
            </button>
            <button
              onClick={() => submit('')}
              disabled={submitting}
              className="px-3 py-2 text-sm font-semibold rounded-lg bg-gray-200 text-gray-800 hover:bg-gray-300 disabled:opacity-60"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Dashboard({
  events,
  taskStatus,
  currentIteration,
  isConnected,
  clearEvents,
  browserRunning,
  initialTask,
  interventionData,
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

      {interventionData && <InterventionBanner data={interventionData} />}

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
