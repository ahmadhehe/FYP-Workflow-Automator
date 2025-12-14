import React, { useState } from 'react';
import { 
  PaperAirplaneIcon, 
  GlobeAltIcon,
  ChevronDownIcon,
  SparklesIcon
} from '@heroicons/react/24/outline';
import clsx from 'clsx';

const providers = [
  { id: 'openai', name: 'OpenAI', description: 'GPT-4 Turbo' },
  { id: 'anthropic', name: 'Anthropic', description: 'Claude 3.5 Sonnet' },
  { id: 'gemini', name: 'Google Gemini', description: 'Gemini 2.5 Flash' },
];

export function TaskInput({ onSubmit, isRunning, onStop }) {
  const [instruction, setInstruction] = useState('');
  const [initialUrl, setInitialUrl] = useState('');
  const [provider, setProvider] = useState(() => localStorage.getItem('defaultProvider') || 'openai');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!instruction.trim() || isRunning) return;
    
    onSubmit({
      instruction: instruction.trim(),
      initialUrl: initialUrl.trim() || null,
      provider,
    });
  };

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-maroon-500 to-maroon-600">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-white/20">
            <SparklesIcon className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">New Automation</h2>
            <p className="text-sm text-maroon-100">Describe what you want the agent to do</p>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="p-6 space-y-4">
        {/* Main instruction input */}
        <div>
          <label className="label">Task Description</label>
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="e.g., Go to amazon.com, search for 'wireless headphones', and find the best rated option under $100"
            className="input min-h-[120px] resize-none"
            disabled={isRunning}
          />
        </div>

        {/* Advanced options toggle */}
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          <ChevronDownIcon className={clsx(
            'h-4 w-4 transition-transform duration-200',
            showAdvanced && 'rotate-180'
          )} />
          Advanced Options
        </button>

        {/* Advanced options */}
        {showAdvanced && (
          <div className="space-y-4 pt-2 animate-fade-in">
            {/* Initial URL */}
            <div>
              <label className="label">Starting URL (optional)</label>
              <div className="relative">
                <GlobeAltIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
                <input
                  type="url"
                  value={initialUrl}
                  onChange={(e) => setInitialUrl(e.target.value)}
                  placeholder="https://example.com"
                  className="input pl-12"
                  disabled={isRunning}
                />
              </div>
            </div>

            {/* Provider selection */}
            <div>
              <label className="label">AI Provider</label>
              <div className="grid grid-cols-2 gap-3">
                {providers.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setProvider(p.id)}
                    disabled={isRunning}
                    className={clsx(
                      'p-4 rounded-lg border text-left transition-all duration-200',
                      provider === p.id
                        ? 'border-maroon-500 bg-maroon-50 text-maroon-700'
                        : 'border-gray-200 hover:border-gray-300 text-gray-600 hover:bg-gray-50'
                    )}
                  >
                    <div className="font-medium">{p.name}</div>
                    <div className="text-xs text-gray-500 mt-1">{p.description}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Submit button */}
        <div className="flex gap-3 pt-2">
          {isRunning ? (
            <button
              type="button"
              onClick={onStop}
              className="btn-danger flex-1"
            >
              Stop Execution
            </button>
          ) : (
            <button
              type="submit"
              disabled={!instruction.trim()}
              className="btn-primary flex-1"
            >
              <PaperAirplaneIcon className="h-5 w-5" />
              Run Automation
            </button>
          )}
        </div>
      </form>
    </div>
  );
}

export default TaskInput;
