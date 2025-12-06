import React from 'react';
import { CheckCircleIcon, XCircleIcon, DocumentTextIcon } from '@heroicons/react/24/outline';
import clsx from 'clsx';

export function ResultPanel({ result, status, error }) {
  if (!result && !error) {
    return null;
  }

  const isSuccess = status === 'completed' && !error;

  return (
    <div className={clsx(
      'card overflow-hidden',
      isSuccess ? 'border-emerald-500/30' : 'border-red-500/30'
    )}>
      {/* Header */}
      <div className={clsx(
        'px-6 py-4 border-b border-dark-700/50',
        isSuccess ? 'bg-emerald-500/10' : 'bg-red-500/10'
      )}>
        <div className="flex items-center gap-3">
          <div className={clsx(
            'p-2 rounded-lg',
            isSuccess ? 'bg-emerald-500/20' : 'bg-red-500/20'
          )}>
            {isSuccess ? (
              <CheckCircleIcon className="h-5 w-5 text-emerald-400" />
            ) : (
              <XCircleIcon className="h-5 w-5 text-red-400" />
            )}
          </div>
          <div>
            <h2 className={clsx(
              'text-lg font-semibold',
              isSuccess ? 'text-emerald-400' : 'text-red-400'
            )}>
              {isSuccess ? 'Task Completed' : 'Task Failed'}
            </h2>
            <p className="text-sm text-dark-500">
              {isSuccess ? 'The automation completed successfully' : 'An error occurred during execution'}
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        {error ? (
          <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p className="text-red-400 font-mono text-sm">{error}</p>
          </div>
        ) : result ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-dark-400">
              <DocumentTextIcon className="h-4 w-4" />
              <span className="text-sm font-medium">Agent Response</span>
            </div>
            <div className="p-4 bg-dark-800/50 rounded-lg">
              <p className="text-dark-200 whitespace-pre-wrap">{result}</p>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default ResultPanel;
