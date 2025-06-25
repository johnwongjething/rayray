import { useNavigate } from 'react-router-dom';

// Utility function to handle token validation and API calls
export const handleApiCall = async (url, options = {}, navigate) => {
  const token = localStorage.getItem('token');
  
  // Check if token exists
  if (!token) {
    throw new Error('Authentication required. Please log in again.');
  }

  // Add authorization header if not present
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
    ...options.headers
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers
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

// Hook for token validation
export const useTokenValidation = () => {
  const navigate = useNavigate();
  
  const validateToken = () => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/login');
      return false;
    }
    return true;
  };

  const handleAuthError = (error) => {
    if (error.message.includes('Session expired') || error.message.includes('Authentication required')) {
      localStorage.clear();
      navigate('/login');
    }
  };

  return { validateToken, handleAuthError };
}; 