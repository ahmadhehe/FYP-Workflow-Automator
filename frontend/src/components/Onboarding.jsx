import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  GlobeAltIcon,
  AcademicCapIcon,
  FolderOpenIcon,
  Cog6ToothIcon,
  CheckCircleIcon,
  PlusIcon,
  XMarkIcon,
  DocumentPlusIcon,
} from '@heroicons/react/24/outline';
import clsx from 'clsx';
import { supabase } from '../lib/supabase';
import api from '../services/api';

const SAKAI_TABS = [
  'Gradebook', 'Resources', 'Assignments', 'Announcements',
  'Forums', 'Calendar', 'Syllabus', 'Roster',
];

const FILE_TYPES = ['syllabus', 'assignment', 'notes', 'other'];

const STEPS = [
  { id: 1, label: 'LMS Setup', icon: GlobeAltIcon },
  { id: 2, label: 'Courses', icon: AcademicCapIcon },
  { id: 3, label: 'Files', icon: FolderOpenIcon },
  { id: 4, label: 'Tab Prefs', icon: Cog6ToothIcon },
  { id: 5, label: 'Summary', icon: CheckCircleIcon },
];

// ── Progress bar ──────────────────────────────────────────────────────────────

function ProgressBar({ currentStep }) {
  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-2">
        {STEPS.map((step, idx) => {
          const Icon = step.icon;
          const done = currentStep > step.id;
          const active = currentStep === step.id;
          return (
            <React.Fragment key={step.id}>
              <div className="flex flex-col items-center gap-1">
                <div className={clsx(
                  'w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all',
                  done ? 'bg-maroon-600 border-maroon-600 text-white'
                    : active ? 'border-maroon-600 text-maroon-600 bg-white'
                    : 'border-gray-300 text-gray-400 bg-white'
                )}>
                  {done ? <CheckCircleIcon className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
                </div>
                <span className={clsx(
                  'text-xs font-medium',
                  active ? 'text-maroon-700' : done ? 'text-maroon-500' : 'text-gray-400'
                )}>
                  {step.label}
                </span>
              </div>
              {idx < STEPS.length - 1 && (
                <div className={clsx(
                  'flex-1 h-0.5 mx-2 mb-5',
                  currentStep > step.id ? 'bg-maroon-600' : 'bg-gray-200'
                )} />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

// ── Step 1: LMS credentials (FastAPI → lms_teacher_profiles via service_role) ─

function Step1({ onNext }) {
  const [sakaiUrl, setSakaiUrl] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Pre-fill if re-running setup
  useEffect(() => {
    api.getLMSProfile()
      .then(data => {
        if (data?.profile) {
          setSakaiUrl(data.profile.sakai_url || '');
          setUsername(data.profile.username || '');
          setPassword(data.profile.password || '');
        }
      })
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    if (!sakaiUrl.trim() || !username.trim() || !password.trim()) {
      setError('All fields are required.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const profile = await api.saveLMSProfile({
        sakai_url: sakaiUrl.trim(),
        username: username.trim(),
        password: password.trim(),
        onboarding_done: false,
      });
      onNext(profile);
    } catch (err) {
      setError(err.message || 'Failed to save profile.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-bold text-gray-900">Sakai LMS Setup</h2>
        <p className="text-gray-500 mt-1">Enter your institution's Sakai URL and login credentials.</p>
      </div>

      <div>
        <label className="label">Institution Sakai URL</label>
        <div className="relative">
          <GlobeAltIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="url"
            value={sakaiUrl}
            onChange={e => setSakaiUrl(e.target.value)}
            placeholder="https://sakai.institution.edu"
            className="input pl-12"
          />
        </div>
      </div>

      <div>
        <label className="label">Username</label>
        <input
          type="text"
          value={username}
          onChange={e => setUsername(e.target.value)}
          placeholder="Your Sakai username"
          className="input"
        />
      </div>

      <div>
        <label className="label">Password</label>
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          placeholder="Your Sakai password"
          className="input"
        />
        <p className="text-xs text-amber-600 mt-1">
          Stored as plaintext in your private Supabase database (single-user local tool).
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex justify-end pt-2">
        <button onClick={handleSave} disabled={saving} className="btn-primary py-2 px-6">
          {saving ? 'Saving…' : 'Next →'}
        </button>
      </div>
    </div>
  );
}

// ── Step 2: Courses (Supabase JS → existing `courses` table, RLS-scoped) ─────

function Step2({ onNext, onBack }) {
  const [courses, setCourses] = useState([]);
  const [form, setForm] = useState({ name: '', code: '', semester: '' });
  const [adding, setAdding] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Load the teacher's existing courses
  useEffect(() => {
    supabase
      .from('courses')
      .select('id, name, code, semester, sakai_site_id')
      .order('created_at', { ascending: false })
      .then(({ data, error: err }) => {
        if (!err) setCourses(data || []);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleAdd = async () => {
    if (!form.name.trim() || !form.code.trim() || !form.semester.trim()) {
      setError('All fields are required.');
      return;
    }
    setAdding(true);
    setError('');
    try {
      const { data: { user } } = await supabase.auth.getUser();
      const { data, error: err } = await supabase
        .from('courses')
        .insert({ name: form.name.trim(), code: form.code.trim(), semester: form.semester.trim(), created_by: user.id })
        .select()
        .single();
      if (err) throw err;

      // Also register as owner in course_members
      await supabase.from('course_members').insert({
        course_id: data.id,
        user_id: user.id,
        role: 'owner',
      });

      setCourses(prev => [data, ...prev]);
      setForm({ name: '', code: '', semester: '' });
    } catch (err) {
      setError(err.message || 'Failed to add course.');
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (courseId) => {
    const { error: err } = await supabase.from('courses').delete().eq('id', courseId);
    if (err) { setError(err.message); return; }
    setCourses(prev => prev.filter(c => c.id !== courseId));
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-bold text-gray-900">Courses You Teach</h2>
        <p className="text-gray-500 mt-1">These are pulled from your shared database — any changes here appear in the paper-marking system too.</p>
      </div>

      {loading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : courses.length > 0 ? (
        <div className="space-y-2">
          {courses.map(c => (
            <div key={c.id} className="flex items-center justify-between p-3 bg-maroon-50 border border-maroon-200 rounded-lg">
              <div>
                <span className="font-medium text-maroon-900">{c.name}</span>
                <span className="text-sm text-maroon-600 ml-2">({c.code})</span>
                <span className="text-xs text-maroon-500 ml-2">· {c.semester}</span>
              </div>
              <button onClick={() => handleDelete(c.id)} className="p-1 hover:bg-maroon-200 rounded transition-colors">
                <XMarkIcon className="w-4 h-4 text-maroon-700" />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-400 italic">No courses yet — add one below.</p>
      )}

      {/* Add course form */}
      <div className="border border-gray-200 rounded-lg p-4 space-y-3 bg-gray-50">
        <p className="text-sm font-medium text-gray-700">Add a course</p>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="label">Course Name</label>
            <input type="text" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Computer Vision" className="input" />
          </div>
          <div>
            <label className="label">Code</label>
            <input type="text" value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} placeholder="CS401" className="input" />
          </div>
          <div>
            <label className="label">Semester</label>
            <input type="text" value={form.semester} onChange={e => setForm({ ...form, semester: e.target.value })} placeholder="Spring 2026" className="input" />
          </div>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={handleAdd} disabled={adding} className="btn-primary py-2 px-4 flex items-center gap-2">
          <PlusIcon className="h-4 w-4" />
          {adding ? 'Adding…' : 'Add Course'}
        </button>
      </div>

      <div className="flex justify-between pt-2">
        <button onClick={onBack} className="btn-secondary py-2 px-6">← Back</button>
        <button
          onClick={() => onNext(courses)}
          disabled={courses.length === 0}
          className="btn-primary py-2 px-6 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Next →
        </button>
      </div>
    </div>
  );
}

// ── Step 3: Course files (Supabase JS → existing `course_files` table) ────────

function Step3({ courses, onNext, onBack }) {
  const [uploadedFiles, setUploadedFiles] = useState({});
  const [fileTypes, setFileTypes] = useState({});
  const [uploading, setUploading] = useState({});
  const [error, setError] = useState('');

  // Load already-uploaded files for each course
  useEffect(() => {
    if (!courses.length) return;
    const ids = courses.map(c => c.id);
    supabase
      .from('course_files')
      .select('id, course_id, file_name, file_path, file_type, uploaded_at')
      .in('course_id', ids)
      .then(({ data }) => {
        if (!data) return;
        const grouped = {};
        data.forEach(f => {
          if (!grouped[f.course_id]) grouped[f.course_id] = [];
          grouped[f.course_id].push(f);
        });
        setUploadedFiles(grouped);
      });
  }, [courses]);

  const handleFileSelect = async (courseId, e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    const ft = fileTypes[courseId] || 'other';
    setUploading(prev => ({ ...prev, [courseId]: true }));
    setError('');

    for (const file of files) {
      try {
        // Upload to Supabase Storage bucket "course-materials"
        const storagePath = `${courseId}/${Date.now()}_${file.name}`;
        const { error: upErr } = await supabase.storage
          .from('course-materials')
          .upload(storagePath, file);
        if (upErr) throw upErr;

        // Insert row into existing course_files table
        const { data: row, error: dbErr } = await supabase
          .from('course_files')
          .insert({ course_id: courseId, file_name: file.name, file_path: storagePath, file_type: ft })
          .select()
          .single();
        if (dbErr) throw dbErr;

        setUploadedFiles(prev => ({
          ...prev,
          [courseId]: [...(prev[courseId] || []), row],
        }));
      } catch (err) {
        setError(`Failed to upload "${file.name}": ${err.message}`);
      }
    }
    setUploading(prev => ({ ...prev, [courseId]: false }));
    e.target.value = '';
  };

  const handleRemoveFile = async (courseId, fileId, filePath) => {
    await supabase.storage.from('course-materials').remove([filePath]);
    await supabase.from('course_files').delete().eq('id', fileId);
    setUploadedFiles(prev => ({
      ...prev,
      [courseId]: (prev[courseId] || []).filter(f => f.id !== fileId),
    }));
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">Course Materials</h2>
        <p className="text-gray-500 mt-1">Upload files per course. Stored in Supabase Storage, linked in the shared database.</p>
      </div>

      {courses.map(course => (
        <div key={course.id} className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 bg-maroon-50 border-b border-maroon-100">
            <p className="font-semibold text-maroon-800">{course.name} <span className="text-maroon-500 font-normal">({course.code})</span></p>
          </div>
          <div className="p-4 space-y-3">
            {/* Existing files */}
            {(uploadedFiles[course.id] || []).map(f => (
              <div key={f.id} className="flex items-center justify-between p-2 bg-maroon-50 border border-maroon-200 rounded">
                <div className="flex items-center gap-2 min-w-0">
                  <DocumentPlusIcon className="h-4 w-4 text-maroon-600 shrink-0" />
                  <span className="text-sm text-maroon-900 truncate">{f.file_name}</span>
                  <span className="text-xs text-maroon-500 capitalize shrink-0">{f.file_type || 'other'}</span>
                </div>
                <button onClick={() => handleRemoveFile(course.id, f.id, f.file_path)} className="p-1 hover:bg-maroon-200 rounded ml-2">
                  <XMarkIcon className="w-3.5 h-3.5 text-maroon-700" />
                </button>
              </div>
            ))}

            {/* File type selector + upload */}
            <div className="flex gap-3 items-end">
              <div>
                <label className="label">File type</label>
                <select
                  value={fileTypes[course.id] || 'other'}
                  onChange={e => setFileTypes(prev => ({ ...prev, [course.id]: e.target.value }))}
                  className="input py-1.5 text-sm"
                >
                  {FILE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <label className="flex-1 flex items-center justify-center h-10 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-maroon-400 hover:bg-maroon-50 transition-colors">
                <span className="text-xs text-gray-500">
                  {uploading[course.id] ? 'Uploading…' : '+ Upload files'}
                </span>
                <input type="file" multiple className="hidden" onChange={e => handleFileSelect(course.id, e)} disabled={!!uploading[course.id]} />
              </label>
            </div>
          </div>
        </div>
      ))}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex justify-between pt-2">
        <button onClick={onBack} className="btn-secondary py-2 px-6">← Back</button>
        <button onClick={onNext} className="btn-primary py-2 px-6">Next →</button>
      </div>
    </div>
  );
}

// ── Step 4: Tab preferences (Supabase JS → lms_tab_preferences) ──────────────

function Step4({ courses, onNext, onBack, userId }) {
  const [tabPrefs, setTabPrefs] = useState(() => {
    const init = {};
    courses.forEach(c => { init[c.id] = new Set(SAKAI_TABS); });
    return init;
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Load existing prefs
  useEffect(() => {
    if (!courses.length) return;
    const ids = courses.map(c => c.id);
    supabase
      .from('lms_tab_preferences')
      .select('course_id, tab_name, is_enabled')
      .in('course_id', ids)
      .then(({ data }) => {
        if (!data || data.length === 0) return;
        const grouped = {};
        data.forEach(row => {
          if (!grouped[row.course_id]) grouped[row.course_id] = new Set();
          if (row.is_enabled) grouped[row.course_id].add(row.tab_name);
        });
        setTabPrefs(prev => ({ ...prev, ...grouped }));
      });
  }, [courses]);

  const toggle = (courseId, tab) => {
    setTabPrefs(prev => {
      const next = new Set(prev[courseId]);
      if (next.has(tab)) next.delete(tab); else next.add(tab);
      return { ...prev, [courseId]: next };
    });
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      for (const course of courses) {
        // Delete existing prefs then re-insert
        await supabase.from('lms_tab_preferences').delete().eq('course_id', course.id);
        const rows = SAKAI_TABS.map(t => ({
          course_id: course.id,
          tab_name: t,
          is_enabled: tabPrefs[course.id]?.has(t) ?? true,
          user_id: userId,
        }));
        const { error: err } = await supabase.from('lms_tab_preferences').insert(rows);
        if (err) throw err;
      }
      onNext();
    } catch (err) {
      setError(err.message || 'Failed to save tab preferences.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">Sakai Tab Preferences</h2>
        <p className="text-gray-500 mt-1">Choose which Sakai tools to enable per course. All enabled by default.</p>
      </div>

      {courses.map(course => (
        <div key={course.id} className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 bg-maroon-50 border-b border-maroon-100">
            <p className="font-semibold text-maroon-800">{course.name} <span className="text-maroon-500 font-normal">({course.code})</span></p>
          </div>
          <div className="p-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
            {SAKAI_TABS.map(tab => {
              const enabled = tabPrefs[course.id]?.has(tab) ?? true;
              return (
                <button
                  key={tab}
                  type="button"
                  onClick={() => toggle(course.id, tab)}
                  className={clsx(
                    'px-3 py-2 rounded-lg border text-sm font-medium text-left transition-all',
                    enabled ? 'border-maroon-500 bg-maroon-50 text-maroon-700' : 'border-gray-200 bg-white text-gray-400'
                  )}
                >
                  {tab}
                </button>
              );
            })}
          </div>
        </div>
      ))}

      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex justify-between pt-2">
        <button onClick={onBack} className="btn-secondary py-2 px-6">← Back</button>
        <button onClick={handleSave} disabled={saving} className="btn-primary py-2 px-6">
          {saving ? 'Saving…' : 'Next →'}
        </button>
      </div>
    </div>
  );
}

// ── Step 5: Summary ───────────────────────────────────────────────────────────

function Step5({ profile, courses, onBack }) {
  const navigate = useNavigate();
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState('');

  const handleFinish = async () => {
    setFinishing(true);
    setError('');
    try {
      await api.completeOnboarding();
      navigate('/');
    } catch (err) {
      setError(err.message || 'Failed to complete onboarding.');
      setFinishing(false);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-bold text-gray-900">Setup Summary</h2>
        <p className="text-gray-500 mt-1">Review your configuration before finishing.</p>
      </div>

      <div className="space-y-4">
        <div className="p-4 border border-gray-200 rounded-lg bg-gray-50 space-y-1">
          <p className="text-sm font-semibold text-gray-700 mb-2">Sakai LMS</p>
          <p className="text-sm text-gray-600"><span className="font-medium">URL:</span> {profile?.sakai_url}</p>
          <p className="text-sm text-gray-600"><span className="font-medium">Username:</span> {profile?.username}</p>
          <p className="text-xs text-gray-400">Password: ••••••••</p>
        </div>

        <div className="p-4 border border-gray-200 rounded-lg bg-gray-50">
          <p className="text-sm font-semibold text-gray-700 mb-2">Courses ({courses.length})</p>
          {courses.length === 0 ? (
            <p className="text-sm text-gray-400 italic">No courses configured.</p>
          ) : (
            <ul className="space-y-1">
              {courses.map(c => (
                <li key={c.id} className="text-sm text-gray-700">
                  • <span className="font-medium">{c.name}</span> ({c.code}) — {c.semester}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
        <div className="flex items-start gap-3">
          <CheckCircleIcon className="h-5 w-5 text-emerald-600 mt-0.5 shrink-0" />
          <p className="text-sm text-emerald-800">
            Every future automation task will automatically include your Sakai credentials and course list — no need to type them each time. Your courses are shared with the paper-marking system.
          </p>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex justify-between pt-2">
        <button onClick={onBack} className="btn-secondary py-2 px-6">← Back</button>
        <button onClick={handleFinish} disabled={finishing} className="btn-primary py-2 px-6">
          {finishing ? 'Finishing…' : 'Complete Setup ✓'}
        </button>
      </div>
    </div>
  );
}

// ── Main Onboarding component ─────────────────────────────────────────────────

export function Onboarding() {
  const [step, setStep] = useState(1);
  const [profile, setProfile] = useState(null);
  const [courses, setCourses] = useState([]);
  const [userId, setUserId] = useState(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUserId(session?.user?.id ?? null);
    });
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 flex items-start justify-center pt-12 px-4">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-8">
          <div className="inline-flex p-3 rounded-xl bg-gradient-to-br from-maroon-600 to-maroon-800 mb-4">
            <AcademicCapIcon className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900">LMS Setup</h1>
          <p className="text-gray-500 mt-2">Configure your Sakai LMS so the agent can automate tasks on your behalf.</p>
        </div>

        <ProgressBar currentStep={step} />

        <div className="card p-6">
          {step === 1 && (
            <Step1 onNext={savedProfile => { setProfile(savedProfile); setStep(2); }} />
          )}
          {step === 2 && (
            <Step2 onNext={savedCourses => { setCourses(savedCourses); setStep(3); }} onBack={() => setStep(1)} />
          )}
          {step === 3 && (
            <Step3 courses={courses} onNext={() => setStep(4)} onBack={() => setStep(2)} />
          )}
          {step === 4 && (
            <Step4 courses={courses} onNext={() => setStep(5)} onBack={() => setStep(3)} userId={userId} />
          )}
          {step === 5 && (
            <Step5 profile={profile} courses={courses} onBack={() => setStep(4)} />
          )}
        </div>
      </div>
    </div>
  );
}

export default Onboarding;
