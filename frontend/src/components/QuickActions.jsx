import React from 'react';
import {
  CloudArrowUpIcon,
  MegaphoneIcon,
  CalendarDaysIcon,
  FolderOpenIcon,
} from '@heroicons/react/24/outline';
import clsx from 'clsx';

const QUICK_ACTIONS = [
  {
    id: 'upload-assignment',
    label: 'Upload Assignment',
    icon: CloudArrowUpIcon,
    description: 'Post a new assignment to Sakai',
    buildPrompt: (courses) => {
      const courseList = courses.map(c => `${c.name} (${c.code})`).join(', ');
      return `Go to my Sakai LMS and upload a new assignment. My courses are: ${courseList}. Ask me which course and what the assignment details should be.`;
    },
  },
  {
    id: 'post-announcement',
    label: 'Post Announcement',
    icon: MegaphoneIcon,
    description: 'Send an announcement to students',
    buildPrompt: (courses) => {
      const courseList = courses.map(c => `${c.name} (${c.code})`).join(', ');
      return `Go to my Sakai LMS and post an announcement. My courses are: ${courseList}. Ask me which course and what the announcement should say.`;
    },
  },
  {
    id: 'setup-semester',
    label: 'Setup New Semester',
    icon: CalendarDaysIcon,
    description: 'Configure all Sakai tools for a new term',
    buildPrompt: (courses) => {
      const courseList = courses.map(c => `${c.name} (${c.code})`).join(', ');
      return `Go to my Sakai LMS and set up a new semester. Enable the required tabs and tools for each of my courses: ${courseList}.`;
    },
  },
  {
    id: 'upload-course-files',
    label: 'Upload Course Files',
    icon: FolderOpenIcon,
    description: 'Upload saved materials to LMS Resources',
    buildPrompt: (courses) => {
      const courseList = courses.map(c => `${c.name} (${c.code})`).join(', ');
      return `Go to my Sakai LMS Resources section and upload course materials for my courses: ${courseList}. Use the files I have previously configured.`;
    },
  },
];

export function QuickActions({ courses, onInjectPrompt, isRunning }) {
  return (
    <div className="card overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 bg-gradient-to-r from-maroon-600 to-maroon-700">
        <h3 className="text-sm font-semibold text-white">Quick Actions</h3>
        <p className="text-xs text-maroon-200 mt-0.5">LMS automation shortcuts</p>
      </div>
      <div className="p-3 space-y-2">
        {QUICK_ACTIONS.map((action) => {
          const Icon = action.icon;
          const disabled = isRunning || !courses.length;
          return (
            <button
              key={action.id}
              disabled={disabled}
              onClick={() => onInjectPrompt(action.buildPrompt(courses))}
              className={clsx(
                'w-full text-left p-3 rounded-lg border transition-all duration-200',
                disabled
                  ? 'border-gray-200 bg-gray-50 opacity-50 cursor-not-allowed'
                  : 'border-gray-200 hover:border-maroon-400 hover:bg-maroon-50 cursor-pointer'
              )}
            >
              <div className="flex items-start gap-3">
                <Icon className="h-5 w-5 text-maroon-600 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-gray-800">{action.label}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{action.description}</p>
                </div>
              </div>
            </button>
          );
        })}

        {!courses.length && (
          <p className="text-xs text-gray-400 text-center py-2">
            Complete LMS setup to enable quick actions
          </p>
        )}
      </div>
    </div>
  );
}

export default QuickActions;
