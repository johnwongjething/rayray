import React, { useState } from 'react';
import { Container, Typography, TextField, Button, Snackbar, Alert, Box } from '@mui/material';
import { API_BASE_URL } from '../config';

function ForgotUsername({ t = x => x }) {
  const [email, setEmail] = useState('');
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE_URL}/api/request_username`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (res.ok) {
        setSnackbar({ open: true, message: t('usernameSent'), severity: 'success' });
      } else {
        setSnackbar({ open: true, message: data.error || t('noUserFound'), severity: 'error' });
      }
    } catch (err) {
      setSnackbar({ open: true, message: t('emailRequired'), severity: 'error' });
    }
  };

  return (
    <Container maxWidth="sm">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" gutterBottom>{t('forgotUsernameTitle')}</Typography>
        <Typography variant="body1" sx={{ mb: 2 }}>{t('forgotUsernameInstruction')}</Typography>
        <form onSubmit={handleSubmit}>
          <TextField
            fullWidth
            label={t('customerEmail')}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            margin="normal"
          />
          <Button type="submit" variant="contained" color="primary" fullWidth sx={{ mt: 2 }}>
            {t('submit')}
          </Button>
        </form>
        <Snackbar
          open={snackbar.open}
          autoHideDuration={5000}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert onClose={() => setSnackbar({ ...snackbar, open: false })} severity={snackbar.severity}>
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Box>
    </Container>
  );
}

export default ForgotUsername;
