import React from 'react';
import clsx from 'clsx';

export function StatusBar({ status, currentIteration, isConnected }) {
  const getStatusConfig = () => {
    switch (status) {
      case 'running':
        return {
          color: 'bg-primary-500',
          text: 'Running',
          pulse: true,
          textColor: 'text-primary-400',
        };
      case 'completed':
        return {
          color: 'bg-emerald-500',
          text: 'Completed',
          pulse: false,
          textColor: 'text-emerald-400',
        };
      case 'failed':
      case 'error':
        return {
          color: 'bg-red-500',
          text: 'Failed',
          pulse: false,
          textColor: 'text-red-400',
        };
      case 'initializing':
        return {
          color: 'bg-amber-500',
          text: 'Initializing',
          pulse: true,
          textColor: 'text-amber-400',
        };
      default:
        return {
          color: 'bg-dark-600',
          text: 'Idle',
          pulse: false,
          textColor: 'text-dark-400',
        };
    }
  };

  const config = getStatusConfig();

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        {/* Status Indicator */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="relative">
              <span className={clsx(
                'block h-3 w-3 rounded-full',
                config.color,
                config.pulse && 'animate-pulse'
              )} />
              {config.pulse && (
                <span className={clsx(
                  'absolute inset-0 h-3 w-3 rounded-full animate-ping opacity-75',
                  config.color
                )} />
              )}
            </div>
            <span className={clsx('font-medium', config.textColor)}>
              {config.text}
            </span>
          </div>

          {/* Connection Status */}
          <div className="h-4 w-px bg-dark-700" />
          <div className="flex items-center gap-2">
            <span className={clsx(
              'h-2 w-2 rounded-full',
              isConnected ? 'bg-emerald-500' : 'bg-red-500'
            )} />
            <span className="text-sm text-dark-400">
              {isConnected ? 'Live' : 'Offline'}
            </span>
          </div>
        </div>

        {/* Iteration Counter */}
        {currentIteration && (
          <div className="flex items-center gap-3 px-4 py-2 bg-dark-800 rounded-lg">
            <span className="text-sm text-dark-400">Iteration</span>
            <div className="flex items-baseline gap-1">
              <span className="text-xl font-semibold text-primary-400">
                {currentIteration.current}
              </span>
              <span className="text-dark-500">/</span>
              <span className="text-dark-400">{currentIteration.max}</span>
            </div>
            {/* Progress bar */}
            <div className="w-24 h-1.5 bg-dark-700 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-primary-500 to-cyan-500 transition-all duration-300"
                style={{ 
                  width: `${(currentIteration.current / currentIteration.max) * 100}%` 
                }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default StatusBar;
