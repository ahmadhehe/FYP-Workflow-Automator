import React, { useState, useEffect } from 'react';
import { 
  Cog6ToothIcon,
  KeyIcon,
  ServerIcon,
  PaintBrushIcon,
  TrashIcon,
  CheckIcon
} from '@heroicons/react/24/outline';
import api from '../services/api';
import clsx from 'clsx';

export function Settings() {
  const [browserStatus, setBrowserStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Settings state (stored in localStorage for frontend-only settings)
  const [settings, setSettings] = useState({
    defaultProvider: localStorage.getItem('defaultProvider') || 'openai',
    apiEndpoint: localStorage.getItem('apiEndpoint') || 'http://localhost:8000',
    wsEndpoint: localStorage.getItem('wsEndpoint') || 'ws://localhost:8000/ws',
    autoScroll: localStorage.getItem('autoScroll') !== 'false',
    soundNotifications: localStorage.getItem('soundNotifications') === 'true',
  });

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const status = await api.getStatus();
        setBrowserStatus(status);
      } catch (error) {
        console.error('Failed to fetch status:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();
  }, []);

  const handleSave = () => {
    setSaving(true);
    
    // Save to localStorage
    Object.entries(settings).forEach(([key, value]) => {
      localStorage.setItem(key, value.toString());
    });

    setTimeout(() => {
      setSaving(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }, 500);
  };

  const handleStartBrowser = async () => {
    try {
      await api.startBrowser(settings.defaultProvider, false);
      const status = await api.getStatus();
      setBrowserStatus(status);
    } catch (error) {
      console.error('Failed to start browser:', error);
    }
  };

  const handleStopBrowser = async () => {
    try {
      await api.stopBrowser();
      const status = await api.getStatus();
      setBrowserStatus(status);
    } catch (error) {
      console.error('Failed to stop browser:', error);
    }
  };

  const handleClearHistory = async () => {
    if (!window.confirm('Are you sure you want to clear all flow history?')) return;
    
    try {
      await api.clearFlows();
      alert('Flow history cleared successfully');
    } catch (error) {
      console.error('Failed to clear history:', error);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <div className="p-3 rounded-xl bg-gradient-to-br from-primary-500 to-cyan-500">
          <Cog6ToothIcon className="h-6 w-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-dark-100">Settings</h1>
          <p className="text-dark-500">Configure your browser agent preferences</p>
        </div>
      </div>

      {/* Browser Control */}
      <div className="card">
        <div className="px-6 py-4 border-b border-dark-700/50">
          <div className="flex items-center gap-3">
            <ServerIcon className="h-5 w-5 text-primary-400" />
            <h2 className="text-lg font-semibold text-dark-100">Browser Control</h2>
          </div>
        </div>
        <div className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-dark-200 font-medium">Browser Status</p>
              <p className="text-sm text-dark-500">
                {browserStatus?.browser_running 
                  ? 'The browser is currently running'
                  : 'The browser is not running'
                }
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className={clsx(
                'px-3 py-1 rounded-full text-sm font-medium',
                browserStatus?.browser_running 
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'bg-dark-700 text-dark-400'
              )}>
                {browserStatus?.browser_running ? 'Running' : 'Stopped'}
              </span>
              {browserStatus?.browser_running ? (
                <button onClick={handleStopBrowser} className="btn-danger py-2 px-4">
                  Stop Browser
                </button>
              ) : (
                <button onClick={handleStartBrowser} className="btn-primary py-2 px-4">
                  Start Browser
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* AI Provider */}
      <div className="card">
        <div className="px-6 py-4 border-b border-dark-700/50">
          <div className="flex items-center gap-3">
            <KeyIcon className="h-5 w-5 text-amber-400" />
            <h2 className="text-lg font-semibold text-dark-100">AI Provider</h2>
          </div>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="label">Default Provider</label>
            <select
              value={settings.defaultProvider}
              onChange={(e) => setSettings({ ...settings, defaultProvider: e.target.value })}
              className="input"
            >
              <option value="openai">OpenAI (GPT-4 Turbo)</option>
              <option value="anthropic">Anthropic (Claude 3.5 Sonnet)</option>
            </select>
            <p className="text-xs text-dark-500 mt-2">
              Make sure you have the corresponding API key set in your environment variables
            </p>
          </div>
        </div>
      </div>

      {/* Connection Settings */}
      <div className="card">
        <div className="px-6 py-4 border-b border-dark-700/50">
          <div className="flex items-center gap-3">
            <ServerIcon className="h-5 w-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-dark-100">Connection</h2>
          </div>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="label">API Endpoint</label>
            <input
              type="url"
              value={settings.apiEndpoint}
              onChange={(e) => setSettings({ ...settings, apiEndpoint: e.target.value })}
              className="input"
              placeholder="http://localhost:8000"
            />
          </div>
          <div>
            <label className="label">WebSocket Endpoint</label>
            <input
              type="url"
              value={settings.wsEndpoint}
              onChange={(e) => setSettings({ ...settings, wsEndpoint: e.target.value })}
              className="input"
              placeholder="ws://localhost:8000/ws"
            />
          </div>
        </div>
      </div>

      {/* UI Preferences */}
      <div className="card">
        <div className="px-6 py-4 border-b border-dark-700/50">
          <div className="flex items-center gap-3">
            <PaintBrushIcon className="h-5 w-5 text-purple-400" />
            <h2 className="text-lg font-semibold text-dark-100">Preferences</h2>
          </div>
        </div>
        <div className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-dark-200 font-medium">Auto-scroll Timeline</p>
              <p className="text-sm text-dark-500">Automatically scroll to new actions</p>
            </div>
            <button
              onClick={() => setSettings({ ...settings, autoScroll: !settings.autoScroll })}
              className={clsx(
                'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                settings.autoScroll ? 'bg-primary-600' : 'bg-dark-600'
              )}
            >
              <span
                className={clsx(
                  'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                  settings.autoScroll ? 'translate-x-6' : 'translate-x-1'
                )}
              />
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-dark-200 font-medium">Sound Notifications</p>
              <p className="text-sm text-dark-500">Play sound when task completes</p>
            </div>
            <button
              onClick={() => setSettings({ ...settings, soundNotifications: !settings.soundNotifications })}
              className={clsx(
                'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                settings.soundNotifications ? 'bg-primary-600' : 'bg-dark-600'
              )}
            >
              <span
                className={clsx(
                  'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                  settings.soundNotifications ? 'translate-x-6' : 'translate-x-1'
                )}
              />
            </button>
          </div>
        </div>
      </div>

      {/* Data Management */}
      <div className="card">
        <div className="px-6 py-4 border-b border-dark-700/50">
          <div className="flex items-center gap-3">
            <TrashIcon className="h-5 w-5 text-red-400" />
            <h2 className="text-lg font-semibold text-dark-100">Data Management</h2>
          </div>
        </div>
        <div className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-dark-200 font-medium">Clear Flow History</p>
              <p className="text-sm text-dark-500">Delete all recorded automation flows</p>
            </div>
            <button onClick={handleClearHistory} className="btn-danger py-2 px-4">
              Clear History
            </button>
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="btn-primary py-3 px-8"
        >
          {saved ? (
            <>
              <CheckIcon className="h-5 w-5" />
              Saved!
            </>
          ) : saving ? (
            'Saving...'
          ) : (
            'Save Settings'
          )}
        </button>
      </div>
    </div>
  );
}

export default Settings;
