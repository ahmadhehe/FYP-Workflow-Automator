import React, { useRef, useState } from 'react';
import {
  FolderOpenIcon,
  DocumentIcon,
  TrashIcon,
  PlusIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import clsx from 'clsx';
import { useTeacherProfile } from '../hooks/useTeacherProfile';

const FILE_TYPE_LABELS = {
  syllabus: 'Syllabus',
  assignment: 'Assignment',
  lecture: 'Lecture',
  other: 'Other',
};

export function FilesPage() {
  const { courses, courseFiles, uploadFileToCourse, deleteFile, loading } = useTeacherProfile();
  const [expanded, setExpanded] = useState({});
  const [uploading, setUploading] = useState(null);
  const [fileType, setFileType] = useState('other');
  const [pendingCourseId, setPendingCourseId] = useState(null);
  const fileInputRef = useRef(null);

  const toggle = (id) => setExpanded(prev => ({ ...prev, [id]: !prev[id] }));

  const handleAddClick = (courseId) => {
    setPendingCourseId(courseId);
    fileInputRef.current.click();
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file || !pendingCourseId) return;
    setUploading(pendingCourseId);
    try {
      await uploadFileToCourse(pendingCourseId, file, fileType);
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setUploading(null);
      setPendingCourseId(null);
      e.target.value = '';
    }
  };

  const handleDelete = async (fileId, storagePath) => {
    if (!window.confirm('Delete this file?')) return;
    try {
      await deleteFile(fileId, storagePath);
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  const totalFiles = Object.values(courseFiles).reduce((n, arr) => n + arr.length, 0);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <div className="p-3 rounded-xl bg-gradient-to-br from-maroon-600 to-maroon-800">
          <FolderOpenIcon className="h-6 w-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Course Files</h1>
          <p className="text-gray-500">{totalFiles} file{totalFiles !== 1 ? 's' : ''} across {courses.length} course{courses.length !== 1 ? 's' : ''}</p>
        </div>
      </div>

      {/* File type selector */}
      <div className="card p-4 flex items-center gap-3 flex-wrap">
        <span className="text-sm text-gray-600 font-medium">Upload new files as:</span>
        {Object.entries(FILE_TYPE_LABELS).map(([val, label]) => (
          <button
            key={val}
            type="button"
            onClick={() => setFileType(val)}
            className={clsx(
              'text-sm px-3 py-1.5 rounded-full border transition-colors',
              fileType === val
                ? 'bg-maroon-600 text-white border-maroon-600'
                : 'border-gray-300 text-gray-500 hover:border-maroon-400 hover:text-maroon-600'
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <input ref={fileInputRef} type="file" className="hidden" onChange={handleFileChange}
        accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.csv,.xlsx,.zip" />

      {/* Course list */}
      {loading ? (
        <p className="text-gray-400 text-sm text-center py-12">Loading…</p>
      ) : courses.length === 0 ? (
        <div className="card p-8 text-center text-gray-400">
          <FolderOpenIcon className="h-10 w-10 mx-auto mb-3 opacity-40" />
          <p className="font-medium">No courses configured yet.</p>
          <p className="text-sm mt-1">Add courses in Settings → Re-run Setup.</p>
        </div>
      ) : (
        <div className="card divide-y divide-gray-100 overflow-hidden">
          {courses.map(course => {
            const files = courseFiles[course.id] || [];
            const isOpen = expanded[course.id] ?? true;
            const isUploading = uploading === course.id;

            return (
              <div key={course.id}>
                {/* Course row */}
                <div
                  className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-gray-50 select-none"
                  onClick={() => toggle(course.id)}
                >
                  {isOpen
                    ? <ChevronDownIcon className="h-4 w-4 text-gray-400 shrink-0" />
                    : <ChevronRightIcon className="h-4 w-4 text-gray-400 shrink-0" />
                  }
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-gray-800 truncate">{course.name}</p>
                    <p className="text-xs text-gray-400">{course.code} · {course.semester} · {files.length} file{files.length !== 1 ? 's' : ''}</p>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); handleAddClick(course.id); }}
                    disabled={isUploading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-maroon-50 text-maroon-700 hover:bg-maroon-100 text-sm font-medium transition-colors"
                  >
                    {isUploading ? 'Uploading…' : <><PlusIcon className="h-4 w-4" /> Add File</>}
                  </button>
                </div>

                {/* File rows */}
                {isOpen && (
                  <div className="bg-gray-50 border-t border-gray-100">
                    {files.length === 0 ? (
                      <p className="text-sm text-gray-400 italic px-12 py-3">No files uploaded yet.</p>
                    ) : (
                      files.map(file => (
                        <div key={file.id}
                          className="flex items-center gap-3 px-12 py-2.5 hover:bg-gray-100 group transition-colors">
                          <DocumentIcon className="h-4 w-4 text-maroon-400 shrink-0" />
                          <span className="flex-1 text-sm text-gray-700 truncate" title={file.file_name}>
                            {file.file_name}
                          </span>
                          <span className={clsx(
                            'text-xs px-2 py-0.5 rounded-full',
                            file.file_type === 'syllabus' ? 'bg-blue-100 text-blue-700' :
                            file.file_type === 'assignment' ? 'bg-amber-100 text-amber-700' :
                            file.file_type === 'lecture' ? 'bg-purple-100 text-purple-700' :
                            'bg-gray-100 text-gray-500'
                          )}>
                            {FILE_TYPE_LABELS[file.file_type] || file.file_type}
                          </span>
                          <button
                            type="button"
                            onClick={() => handleDelete(file.id, file.file_path)}
                            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:text-red-600 text-gray-400 transition-all"
                            title="Delete"
                          >
                            <TrashIcon className="h-4 w-4" />
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default FilesPage;
