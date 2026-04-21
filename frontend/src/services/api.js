import { supabase } from '../lib/supabase';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

async function getAuthHeader() {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {};
}

class ApiService {
  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const authHeader = await getAuthHeader();
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...authHeader,
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Request failed');
      }

      return data;
    } catch (error) {
      console.error('API Error:', error);
      throw error;
    }
  }

  // Browser control
  async startBrowser(provider = 'openai', headless = false) {
    return this.request(`/start?provider=${provider}&headless=${headless}`, {
      method: 'POST',
    });
  }

  async stopBrowser() {
    return this.request('/stop', { method: 'POST' });
  }

  async respondToIntervention(response = '') {
    return this.request('/intervention/respond', {
      method: 'POST',
      body: JSON.stringify({ response }),
    });
  }

  async getStatus() {
    return this.request('/status');
  }

  // Task execution
  async runTask(instruction, initialUrl = null, provider = null, files = null) {
    return this.request('/task', {
      method: 'POST',
      body: JSON.stringify({
        instruction,
        initial_url: initialUrl,
        provider,
        files: files && files.length > 0 ? files : null,
      }),
    });
  }

  // File upload
  async uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    const url = `${API_BASE}/upload-file`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'File upload failed');
      }

      return data;
    } catch (error) {
      console.error('File Upload Error:', error);
      throw error;
    }
  }

  // Flow history
  async getFlows(limit = 20, offset = 0) {
    return this.request(`/flows?limit=${limit}&offset=${offset}`);
  }

  async getFlow(flowId) {
    return this.request(`/flows/${flowId}`);
  }

  async updateFlow(flowId, instruction) {
    return this.request(`/flows/${flowId}`, {
      method: 'PUT',
      body: JSON.stringify({ instruction }),
    });
  }

  async deleteFlow(flowId) {
    return this.request(`/flows/${flowId}`, { method: 'DELETE' });
  }

  async rerunFlow(flowId) {
    return this.request(`/flows/${flowId}/rerun`, { method: 'POST' });
  }

  async clearFlows() {
    return this.request('/flows', { method: 'DELETE' });
  }

  // Profile management
  async startProfileBrowser(url = null) {
    const endpoint = url ? `/profile/start?url=${encodeURIComponent(url)}` : '/profile/start';
    return this.request(endpoint, { method: 'POST' });
  }

  async stopProfileBrowser() {
    return this.request('/profile/stop', { method: 'POST' });
  }

  async getProfileStatus() {
    return this.request('/profile/status');
  }

  async clearProfile() {
    return this.request('/profile/clear', { method: 'DELETE' });
  }

  // Costs analytics
  async getCosts(timeRange = 'all') {
    return this.request(`/costs?time_range=${timeRange}`);
  }

  // ── LMS Onboarding ──────────────────────────────────────────────────────────

  async getOnboardingStatus() {
    return this.request('/onboarding/status');
  }

  async getLMSProfile() {
    return this.request('/profile/lms');
  }

  async saveLMSProfile(data) {
    return this.request('/profile/lms', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async completeOnboarding() {
    return this.request('/profile/lms/complete-onboarding', { method: 'POST' });
  }

  async addCourse(data) {
    return this.request('/profile/lms/courses', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateCourse(courseId, data) {
    return this.request(`/profile/lms/courses/${courseId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteCourse(courseId) {
    return this.request(`/profile/lms/courses/${courseId}`, { method: 'DELETE' });
  }

  async uploadCourseFile(courseId, file, fileType = 'other') {
    const formData = new FormData();
    formData.append('file', file);
    const url = `${API_BASE}/profile/lms/courses/${courseId}/files?file_type=${fileType}`;
    const response = await fetch(url, { method: 'POST', body: formData });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Upload failed');
    return data;
  }

  async saveTabPreferences(courseId, enabledTabs) {
    return this.request('/profile/lms/tab-preferences', {
      method: 'POST',
      body: JSON.stringify({ course_id: courseId, enabled_tabs: enabledTabs }),
    });
  }

  // Voice transcription
  async transcribeAudio(audioBlob) {
    const formData = new FormData();
    formData.append('file', audioBlob, 'recording.webm');

    const url = `${API_BASE}/transcribe`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Transcription failed');
      }

      return data;
    } catch (error) {
      console.error('Transcription Error:', error);
      throw error;
    }
  }
}

export const api = new ApiService();
export default api;
