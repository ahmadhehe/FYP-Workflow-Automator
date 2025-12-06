import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { 
  HomeIcon, 
  ClockIcon, 
  Cog6ToothIcon,
  CommandLineIcon,
  SignalIcon,
  SignalSlashIcon
} from '@heroicons/react/24/outline';
import clsx from 'clsx';

const navigation = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  { name: 'History', href: '/history', icon: ClockIcon },
  { name: 'Settings', href: '/settings', icon: Cog6ToothIcon },
];

export function Sidebar({ isConnected, browserRunning }) {
  const location = useLocation();

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 bg-dark-900/80 backdrop-blur-xl border-r border-dark-700/50">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 px-6 border-b border-dark-700/50">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary-500 to-cyan-500 shadow-glow">
          <CommandLineIcon className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-dark-100">Browser Agent</h1>
          <p className="text-xs text-dark-500">AI Automation</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-1 p-4">
        {navigation.map((item) => {
          const isActive = location.pathname === item.href;
          return (
            <Link
              key={item.name}
              to={item.href}
              className={clsx(
                'flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200',
                isActive 
                  ? 'bg-primary-600/20 text-primary-400 border border-primary-500/30' 
                  : 'text-dark-400 hover:text-dark-100 hover:bg-dark-800'
              )}
            >
              <item.icon className="h-5 w-5" />
              <span className="font-medium">{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* Status indicators */}
      <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-dark-700/50">
        <div className="space-y-3">
          {/* WebSocket Status */}
          <div className="flex items-center justify-between px-2">
            <span className="text-xs text-dark-500">WebSocket</span>
            <div className="flex items-center gap-2">
              {isConnected ? (
                <>
                  <SignalIcon className="h-4 w-4 text-emerald-400" />
                  <span className="text-xs text-emerald-400">Connected</span>
                </>
              ) : (
                <>
                  <SignalSlashIcon className="h-4 w-4 text-red-400" />
                  <span className="text-xs text-red-400">Disconnected</span>
                </>
              )}
            </div>
          </div>

          {/* Browser Status */}
          <div className="flex items-center justify-between px-2">
            <span className="text-xs text-dark-500">Browser</span>
            <div className="flex items-center gap-2">
              <span className={clsx(
                'h-2 w-2 rounded-full',
                browserRunning ? 'bg-emerald-400 animate-pulse' : 'bg-dark-600'
              )} />
              <span className={clsx(
                'text-xs',
                browserRunning ? 'text-emerald-400' : 'text-dark-500'
              )}>
                {browserRunning ? 'Running' : 'Stopped'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
