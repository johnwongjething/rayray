import React, { useState, useEffect } from 'react';
import { Container, Typography, Button, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, CircularProgress, Alert, Snackbar } from '@mui/material';
import { API_BASE_URL } from '../config';

function UserApproval({ t = x => x }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const fetchUsers = async () => {
    setLoading(true);
    setError(null);
    const token = document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1];
    if (!token) {
      setError('Not authenticated');
      setLoading(false);
      return;
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/unapproved_users`, {
        credentials: 'include',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to fetch users');
      const data = await response.json();
      setUsers(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message);
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleApprove = async (userId) => {
    const token = document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1];
    if (!token) {
      setSnackbar({ open: true, message: 'Not authenticated', severity: 'error' });
      return;
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/approve_user/${userId}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to approve user');
      setSnackbar({ open: true, message: t('userApproved') || 'User approved', severity: 'success' });
      fetchUsers();
    } catch (err) {
      setSnackbar({ open: true, message: t('failedToApproveUser') || 'Approval failed', severity: 'error' });
    }
  };

  const handleCloseSnackbar = () => setSnackbar({ ...snackbar, open: false });

  return (
    <Container>
      <Typography variant="h4" gutterBottom>{t('userApproval')}</Typography>
      {loading ? <CircularProgress /> : error ? <Alert severity="error">{error}</Alert> : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>{t('username')}</TableCell>
                <TableCell>{t('email')}</TableCell>
                <TableCell>{t('actions')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {users.map(user => (
                <TableRow key={user.id}>
                  <TableCell>{user.username}</TableCell>
                  <TableCell>{user.customer_email}</TableCell>
                  <TableCell>
                    <Button variant="contained" color="primary" onClick={() => handleApprove(user.id)}>
                      {t('approve')}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={handleCloseSnackbar} message={snackbar.message} />
    </Container>
  );
}

export default UserApproval;