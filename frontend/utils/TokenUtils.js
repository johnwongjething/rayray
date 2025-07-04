import { useNavigate } from 'react-router-dom';

// Utility function to handle API calls with cookie-based auth
export const handleApiCall = async (url, options = {}, navigate) => {
  try {
    const response = await fetch(url, {
      ...options,
      credentials: 'include', // Always send cookies!
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    });

    // Handle 401 Unauthorized
    if (response.status === 401) {
      localStorage.clear();
      if (navigate) {
        navigate('/login');
      }
      throw new Error('Session expired. Please log in again.');
    }

    // Handle other errors
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
    }

    return response;
  } catch (error) {
    // If it's already a handled error, re-throw it
    if (error.message.includes('Session expired') || error.message.includes('Authentication required')) {
      throw error;
    }
    // Handle network errors
    console.error('API call error:', error);
    throw new Error('Network error. Please try again.');
  }
};

// Utility to check if user is logged in by calling a protected backend endpoint
export const checkSession = async () => {
  try {
    const res = await fetch('/api/me', { credentials: 'include' });
    if (!res.ok) return false;
    return true;
  } catch {
    return false;
  }
};