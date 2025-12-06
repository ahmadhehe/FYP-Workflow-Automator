import React, { useState, useEffect } from 'react';
import { 
  ClockIcon, 
  ArrowPathIcon, 
  TrashIcon,
  PencilIcon,
  PlayIcon,
  CheckCircleIcon,
  XCircleIcon,
  ChevronRightIcon,
  MagnifyingGlassIcon,
  FunnelIcon
} from '@heroicons/react/24/outline';
import { formatDistanceToNow, format } from 'date-fns';
import clsx from 'clsx';
import api from '../services/api';

function FlowCard({ flow, onSelect, onRerun, onDelete, isSelected }) {
  const statusConfig = {
    completed: { icon: CheckCircleIcon, color: 'text-emerald-400', bg: 'bg-emerald-500/20' },
    failed: { icon: XCircleIcon, color: 'text-red-400', bg: 'bg-red-500/20' },
    running: { icon: ArrowPathIcon, color: 'text-primary-400', bg: 'bg-primary-500/20' },
  };

  const config = statusConfig[flow.status] || statusConfig.completed;
  const StatusIcon = config.icon;

  return (
    <div 
      onClick={() => onSelect(flow)}
      className={clsx(
        'card-hover p-4 cursor-pointer group',
        isSelected && 'border-primary-500 bg-primary-500/5'
      )}
    >
      <div className="flex items-start gap-4">
        {/* Status Icon */}
        <div className={clsx('p-2 rounded-lg flex-shrink-0', config.bg)}>
          <StatusIcon className={clsx('h-5 w-5', config.color)} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <p className="text-dark-100 font-medium line-clamp-2 group-hover:text-primary-400 transition-colors">
            {flow.instruction}
          </p>
          
          <div className="flex items-center gap-4 mt-2 text-sm text-dark-500">
            {flow.initial_url && (
              <span className="truncate max-w-[200px]">{flow.initial_url}</span>
            )}
            <span>{flow.action_count} actions</span>
          </div>

          <div className="flex items-center justify-between mt-3">
            <span className="text-xs text-dark-600">
              {formatDistanceToNow(new Date(flow.created_at), { addSuffix: true })}
            </span>

            {/* Actions */}
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={(e) => { e.stopPropagation(); onRerun(flow); }}
                className="p-1.5 rounded-md hover:bg-dark-700 text-dark-400 hover:text-primary-400 transition-colors"
                title="Re-run"
              >
                <PlayIcon className="h-4 w-4" />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(flow.id); }}
                className="p-1.5 rounded-md hover:bg-dark-700 text-dark-400 hover:text-red-400 transition-colors"
                title="Delete"
              >
                <TrashIcon className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        <ChevronRightIcon className="h-5 w-5 text-dark-600 group-hover:text-dark-400 transition-colors flex-shrink-0" />
      </div>
    </div>
  );
}

