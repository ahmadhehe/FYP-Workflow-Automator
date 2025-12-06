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
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 bg-maroon-500 shadow-xl">
      {/* Logo */}
      <div className="flex h-20 items-center gap-3 px-6 border-b border-maroon-400/30">
        <img src="/logo.jpg" alt="Logo" className="h-12 w-12 rounded-lg object-cover" />
        <div>
          <h1 className="text-lg font-semibold text-white">Browser Agent</h1>
          <p className="text-xs text-maroon-200">AI Automation</p>
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
                  ? 'bg-white text-maroon-600 shadow-md' 
                  : 'text-maroon-100 hover:text-white hover:bg-maroon-400/50'
              )}
            >
              <item.icon className="h-5 w-5" />
              <span className="font-medium">{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* Status indicators */}
      <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-maroon-400/30">
        <div className="space-y-3">
          {/* WebSocket Status */}
          <div className="flex items-center justify-between px-2">
            <span className="text-xs text-maroon-200">WebSocket</span>
            <div className="flex items-center gap-2">
              {isConnected ? (
                <>
                  <SignalIcon className="h-4 w-4 text-emerald-300" />
                  <span className="text-xs text-emerald-300">Connected</span>
                </>
              ) : (
                <>
                  <SignalSlashIcon className="h-4 w-4 text-red-300" />
                  <span className="text-xs text-red-300">Disconnected</span>
                </>
              )}
            </div>
          </div>

          {/* Browser Status */}
          <div className="flex items-center justify-between px-2">
            <span className="text-xs text-maroon-200">Browser</span>
            <div className="flex items-center gap-2">
              <span className={clsx(
                'h-2 w-2 rounded-full',
                browserRunning ? 'bg-emerald-300 animate-pulse' : 'bg-maroon-300'
              )} />
              <span className={clsx(
                'text-xs',
                browserRunning ? 'text-emerald-300' : 'text-maroon-200'
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
