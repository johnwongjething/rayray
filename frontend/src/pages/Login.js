import React, { useState } from 'react';
import { Container, Typography, Box, TextField, Button, Snackbar, Alert } from '@mui/material';
import { useNavigate, Link } from 'react-router-dom';
import { API_BASE_URL } from '../config';

function Login({ t = x => x }) {
  const [formData, setFormData] = useState({ username: '', password: '' });
  const [error, setError] = useState('');
  const navigate = useNavigate();

  // Simple input validation
  const validateInput = () => {
    if (!formData.username || !formData.password) {
      setError('Username and password are required.');
      return false;
    }
    // Add more validation as needed (e.g., regex for username)
    return true;
  };

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateInput()) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include', // Important: allow cookies to be set
        body: JSON.stringify(formData)
      });
      const data = await res.json();
      if (res.ok) {
        // No longer store any sensitive data in localStorage
        // Optionally, fetch user info from /api/me if needed
        navigate('/dashboard');
      } else {
        setError(data.error || t('loginFailed') || 'Login failed');
      }
    } catch (err) {
      setError(t('loginFailed') || 'Login failed');
    }
  };

  return (
    <Container maxWidth="sm">
      <Box sx={{ my: 4, p: { xs: 2, sm: 4 }, boxShadow: 2, borderRadius: 2 }}>
        <Typography variant="h4" align="center" gutterBottom>
          {t('login')}
        </Typography>
        <form onSubmit={handleSubmit} autoComplete="off">
          <TextField
            fullWidth
            label={t('username')}
            name="username"
            value={formData.username}
            onChange={handleChange}
            margin="normal"
            required
          />
          <TextField
            fullWidth
            label={t('password')}
            name="password"
            type="password"
            value={formData.password}
            onChange={handleChange}
            margin="normal"
            required
          />
          <Button type="submit" variant="contained" color="primary" fullWidth sx={{ mt: 2 }}>
            {t('login')}
          </Button>
        </form>
        <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 1 }}>
          <Link to="/forgot-password" style={{ textDecoration: 'none', color: '#1976d2' }}>
            {t('forgotPassword')}
          </Link>
          <Link to="/forgot-username" style={{ textDecoration: 'none', color: '#1976d2' }}>
            {t('forgotUsername')}
          </Link>
        </Box>
        <Snackbar
          open={!!error}
          autoHideDuration={6000}
          onClose={() => setError('')}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert onClose={() => setError('')} severity="error" sx={{ width: '100%' }}>
            {error}
          </Alert>
        </Snackbar>
      </Box>
    </Container>
  );
}

export default Login;