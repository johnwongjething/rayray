const environment = process.env.NODE_ENV || 'development';

// Initial config object
const config = {
  development: {
    API_BASE_URL: 'http://localhost:8000', // changed from 5000 to 8000
  },
  production: {
    API_BASE_URL: (process.env.REACT_APP_API_BASE_URL || 'https://rayray.onrender.com').trim(), // ✅ no /api
  },
};

// Clean up the URL to remove trailing slash and ensure proper format
if (config[environment].API_BASE_URL) {
  config[environment].API_BASE_URL = config[environment].API_BASE_URL.replace(/\/$/, '');
}

const currentConfig = config[environment];

export const API_BASE_URL = currentConfig.API_BASE_URL;

export default currentConfig;
