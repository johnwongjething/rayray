import React, { useEffect, useState } from 'react';
import { Container, Typography, Box, Button, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, CircularProgress, Snackbar, Alert } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '../config';

function UserApproval({ t = x => x }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const navigate = useNavigate();

  // Fetch unapproved users
  const fetchUsers = async () => {
    setLoading(true);
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
        setLoading(false);
        return;
      }
      if (!res.ok) throw new Error('Failed to fetch users');
      const data = await res.json();
      setUsers(data.users || data || []);
      setError(null);
    } catch (err) {
      setError('Failed to fetch users');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
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
        fetchUsers();
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
        {loading ? (
          <CircularProgress />
        ) : error ? (
          <Typography color="error">{error}</Typography>
        ) : (
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Username</TableCell>
                  <TableCell>Email</TableCell>
                  <TableCell>Company Name</TableCell>
                  <TableCell>Phone</TableCell>
                  <TableCell>Role</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>{user.username}</TableCell>
                    <TableCell>{user.customer_email}</TableCell>
                    <TableCell>{user.customer_name}</TableCell>
                    <TableCell>{user.customer_phone}</TableCell>
                    <TableCell>{user.role}</TableCell>
                    <TableCell>
                      <Button variant="contained" color="primary" onClick={() => handleApprove(user.id)}>
                        Approve
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
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