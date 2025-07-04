import React, { useState } from 'react';
import {
  Container,
  Typography,
  Box,
  TextField,
  Button,
  MenuItem,
  Select,
  InputLabel,
  FormControl,
  Snackbar,
  Alert
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '../config';

function Register({ t = x => x }) {
  const initialFormData = {
    username: '',
    password: '',
    role: 'customer',
    customer_name: '',
    customer_email: '',
    customer_phone: '',
    confirm_email: '',
  };
  const [formData, setFormData] = useState(initialFormData);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const navigate = useNavigate();

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Input validation
    if (!formData.username || !formData.password || !formData.customer_email) {
      setSnackbar({ open: true, message: t('allFieldsRequired') || 'All required fields must be filled.', severity: 'error' });
      return;
    }
    if (formData.confirm_email && formData.customer_email !== formData.confirm_email) {
      setSnackbar({ open: true, message: t('emailMismatch') || 'Email addresses do not match', severity: 'error' });
      return;
    }
    // Password strength check
    if (formData.password.length < 8 ||
        !/[A-Z]/.test(formData.password) ||
        !/[a-z]/.test(formData.password) ||
        !/[0-9]/.test(formData.password) ||
        !/[!@#$%^&*(),.?":{}|<>]/.test(formData.password)) {
      setSnackbar({ open: true, message: t('passwordRequirement') || 'Password must be at least 8 characters, include an uppercase letter, a lowercase letter, a number, and a special character.', severity: 'error' });
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(formData)
      });
      const data = await res.json();
      if (res.ok) {
        setSnackbar({ open: true, message: data.message, severity: 'success' });
        await fetch(`${API_BASE_URL}/api/notify_new_user`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            username: formData.username,
            email: formData.customer_email,
            role: formData.role,
          }),
        });
        setTimeout(() => navigate('/login'), 2000);
      } else {
        setSnackbar({ open: true, message: data.error, severity: 'error' });
      }
    } catch (err) {
      setSnackbar({ open: true, message: t('registrationFailed') || 'Registration failed', severity: 'error' });
    }
  };

  return (
    <Container maxWidth="sm">
      <Box sx={{ my: 4, p: { xs: 2, sm: 4 }, boxShadow: 2, borderRadius: 2 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          {t('register')}
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
          <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
            {t('passwordRequirement') ||
              'Password must be at least 8 characters, include an uppercase letter, a lowercase letter, a number, and a special character.'}
          </Typography>
          <FormControl fullWidth margin="normal" required>
            <InputLabel id="role-label">{t('role')}</InputLabel>
            <Select
              labelId="role-label"
              id="role"
              name="role"
              value={formData.role}
              label={t('role')}
              onChange={handleChange}
            >
              <MenuItem value="customer">{t('customer')}</MenuItem>
              <MenuItem value="staff">{t('staff')}</MenuItem>
            </Select>
          </FormControl>
          <TextField
            fullWidth
            label={t('customerName')}
            name="customer_name"
            value={formData.customer_name}
            onChange={handleChange}
            margin="normal"
            required
          />
          <TextField
            fullWidth
            label={t('email')}
            name="customer_email"
            type="email"
            value={formData.customer_email}
            onChange={handleChange}
            margin="normal"
            required
          />
          <TextField
            fullWidth
            label={t('confirmEmail') || 'Confirm Email Address'}
            name="confirm_email"
            type="email"
            value={formData.confirm_email}
            onChange={handleChange}
            margin="normal"
            required
          />
          <TextField
            fullWidth
            label={t('phoneNumber')}
            name="customer_phone"
            value={formData.customer_phone}
            onChange={handleChange}
            margin="normal"
            required
          />
          <Button type="submit" variant="contained" color="primary" sx={{ mt: 2 }} fullWidth>
            {t('register')}
          </Button>
        </form>
        <Snackbar
          open={snackbar.open}
          autoHideDuration={4000}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert onClose={() => setSnackbar({ ...snackbar, open: false })} severity={snackbar.severity} sx={{ width: '100%' }}>
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Box>
    </Container>
  );
}

export default Register;