import React, { useState, useEffect } from 'react';
import { 
  BanknotesIcon,
  CurrencyDollarIcon,
  ChartBarIcon,
  CalendarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon
} from '@heroicons/react/24/outline';
import api from '../services/api';
import clsx from 'clsx';

// Pricing per 1M tokens (as of Dec 2024)
const PRICING = {
  openai: {
    name: 'OpenAI GPT-4 Turbo',
    input: 10.00,   // $10 per 1M input tokens
    output: 30.00,  // $30 per 1M output tokens
  },
  anthropic: {
    name: 'Claude 3.5 Sonnet',
    input: 3.00,    // $3 per 1M input tokens
    output: 15.00,  // $15 per 1M output tokens
  },
  gemini: {
    name: 'Gemini 2.5 Flash',
    input: 0.075,   // $0.075 per 1M input tokens (128k context)
    output: 0.30,   // $0.30 per 1M output tokens
  }
};

export function Costs() {
  const [costs, setCosts] = useState(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('all'); // all, today, week, month

  useEffect(() => {
    const fetchCosts = async () => {
      try {
        const data = await api.getCosts(timeRange);
        setCosts(data);
      } catch (error) {
        console.error('Failed to fetch costs:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchCosts();
  }, [timeRange]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-maroon-600"></div>
      </div>
    );
  }

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 4,
      maximumFractionDigits: 4,
    }).format(amount);
  };

  const formatNumber = (num) => {
    return new Intl.NumberFormat('en-US').format(num);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Cost Analytics</h1>
          <p className="text-gray-500 mt-1">Track your LLM API usage and costs</p>
        </div>

        {/* Time Range Filter */}
        <div className="flex gap-2">
          {[
            { value: 'all', label: 'All Time' },
            { value: 'today', label: 'Today' },
            { value: 'week', label: 'This Week' },
            { value: 'month', label: 'This Month' },
          ].map((range) => (
            <button
              key={range.value}
              onClick={() => setTimeRange(range.value)}
              className={clsx(
                'px-4 py-2 rounded-lg text-sm font-medium transition-all',
                timeRange === range.value
                  ? 'bg-maroon-600 text-white shadow-md'
                  : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
              )}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Total Cost */}
        <div className="card bg-gradient-to-br from-maroon-500 to-maroon-700 text-white">
          <div className="p-6">
            <div className="flex items-center justify-between mb-2">
              <CurrencyDollarIcon className="h-8 w-8 text-maroon-200" />
              {costs?.trend?.cost > 0 && (
                <span className="flex items-center text-sm">
                  <ArrowTrendingUpIcon className="h-4 w-4 mr-1" />
                  {costs.trend.cost.toFixed(1)}%
                </span>
              )}
            </div>
            <p className="text-sm text-maroon-200">Total Cost</p>
            <p className="text-3xl font-bold mt-1">
              {formatCurrency(costs?.total_cost || 0)}
            </p>
          </div>
        </div>

        {/* Total Workflows */}
        <div className="card">
          <div className="p-6">
            <div className="flex items-center justify-between mb-2">
              <ChartBarIcon className="h-8 w-8 text-blue-500" />
            </div>
            <p className="text-sm text-gray-500">Total Workflows</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {formatNumber(costs?.total_workflows || 0)}
            </p>
          </div>
        </div>

        {/* Total Tokens */}
        <div className="card">
          <div className="p-6">
            <div className="flex items-center justify-between mb-2">
              <BanknotesIcon className="h-8 w-8 text-emerald-500" />
            </div>
            <p className="text-sm text-gray-500">Total Tokens</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {formatNumber(costs?.total_tokens || 0)}
            </p>
          </div>
        </div>

        {/* Average Cost per Workflow */}
        <div className="card">
          <div className="p-6">
            <div className="flex items-center justify-between mb-2">
              <CalendarIcon className="h-8 w-8 text-amber-500" />
            </div>
            <p className="text-sm text-gray-500">Avg Cost/Workflow</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {formatCurrency(costs?.avg_cost_per_workflow || 0)}
            </p>
          </div>
        </div>
      </div>

      {/* Provider Breakdown */}
      <div className="card">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <h2 className="text-lg font-semibold text-gray-900">Cost by Provider</h2>
        </div>
        <div className="p-6">
          <div className="space-y-4">
            {costs?.by_provider && Object.entries(costs.by_provider).map(([provider, data]) => (
              <div key={provider} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="font-semibold text-gray-900">
                      {PRICING[provider]?.name || provider}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {formatNumber(data.workflows)} workflows
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-maroon-600">
                      {formatCurrency(data.cost)}
                    </p>
                    <p className="text-sm text-gray-500">
                      {((data.cost / (costs.total_cost || 1)) * 100).toFixed(1)}% of total
                    </p>
                  </div>
                </div>
                
                {/* Token Usage */}
                <div className="grid grid-cols-2 gap-4 mt-3 pt-3 border-t border-gray-100">
                  <div>
                    <p className="text-xs text-gray-500">Input Tokens</p>
                    <p className="text-sm font-medium text-gray-900">
                      {formatNumber(data.input_tokens)}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {formatCurrency(data.input_cost)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Output Tokens</p>
                    <p className="text-sm font-medium text-gray-900">
                      {formatNumber(data.output_tokens)}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {formatCurrency(data.output_cost)}
                    </p>
                  </div>
                </div>

                {/* Cost Breakdown Bar */}
                <div className="mt-3">
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden flex">
                    <div 
                      className="bg-blue-500 h-full"
                      style={{ width: `${(data.input_cost / data.cost) * 100}%` }}
                    ></div>
                    <div 
                      className="bg-emerald-500 h-full"
                      style={{ width: `${(data.output_cost / data.cost) * 100}%` }}
                    ></div>
                  </div>
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>Input</span>
                    <span>Output</span>
                  </div>
                </div>
              </div>
            ))}
            
            {(!costs?.by_provider || Object.keys(costs.by_provider).length === 0) && (
              <div className="text-center py-8 text-gray-500">
                No cost data available yet. Run some workflows to see analytics.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Workflows */}
      <div className="card">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <h2 className="text-lg font-semibold text-gray-900">Recent Workflows</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Date
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Provider
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Instruction
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Tokens
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Cost
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {costs?.recent_workflows?.map((workflow) => (
                <tr key={workflow.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(workflow.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="px-2 py-1 text-xs font-medium rounded-full bg-maroon-100 text-maroon-700">
                      {workflow.provider}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900 max-w-md truncate">
                    {workflow.instruction}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(workflow.total_tokens)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 text-right">
                    {formatCurrency(workflow.cost)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {(!costs?.recent_workflows || costs.recent_workflows.length === 0) && (
            <div className="text-center py-8 text-gray-500">
              No workflows yet
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Costs;
