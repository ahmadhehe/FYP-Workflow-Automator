import React, { useEffect, useRef } from 'react';
import { 
  CheckCircleIcon, 
  XCircleIcon, 
  ArrowPathIcon,
  CursorArrowRaysIcon,
  PencilSquareIcon,
  GlobeAltIcon,
  ArrowsUpDownIcon,
  LightBulbIcon,
  PlayIcon,
  CommandLineIcon
} from '@heroicons/react/24/outline';
import clsx from 'clsx';
import { formatDistanceToNow } from 'date-fns';

const getActionIcon = (type, tool) => {
  switch (type) {
    case 'start':
      return PlayIcon;
    case 'navigate':
      return GlobeAltIcon;
    case 'thinking':
      return LightBulbIcon;
    case 'complete':
      return CheckCircleIcon;
    case 'tool_call':
    case 'tool_result':
      switch (tool) {
        case 'click':
          return CursorArrowRaysIcon;
        case 'inputText':
          return PencilSquareIcon;
        case 'navigate':
          return GlobeAltIcon;
        case 'scrollDown':
        case 'scrollUp':
          return ArrowsUpDownIcon;
        case 'getInteractiveSnapshot':
          return CommandLineIcon;
        default:
          return CommandLineIcon;
      }
    default:
      return ArrowPathIcon;
  }
};

const getActionColor = (type, success) => {
  if (type === 'tool_result') {
    return success ? 'text-emerald-600 bg-emerald-100' : 'text-red-600 bg-red-100';
  }
  
  switch (type) {
    case 'start':
    case 'navigate':
      return 'text-maroon-600 bg-maroon-100';
    case 'thinking':
      return 'text-gold-600 bg-gold-100';
    case 'complete':
      return 'text-emerald-600 bg-emerald-100';
    case 'tool_call':
      return 'text-blue-600 bg-blue-100';
    default:
      return 'text-gray-500 bg-gray-100';
  }
};

function ActionItem({ action, isLatest }) {
  const Icon = getActionIcon(action.type, action.tool);
  const colorClass = getActionColor(action.type, action.success);

  return (
    <div className={clsx(
      'flex gap-4 p-4 rounded-lg transition-all duration-300',
      isLatest ? 'bg-maroon-50 border border-maroon-200' : 'hover:bg-gray-50'
    )}>
      {/* Icon */}
      <div className={clsx(
        'flex-shrink-0 p-2 rounded-lg',
        colorClass
      )}>
        <Icon className="h-5 w-5" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-gray-900">
            {action.tool || action.type}
          </span>
          {action.iteration > 0 && (
            <span className="badge-neutral text-xs">
              Step {action.iteration}
            </span>
          )}
          {action.type === 'tool_result' && (
            action.success ? (
              <CheckCircleIcon className="h-4 w-4 text-emerald-500" />
            ) : (
              <XCircleIcon className="h-4 w-4 text-red-500" />
            )
          )}
        </div>
        
        <p className="text-sm text-gray-500 mt-1 line-clamp-2">
          {action.message}
        </p>

        {/* Arguments preview for tool calls */}
        {action.arguments && Object.keys(action.arguments).length > 0 && (
          <div className="mt-2 p-2 bg-gray-100 rounded text-xs font-mono text-gray-600 overflow-x-auto">
            {JSON.stringify(action.arguments, null, 2).substring(0, 200)}
            {JSON.stringify(action.arguments).length > 200 && '...'}
          </div>
        )}

        {/* URL for navigate actions */}
        {action.url && (
          <div className="mt-2 text-xs text-maroon-600 truncate">
            {action.url}
          </div>
        )}
      </div>

      {/* Timestamp */}
      {action.timestamp && (
        <div className="flex-shrink-0 text-xs text-gray-400">
          {formatDistanceToNow(new Date(action.timestamp), { addSuffix: true })}
        </div>
      )}
    </div>
  );
}

export function ActionTimeline({ events, taskStatus }) {
  const containerRef = useRef(null);
  const shouldAutoScroll = useRef(true);

  // Auto-scroll to latest action
  useEffect(() => {
    if (shouldAutoScroll.current && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [events]);

  // Handle manual scroll
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    shouldAutoScroll.current = scrollHeight - scrollTop - clientHeight < 100;
  };

  const isEmpty = events.length === 0;

  return (
    <div className="card flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-maroon-100">
              <CommandLineIcon className="h-5 w-5 text-maroon-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Action Timeline</h2>
              <p className="text-sm text-gray-500">
                {events.length} action{events.length !== 1 ? 's' : ''} recorded
              </p>
            </div>
          </div>
          
          {taskStatus === 'running' && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-maroon-100 rounded-full">
              <span className="h-2 w-2 rounded-full bg-maroon-500 animate-pulse" />
              <span className="text-xs font-medium text-maroon-700">Live</span>
            </div>
          )}
        </div>
      </div>

      {/* Timeline content */}
      <div 
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-2"
      >
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-12">
            <div className="p-4 rounded-full bg-gray-100 mb-4">
              <CommandLineIcon className="h-8 w-8 text-gray-400" />
            </div>
            <h3 className="text-gray-700 font-medium mb-2">No actions yet</h3>
            <p className="text-gray-500 text-sm max-w-xs">
              Start a new automation task to see the agent's actions appear here in real-time
            </p>
          </div>
        ) : (
          events.map((action, index) => (
            <ActionItem 
              key={`${action.timestamp}-${index}`}
              action={action}
              isLatest={index === events.length - 1}
            />
          ))
        )}
      </div>
    </div>
  );
}

export default ActionTimeline;
