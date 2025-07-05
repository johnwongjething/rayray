console.log('Environment Variables Check:');
console.log('REACT_APP_API_BASE_URL:', process.env.REACT_APP_API_BASE_URL);
console.log('URL Length:', process.env.REACT_APP_API_BASE_URL?.length);
console.log('URL Encoded:', encodeURIComponent(process.env.REACT_APP_API_BASE_URL));

// Check for trailing whitespace
const trimmedUrl = process.env.REACT_APP_API_BASE_URL?.trim();
console.log('Trimmed URL:', trimmedUrl);
console.log('Has Trailing Space:', process.env.REACT_APP_API_BASE_URL !== trimmedUrl);
