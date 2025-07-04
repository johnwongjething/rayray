import React, { useState, useEffect } from 'react';
import { Container, Typography, Box, TextField, Button, Snackbar, Alert } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '../config';

function ResetPassword({ t = x => x }) {
  const { token } = useParams();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const navigate = useNavigate();

  // Debug logging
  useEffect(() => {
    console.log('ResetPassword component loaded');
    console.log('Token from URL:', token);
    if (!token) {
      setSnackbar({ open: true, message: 'No reset token found in URL', severity: 'error' });
    }
  }, [token]);

  const validatePassword = (password) => {
    if (password.length < 8) {
      return 'Password must be at least 8 characters long';
    }
    if (!/[A-Z]/.test(password)) {
      return 'Password must contain at least one uppercase letter';
    }
    if (!/[a-z]/.test(password)) {
      return 'Password must contain at least one lowercase letter';
    }
    if (!/[0-9]/.test(password)) {
      return 'Password must contain at least one number';
    }
    if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
      return 'Password must contain at least one special character';
    }
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!token) {
      setSnackbar({ open: true, message: 'No reset token found', severity: 'error' });
      return;
    }
    
    // Validate passwords match
    if (password !== confirmPassword) {
      setSnackbar({ open: true, message: 'Passwords do not match', severity: 'error' });
      return;
    }

    // Validate password strength
    const passwordError = validatePassword(password);
    if (passwordError) {
      setSnackbar({ open: true, message: passwordError, severity: 'error' });
      return;
    }

    setLoading(true);
    try {
      console.log('Sending reset request with token:', token);
      const res = await fetch(`${API_BASE_URL}/api/reset_password/${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      });
      const data = await res.json();
      console.log('Reset response:', res.status, data);
      if (res.ok) {
        setSnackbar({ open: true, message: data.message || 'Password has been reset successfully', severity: 'success' });
        // Clear form
        setPassword('');
        setConfirmPassword('');
        // Redirect to login after 2 seconds
        setTimeout(() => navigate('/login'), 2000);
      } else {
        setSnackbar({ open: true, message: data.error || 'Password reset failed', severity: 'error' });
      }
    } catch (err) {
      console.error('Reset password error:', err);
      setSnackbar({ open: true, message: 'Password reset failed. Please try again.', severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="sm">
      <Box sx={{ my: 4, textAlign: 'center' }}>
        <Typography variant="h3" component="h1" gutterBottom>
          {t('resetPassword') || 'Reset Password'}
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
          Enter your new password below.
        </Typography>
        
        {!token && (
          <Alert severity="error" sx={{ mb: 2 }}>
            No reset token found in URL. Please check your email link.
          </Alert>
        )}
        
        <form onSubmit={handleSubmit}>
          <TextField
            fullWidth
            label="New Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            margin="normal"
            required
            disabled={loading || !token}
            helperText="Password must be at least 8 characters with uppercase, lowercase, number, and special character"
          />
          <TextField
            fullWidth
            label="Confirm New Password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            margin="normal"
            required
            disabled={loading || !token}
            error={confirmPassword && password !== confirmPassword}
            helperText={confirmPassword && password !== confirmPassword ? "Passwords do not match" : ""}
          />
          <Button 
            type="submit" 
            variant="contained" 
            color="primary" 
            fullWidth
            sx={{ mt: 2, mb: 2 }}
            disabled={loading || !password || !confirmPassword || !token}
          >
            {loading ? 'Resetting Password...' : 'Reset Password'}
          </Button>
        </form>
        
        <Snackbar
          open={snackbar.open}
          autoHideDuration={6000}
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

export default ResetPassword;