// Get the current environment
const environment = process.env.NODE_ENV || 'development';

// Initial config object
const config = {
  development: {
    API_BASE_URL: 'http://localhost:5000',
  },
  production: {
    // Use the new custom domain for production
    API_BASE_URL: (process.env.REACT_APP_API_BASE_URL || 'https://terryraylogicticsco.xyz/api').trim(),
  },
};

// Clean up the URL to remove trailing slash and ensure proper format
if (config[environment].API_BASE_URL) {
  config[environment].API_BASE_URL = config[environment].API_BASE_URL.replace(/\/$/, '');
}

const currentConfig = config[environment];

export const API_BASE_URL = currentConfig.API_BASE_URL;

export default currentConfig;
