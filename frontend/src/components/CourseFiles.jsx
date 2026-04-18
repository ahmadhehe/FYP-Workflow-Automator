import React, { useState, useRef } from 'react';
import {
  FolderOpenIcon,
  DocumentIcon,
  TrashIcon,
  PlusIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import clsx from 'clsx';

const FILE_TYPE_LABELS = {
  syllabus: 'Syllabus',
  assignment: 'Assignment',
  lecture: 'Lecture',
  other: 'Other',
};

export function CourseFiles({ courses, courseFiles, onUpload, onDelete }) {
  const [expanded, setExpanded] = useState({});
  const [uploading, setUploading] = useState(null); // courseId being uploaded to
  const fileInputRef = useRef(null);
  const [pendingCourseId, setPendingCourseId] = useState(null);
  const [fileType, setFileType] = useState('other');

  const toggle = (courseId) =>
    setExpanded(prev => ({ ...prev, [courseId]: !prev[courseId] }));

  const handleAddClick = (courseId) => {
    setPendingCourseId(courseId);
    fileInputRef.current.click();
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file || !pendingCourseId) return;
    setUploading(pendingCourseId);
    try {
      await onUpload(pendingCourseId, file, fileType);
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setUploading(null);
      setPendingCourseId(null);
      e.target.value = '';
    }
  };

  const allFiles = courses.flatMap(c =>
    (courseFiles[c.id] || []).map(f => ({ ...f, courseName: c.name }))
  );

  return (
    <div className="card overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center gap-2">
        <FolderOpenIcon className="h-4 w-4 text-maroon-600" />
        <h3 className="text-sm font-semibold text-gray-800">Course Files</h3>
        <span className="ml-auto text-xs text-gray-400">{allFiles.length} file{allFiles.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        onChange={handleFileChange}
        accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.csv,.xlsx,.zip"
      />

      {/* File type selector shown when pendingCourseId is set — shown inline above input click */}
      <div className="px-4 py-2 border-b border-gray-100 flex items-center gap-2">
        <span className="text-xs text-gray-500">Upload as:</span>
        {Object.entries(FILE_TYPE_LABELS).map(([val, label]) => (
          <button
            key={val}
            type="button"
            onClick={() => setFileType(val)}
            className={clsx(
              'text-xs px-2 py-1 rounded-full border transition-colors',
              fileType === val
                ? 'bg-maroon-600 text-white border-maroon-600'
                : 'border-gray-300 text-gray-500 hover:border-maroon-400'
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="divide-y divide-gray-100 max-h-[420px] overflow-y-auto">
        {courses.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-6">No courses configured yet.</p>
        )}

        {courses.map(course => {
          const files = courseFiles[course.id] || [];
          const isOpen = expanded[course.id];
          const isUploading = uploading === course.id;

          return (
            <div key={course.id}>
              {/* Course header row */}
              <div className="flex items-center gap-2 px-4 py-2 hover:bg-gray-50 cursor-pointer select-none"
                onClick={() => toggle(course.id)}>
                {isOpen
                  ? <ChevronDownIcon className="h-3.5 w-3.5 text-gray-400 shrink-0" />
                  : <ChevronRightIcon className="h-3.5 w-3.5 text-gray-400 shrink-0" />
                }
                <span className="text-sm font-medium text-gray-700 truncate flex-1">{course.name}</span>
                <span className="text-xs text-gray-400">{files.length}</span>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); handleAddClick(course.id); }}
                  disabled={isUploading}
                  className="p-1 rounded hover:bg-maroon-100 text-maroon-600 transition-colors"
                  title="Upload file to this course"
                >
                  {isUploading
                    ? <span className="text-xs">…</span>
                    : <PlusIcon className="h-3.5 w-3.5" />
                  }
                </button>
              </div>

              {/* File list */}
              {isOpen && (
                <div className="pl-8 pr-4 pb-2 space-y-1">
                  {files.length === 0 && (
                    <p className="text-xs text-gray-400 italic py-1">No files uploaded.</p>
                  )}
                  {files.map(file => (
                    <div key={file.id}
                      className="flex items-center gap-2 py-1 group">
                      <DocumentIcon className="h-3.5 w-3.5 text-gray-400 shrink-0" />
                      <span className="text-xs text-gray-700 truncate flex-1" title={file.file_name}>
                        {file.file_name}
                      </span>
                      <span className="text-xs text-gray-400 shrink-0">
                        {FILE_TYPE_LABELS[file.file_type] || file.file_type}
                      </span>
                      <button
                        type="button"
                        onClick={() => onDelete(file.id, file.file_path)}
                        className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:text-red-600 text-gray-400 transition-all"
                        title="Delete file"
                      >
                        <TrashIcon className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default CourseFiles;
