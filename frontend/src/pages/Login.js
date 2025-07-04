import React, { useState } from 'react';
import { Container, Typography, Box, TextField, Button, Snackbar, Alert } from '@mui/material';
import { useNavigate, Link } from 'react-router-dom';
import { API_BASE_URL } from '../config';

function Login({ t = x => x }) {
  const [formData, setFormData] = useState({ username: '', password: '' });
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE_URL}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include', // Important: send cookies and receive JWT in cookie
        body: JSON.stringify(formData)
      });
      const data = await res.json();
      if (res.ok) {
        // Optionally store in localStorage for role/username, but JWT is in cookie
        localStorage.setItem('role', data.role);
        localStorage.setItem('username', data.username);
        if (data.customer_name) localStorage.setItem('customer_name', data.customer_name);
        if (data.customer_email) localStorage.setItem('customer_email', data.customer_email);
        if (data.customer_phone) localStorage.setItem('customer_phone', data.customer_phone);
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
        <form onSubmit={handleSubmit}>
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