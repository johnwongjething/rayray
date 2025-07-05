import React, { useEffect, useState } from 'react';
import { Container, Typography, Box, Button, List, ListItem, ListItemText, Snackbar, Alert } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '../config';

function UserApproval({ t = x => x }) {
  const [unapprovedUsers, setUnapprovedUsers] = useState([]);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const navigate = useNavigate();

  const fetchUnapprovedUsers = async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
        navigate('/login');
        return;
      }

      console.log('Fetching unapproved users from:', `${API_BASE_URL}/api/unapproved_users`);
      const res = await fetch(`${API_BASE_URL}/api/unapproved_users`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      console.log('Response status:', res.status);

      if (res.status === 401) {
        setSnackbar({ open: true, message: 'Session expired. Please log in again.', severity: 'error' });
        localStorage.clear();
        navigate('/login');
        return;
      }

      if (res.ok) {
        const data = await res.json();
        console.log('Response data:', data);
        setUnapprovedUsers(data);
      } else {
        setSnackbar({ open: true, message: 'Failed to fetch users', severity: 'error' });
      }
    } catch (error) {
      console.error('Error fetching unapproved users:', error);
      setSnackbar({ open: true, message: 'Failed to fetch users', severity: 'error' });
    }
  };

  useEffect(() => {
    fetchUnapprovedUsers();
  }, [navigate]);

  const handleApprove = async (id) => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
        navigate('/login');
        return;
      }

      const res = await fetch(`${API_BASE_URL}/api/approve_user/${id}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });

      if (res.status === 401) {
        setSnackbar({ open: true, message: 'Session expired. Please log in again.', severity: 'error' });
        localStorage.clear();
        navigate('/login');
        return;
      }

      if (res.ok) {
        setSnackbar({ open: true, message: 'User approved successfully', severity: 'success' });
        fetchUnapprovedUsers();
      } else {
        setSnackbar({ open: true, message: 'Failed to approve user', severity: 'error' });
      }
    } catch (error) {
      console.error('Error approving user:', error);
      setSnackbar({ open: true, message: 'Failed to approve user', severity: 'error' });
    }
  };

  return (
    <Container>
      <Box sx={{ my: 4 }}>
        <Button onClick={() => navigate('/dashboard')} variant="contained" color="primary" style={{ color: '#fff', marginBottom: 16 }}>
          {t('backToDashboard')}
        </Button>
        <Typography variant="h4" gutterBottom>{t('userApproval')}</Typography>
        <List>
          {unapprovedUsers.map((user) => (
            <ListItem key={user.id}>
              <ListItemText
                primary={user.username}
                secondary={
                  <>
                    <div>{t('email')}: {user.customer_email}</div>
                    <div>{t('companyName')}: {user.customer_name}</div>
                    <div>{t('phone')}: {user.customer_phone}</div>
                    <div>{t('role')}: {t(user.role)}</div>
                  </>
                }
              />
              <Button variant="contained" color="primary" onClick={() => handleApprove(user.id)}>
                {t('approve')}
              </Button>
            </ListItem>
          ))}
        </List>
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

export default UserApproval; 