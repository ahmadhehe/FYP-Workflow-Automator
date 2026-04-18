import { useState, useEffect, useCallback } from 'react';
import { supabase } from '../lib/supabase';
import api from '../services/api';

export function useTeacherProfile() {
  const [profile, setProfile] = useState(null);
  const [courses, setCourses] = useState([]);
  const [courseFiles, setCourseFiles] = useState({}); // { courseId: [file, ...] }
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data: coursesData, error: err } = await supabase
        .from('courses')
        .select('id, name, code, semester, sakai_site_id')
        .order('created_at', { ascending: false });

      if (err) throw err;
      const loadedCourses = coursesData || [];
      setCourses(loadedCourses);

      // Fetch files for all courses in parallel
      const fileResults = await Promise.all(
        loadedCourses.map(async (course) => {
          const { data } = await supabase
            .from('course_files')
            .select('id, file_name, file_path, file_type, uploaded_at')
            .eq('course_id', course.id)
            .order('uploaded_at', { ascending: false });
          return { courseId: course.id, files: data || [] };
        })
      );
      const filesMap = {};
      fileResults.forEach(({ courseId, files }) => { filesMap[courseId] = files; });
      setCourseFiles(filesMap);

      // LMS profile (Sakai credentials) from FastAPI
      try {
        const json = await api.getLMSProfile();
        setProfile(json.profile);
      } catch {
        // No profile yet
      }
    } catch (err) {
      setError(err.message);
      setCourses([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const uploadFileToCourse = useCallback(async (courseId, file, fileType = 'other') => {
    await api.uploadCourseFile(courseId, file, fileType);
    await fetchProfile();
  }, [fetchProfile]);

  const deleteFile = useCallback(async (fileId, storagePath) => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    await supabase.storage.from('course-materials').remove([storagePath]);
    await supabase.from('course_files').delete().eq('id', fileId);
    await fetchProfile();
  }, [fetchProfile]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  return { profile, courses, courseFiles, loading, error, refetch: fetchProfile, uploadFileToCourse, deleteFile };
}

export default useTeacherProfile;
