import React, { useEffect, useState } from 'react';
import { Container, Typography, Box, Button, List, ListItem, ListItemText, Snackbar, Alert } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '../config';

const UserApproval = () => {
  const [unapprovedUsers, setUnapprovedUsers] = useState([]);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const navigate = useNavigate();

  // Fetch unapproved users
  const fetchUnapprovedUsers = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/unapproved_users`, {
        method: 'GET',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' }
      });
      if (res.status === 401) {
        setSnackbar({ open: true, message: 'Session expired. Please log in again.', severity: 'error' });
        localStorage.clear();
        navigate('/login');
        return;
      }
      if (res.ok) {
        const data = await res.json();
        setUnapprovedUsers(data);
      } else {
        setSnackbar({ open: true, message: 'Failed to fetch users', severity: 'error' });
      }
    } catch (error) {
      setSnackbar({ open: true, message: 'Failed to fetch users', severity: 'error' });
    }
  };

  useEffect(() => {
    fetchUnapprovedUsers();
  }, []);

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
          Back to Dashboard
        </Button>
        <Typography variant="h4" gutterBottom>User Approval</Typography>
        <List>
          {unapprovedUsers.map((user) => (
            <ListItem key={user.id}>
              <ListItemText
                primary={user.username}
                secondary={
                  <>
                    <div>Email: {user.customer_email}</div>
                    <div>Company Name: {user.customer_name}</div>
                    <div>Phone: {user.customer_phone}</div>
                    <div>Role: {user.role}</div>
                  </>
                }
              />
              <Button variant="contained" color="primary" onClick={() => handleApprove(user.id)}>
                Approve
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