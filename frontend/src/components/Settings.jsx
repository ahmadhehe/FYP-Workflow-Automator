import React, { useState, useEffect } from 'react';
import { 
  Cog6ToothIcon,
  KeyIcon,
  ServerIcon,
  PaintBrushIcon,
  TrashIcon,
  CheckIcon,
  UserCircleIcon,
  GlobeAltIcon
} from '@heroicons/react/24/outline';
import api from '../services/api';
import clsx from 'clsx';

export function Settings() {
  const [browserStatus, setBrowserStatus] = useState(null);
  const [profileStatus, setProfileStatus] = useState(null);
  const [profileUrl, setProfileUrl] = useState('');
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
        const [status, profile] = await Promise.all([
          api.getStatus(),
          api.getProfileStatus()
        ]);
        setBrowserStatus(status);
        setProfileStatus(profile);
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

  const handleStartProfileBrowser = async () => {
    try {
      await api.startProfileBrowser(profileUrl || null);
      const profile = await api.getProfileStatus();
      setProfileStatus(profile);
    } catch (error) {
      console.error('Failed to start profile browser:', error);
      alert(error.message || 'Failed to start profile browser');
    }
  };

  const handleStopProfileBrowser = async () => {
    try {
      await api.stopProfileBrowser();
      const profile = await api.getProfileStatus();
      setProfileStatus(profile);
    } catch (error) {
      console.error('Failed to stop profile browser:', error);
    }
  };

  const handleClearProfile = async () => {
    if (!window.confirm('Are you sure you want to clear all saved credentials? You will need to log in to websites again.')) return;
    
    try {
      await api.clearProfile();
      const profile = await api.getProfileStatus();
      setProfileStatus(profile);
      alert('Profile data cleared successfully');
    } catch (error) {
      console.error('Failed to clear profile:', error);
      alert(error.message || 'Failed to clear profile');
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <div className="p-3 rounded-xl bg-gradient-to-br from-maroon-600 to-maroon-800">
          <Cog6ToothIcon className="h-6 w-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="text-gray-500">Configure your browser agent preferences</p>
        </div>
      </div>

      {/* Browser Control */}
      <div className="card">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center gap-3">
            <ServerIcon className="h-5 w-5 text-maroon-600" />
            <h2 className="text-lg font-semibold text-gray-900">Browser Control</h2>
          </div>
        </div>
        <div className="p-6 bg-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-700 font-medium">Browser Status</p>
              <p className="text-sm text-gray-500">
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
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-gray-100 text-gray-500'
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

      {/* Profile Management */}
      <div className="card">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center gap-3">
            <UserCircleIcon className="h-5 w-5 text-indigo-600" />
            <h2 className="text-lg font-semibold text-gray-900">Saved Credentials</h2>
          </div>
        </div>
        <div className="p-6 space-y-4 bg-white">
          <p className="text-sm text-gray-600 mb-4">
            Launch a browser to log into websites. Your credentials, cookies, and sessions will be saved 
            and automatically used when running automation tasks.
          </p>
          
          {/* Profile Status */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <p className="text-gray-700 font-medium">Profile Status</p>
              <p className="text-sm text-gray-500">
                {profileStatus?.profile_exists 
                  ? `Profile saved (${profileStatus?.profile_size_mb || 0} MB)`
                  : 'No saved profile'
                }
              </p>
            </div>
            <span className={clsx(
              'px-3 py-1 rounded-full text-sm font-medium',
              profileStatus?.profile_browser_running 
                ? 'bg-indigo-100 text-indigo-700'
                : profileStatus?.profile_exists
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-gray-100 text-gray-500'
            )}>
              {profileStatus?.profile_browser_running 
                ? 'Browser Open' 
                : profileStatus?.profile_exists 
                  ? 'Saved'
                  : 'Not Set Up'
              }
            </span>
          </div>

          {/* URL Input for Profile Browser */}
          <div>
            <label className="label">Starting URL (optional)</label>
            <div className="flex gap-2">
              <input
                type="url"
                value={profileUrl}
                onChange={(e) => setProfileUrl(e.target.value)}
                className="input flex-1"
                placeholder="https://example.com/login"
                disabled={profileStatus?.profile_browser_running}
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Enter a URL to navigate to when opening the profile browser
            </p>
          </div>

          {/* Profile Browser Controls */}
          <div className="flex items-center gap-3">
            {profileStatus?.profile_browser_running ? (
              <button 
                onClick={handleStopProfileBrowser} 
                className="btn-primary py-2 px-4 flex items-center gap-2"
              >
                <CheckIcon className="h-4 w-4" />
                Done Setting Up
              </button>
            ) : (
              <button 
                onClick={handleStartProfileBrowser} 
                className="btn-primary py-2 px-4 flex items-center gap-2"
                disabled={browserStatus?.browser_running}
              >
                <GlobeAltIcon className="h-4 w-4" />
                Open Profile Browser
              </button>
            )}
            
            {profileStatus?.profile_exists && !profileStatus?.profile_browser_running && (
              <button 
                onClick={handleClearProfile} 
                className="btn-danger py-2 px-4"
              >
                Clear Saved Credentials
              </button>
            )}
          </div>
          
          {browserStatus?.browser_running && !profileStatus?.profile_browser_running && (
            <p className="text-sm text-amber-600 mt-2">
              ⚠️ Stop the automation browser first to set up credentials
            </p>
          )}
        </div>
      </div>

      {/* AI Provider */}
      <div className="card">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center gap-3">
            <KeyIcon className="h-5 w-5 text-gold-600" />
            <h2 className="text-lg font-semibold text-gray-900">AI Provider</h2>
          </div>
        </div>
        <div className="p-6 space-y-4 bg-white">
          <div>
            <label className="label">Default Provider</label>
            <select
              value={settings.defaultProvider}
              onChange={(e) => setSettings({ ...settings, defaultProvider: e.target.value })}
              className="input"
            >
              <option value="openai">OpenAI (GPT-4 Turbo)</option>
              <option value="anthropic">Anthropic (Claude 3.5 Sonnet)</option>
              <option value="gemini">Google Gemini (2.5 Flash)</option>
            </select>
            <p className="text-xs text-gray-500 mt-2">
              Make sure you have the corresponding API key set in your environment variables
            </p>
          </div>
        </div>
      </div>

      {/* Connection Settings */}
      <div className="card">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center gap-3">
            <ServerIcon className="h-5 w-5 text-blue-600" />
            <h2 className="text-lg font-semibold text-gray-900">Connection</h2>
          </div>
        </div>
        <div className="p-6 space-y-4 bg-white">
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
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center gap-3">
            <PaintBrushIcon className="h-5 w-5 text-maroon-600" />
            <h2 className="text-lg font-semibold text-gray-900">Preferences</h2>
          </div>
        </div>
        <div className="p-6 space-y-4 bg-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-700 font-medium">Auto-scroll Timeline</p>
              <p className="text-sm text-gray-500">Automatically scroll to new actions</p>
            </div>
            <button
              onClick={() => setSettings({ ...settings, autoScroll: !settings.autoScroll })}
              className={clsx(
                'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                settings.autoScroll ? 'bg-maroon-600' : 'bg-gray-300'
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
              <p className="text-gray-700 font-medium">Sound Notifications</p>
              <p className="text-sm text-gray-500">Play sound when task completes</p>
            </div>
            <button
              onClick={() => setSettings({ ...settings, soundNotifications: !settings.soundNotifications })}
              className={clsx(
                'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                settings.soundNotifications ? 'bg-maroon-600' : 'bg-gray-300'
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
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center gap-3">
            <TrashIcon className="h-5 w-5 text-red-500" />
            <h2 className="text-lg font-semibold text-gray-900">Data Management</h2>
          </div>
        </div>
        <div className="p-6 bg-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-700 font-medium">Clear Flow History</p>
              <p className="text-sm text-gray-500">Delete all recorded automation flows</p>
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