function FlowDetail({ flow, onEdit, onRerun, onClose }) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedInstruction, setEditedInstruction] = useState(flow.instruction);

  const handleSave = async () => {
    await onEdit(flow.id, editedInstruction);
    setIsEditing(false);
  };

  return (
    <div className="card h-full overflow-hidden flex flex-col">
      {/* Header */}
      <div className="px-6 py-4 border-b border-dark-700/50 bg-dark-800/30 flex-shrink-0">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-dark-100">Flow Details</h3>
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-dark-700 text-dark-400"
          >
            <XCircleIcon className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Instruction */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="label mb-0">Task Description</label>
            {!isEditing && (
              <button
                onClick={() => setIsEditing(true)}
                className="btn-ghost py-1 px-2 text-xs"
              >
                <PencilIcon className="h-3.5 w-3.5" />
                Edit
              </button>
            )}
          </div>
          {isEditing ? (
            <div className="space-y-3">
              <textarea
                value={editedInstruction}
                onChange={(e) => setEditedInstruction(e.target.value)}
                className="input min-h-[120px] resize-none"
              />
              <div className="flex gap-2">
                <button onClick={handleSave} className="btn-primary py-2 px-4 text-sm">
                  Save Changes
                </button>
                <button 
                  onClick={() => { setIsEditing(false); setEditedInstruction(flow.instruction); }}
                  className="btn-secondary py-2 px-4 text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <p className="text-dark-200 bg-dark-800/50 p-4 rounded-lg">
              {flow.instruction}
            </p>
          )}
        </div>

        {/* Metadata */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-dark-800/30 rounded-lg">
            <span className="text-xs text-dark-500 block mb-1">Status</span>
            <span className={clsx(
              'font-medium capitalize',
              flow.status === 'completed' ? 'text-emerald-400' : 'text-red-400'
            )}>
              {flow.status}
            </span>
          </div>
          <div className="p-4 bg-dark-800/30 rounded-lg">
            <span className="text-xs text-dark-500 block mb-1">Actions</span>
            <span className="font-medium text-dark-200">{flow.action_count}</span>
          </div>
          <div className="p-4 bg-dark-800/30 rounded-lg">
            <span className="text-xs text-dark-500 block mb-1">Created</span>
            <span className="font-medium text-dark-200 text-sm">
              {format(new Date(flow.created_at), 'MMM d, yyyy HH:mm')}
            </span>
          </div>
          <div className="p-4 bg-dark-800/30 rounded-lg">
            <span className="text-xs text-dark-500 block mb-1">Provider</span>
            <span className="font-medium text-dark-200 capitalize">{flow.provider || 'openai'}</span>
          </div>
        </div>

        {/* Initial URL */}
        {flow.initial_url && (
          <div>
            <label className="label">Starting URL</label>
            <p className="text-primary-400 bg-dark-800/50 p-4 rounded-lg text-sm break-all">
              {flow.initial_url}
            </p>
          </div>
        )}

        {/* Result */}
        {flow.result && (
          <div>
            <label className="label">Result</label>
            <div className="bg-dark-800/50 p-4 rounded-lg">
              <p className="text-dark-200 whitespace-pre-wrap">{flow.result}</p>
            </div>
          </div>
        )}

        {/* Error */}
        {flow.error && (
          <div>
            <label className="label text-red-400">Error</label>
            <div className="bg-red-500/10 border border-red-500/20 p-4 rounded-lg">
              <p className="text-red-400 font-mono text-sm">{flow.error}</p>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-dark-700/50 flex-shrink-0">
        <button
          onClick={() => onRerun(flow)}
          className="btn-primary w-full"
        >
          <PlayIcon className="h-5 w-5" />
          Re-run This Flow
        </button>
      </div>
    </div>
  );
}

export function FlowHistory({ onRerun }) {
  const [flows, setFlows] = useState([]);
  const [selectedFlow, setSelectedFlow] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const fetchFlows = async () => {
    try {
      const data = await api.getFlows(50);
      setFlows(data.flows);
    } catch (error) {
      console.error('Failed to fetch flows:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFlows();
  }, []);

  const handleDelete = async (flowId) => {
    if (!window.confirm('Are you sure you want to delete this flow?')) return;
    
    try {
      await api.deleteFlow(flowId);
      setFlows(flows.filter(f => f.id !== flowId));
      if (selectedFlow?.id === flowId) {
        setSelectedFlow(null);
      }
    } catch (error) {
      console.error('Failed to delete flow:', error);
    }
  };

  const handleEdit = async (flowId, newInstruction) => {
    try {
      await api.updateFlow(flowId, newInstruction);
      setFlows(flows.map(f => 
        f.id === flowId ? { ...f, instruction: newInstruction } : f
      ));
      if (selectedFlow?.id === flowId) {
        setSelectedFlow({ ...selectedFlow, instruction: newInstruction });
      }
    } catch (error) {
      console.error('Failed to update flow:', error);
    }
  };

  const handleRerun = (flow) => {
    onRerun({
      instruction: flow.instruction,
      initialUrl: flow.initial_url,
      provider: flow.provider,
    });
  };

  const handleClearAll = async () => {
    if (!window.confirm('Are you sure you want to delete all flow history?')) return;
    
    try {
      await api.clearFlows();
      setFlows([]);
      setSelectedFlow(null);
    } catch (error) {
      console.error('Failed to clear flows:', error);
    }
  };

  // Filter flows
  const filteredFlows = flows.filter(flow => {
    const matchesSearch = flow.instruction.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || flow.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <ArrowPathIcon className="h-8 w-8 text-dark-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex gap-6 h-full">
      {/* Flow List */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header & Filters */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-amber-500/20">
                <ClockIcon className="h-5 w-5 text-amber-400" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-dark-100">Flow History</h2>
                <p className="text-sm text-dark-500">{flows.length} recorded automations</p>
              </div>
            </div>
            
            {flows.length > 0 && (
              <button onClick={handleClearAll} className="btn-danger py-2 px-4 text-sm">
                <TrashIcon className="h-4 w-4" />
                Clear All
              </button>
            )}
          </div>

          {/* Search & Filter */}
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <MagnifyingGlassIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-dark-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search flows..."
                className="input pl-12"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input w-40"
            >
              <option value="all">All Status</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>

        {/* Flow List */}
        <div className="flex-1 overflow-y-auto space-y-3">
          {filteredFlows.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <div className="p-4 rounded-full bg-dark-800 mb-4">
                <ClockIcon className="h-8 w-8 text-dark-500" />
              </div>
              <h3 className="text-dark-300 font-medium mb-2">
                {searchQuery || statusFilter !== 'all' ? 'No matching flows' : 'No flow history yet'}
              </h3>
              <p className="text-dark-500 text-sm max-w-xs">
                {searchQuery || statusFilter !== 'all' 
                  ? 'Try adjusting your search or filters'
                  : 'Run your first automation to see it appear here'
                }
              </p>
            </div>
          ) : (
            filteredFlows.map(flow => (
              <FlowCard
                key={flow.id}
                flow={flow}
                onSelect={setSelectedFlow}
                onRerun={handleRerun}
                onDelete={handleDelete}
                isSelected={selectedFlow?.id === flow.id}
              />
            ))
          )}
        </div>
      </div>

      {/* Flow Detail Panel */}
      {selectedFlow && (
        <div className="w-[400px] flex-shrink-0">
          <FlowDetail
            flow={selectedFlow}
            onEdit={handleEdit}
            onRerun={handleRerun}
            onClose={() => setSelectedFlow(null)}
          />
        </div>
      )}
    </div>
  );
}

export default FlowHistory;
