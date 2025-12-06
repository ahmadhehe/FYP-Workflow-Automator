const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class ApiService {
  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
      headers: {
        'Content-Type': 'application/json',
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

  async getStatus() {
    return this.request('/status');
  }

  // Task execution
  async runTask(instruction, initialUrl = null, provider = null) {
    return this.request('/task', {
      method: 'POST',
      body: JSON.stringify({
        instruction,
        initial_url: initialUrl,
        provider,
      }),
    });
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
}

export const api = new ApiService();
export default api;
