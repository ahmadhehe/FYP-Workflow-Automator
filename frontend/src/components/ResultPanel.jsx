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
      isSuccess ? 'border-emerald-300' : 'border-red-300'
    )}>
      {/* Header */}
      <div className={clsx(
        'px-6 py-4 border-b',
        isSuccess ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'
      )}>
        <div className="flex items-center gap-3">
          <div className={clsx(
            'p-2 rounded-lg',
            isSuccess ? 'bg-emerald-100' : 'bg-red-100'
          )}>
            {isSuccess ? (
              <CheckCircleIcon className="h-5 w-5 text-emerald-600" />
            ) : (
              <XCircleIcon className="h-5 w-5 text-red-600" />
            )}
          </div>
          <div>
            <h2 className={clsx(
              'text-lg font-semibold',
              isSuccess ? 'text-emerald-700' : 'text-red-700'
            )}>
              {isSuccess ? 'Task Completed' : 'Task Failed'}
            </h2>
            <p className="text-sm text-gray-500">
              {isSuccess ? 'The automation completed successfully' : 'An error occurred during execution'}
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-6 bg-white">
        {error ? (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-700 font-mono text-sm">{error}</p>
          </div>
        ) : result ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-gray-500">
              <DocumentTextIcon className="h-4 w-4" />
              <span className="text-sm font-medium">Agent Response</span>
            </div>
            <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg">
              <p className="text-gray-700 whitespace-pre-wrap">{result}</p>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default ResultPanel;
