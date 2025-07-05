import React, { useState } from 'react';
import { Container, Typography, Box, TextField, Button, Snackbar, Alert } from '@mui/material';
import { API_BASE_URL } from '../config';

function Contact({ t = x => x }) {
  const initialFormData = { name: '', email: '', message: '' };
  const [formData, setFormData] = useState(initialFormData);
  const [submitted, setSubmitted] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE_URL}/api/contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      const data = await res.json();
      if (res.ok) {
        setSnackbar({ open: true, message: data.message, severity: 'success' });
        setFormData(initialFormData);
        setSubmitted(true);
      } else {
        setSnackbar({ open: true, message: data.error || t('failed'), severity: 'error' });
      }
    } catch (err) {
      setSnackbar({ open: true, message: t('failed'), severity: 'error' });
    }
  };

  return (
    <Box
      sx={{
        backgroundImage: 'url(/assets/contact.jpg)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        minHeight: '100vh',
        py: { xs: 4, sm: 8 },
        px: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}
    >
      <Container
        maxWidth="sm"
        sx={{
          background: 'rgba(255,255,255,0.97)',
          borderRadius: 2,
          py: { xs: 3, sm: 4 },
          px: { xs: 2, sm: 4 },
          boxShadow: 3,
        }}
      >
        <Typography variant="h4" component="h1" gutterBottom align="center">
          {t('contact')}
        </Typography>
        <Typography variant="h6" align="center" gutterBottom>
          Solex Logistic Company<br />
          9/85 Tram Rd Doncaster<br />
          +852 65381629
        </Typography>
        <Typography align="center" sx={{ mb: 2 }}>
          {t('contactInstruction')}
        </Typography>
        {submitted ? (
          <Typography color="success.main" align="center" sx={{ mt: 2 }}>
            {t('contactSuccessProfessional')}
          </Typography>
        ) : (
          <form onSubmit={handleSubmit}>
            <TextField
              fullWidth
              label={t('name')}
              name="name"
              value={formData.name}
              onChange={handleChange}
              margin="normal"
              required
            />
            <TextField
              fullWidth
              label={t('email')}
              name="email"
              type="email"
              value={formData.email}
              onChange={handleChange}
              margin="normal"
              required
            />
            <TextField
              fullWidth
              label={t('message')}
              name="message"
              multiline
              rows={4}
              value={formData.message}
              onChange={handleChange}
              margin="normal"
              required
            />
            <Button type="submit" variant="contained" color="primary" sx={{ mt: 2 }} fullWidth>
              {t('sendMessage')}
            </Button>
          </form>
        )}
        <Snackbar
          open={snackbar.open}
          autoHideDuration={6000}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
        >
          <Alert onClose={() => setSnackbar({ ...snackbar, open: false })} severity={snackbar.severity}>
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Container>
    </Box>
  );
}

export default Contact;