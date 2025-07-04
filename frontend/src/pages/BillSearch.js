import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container, Typography, Box, TextField, Button, Snackbar, Alert,
  Table, TableHead, TableBody, TableRow, TableCell, TableContainer, Paper, CircularProgress
} from '@mui/material';
import { API_BASE_URL } from '../config';
import LoadingModal from '../components/LoadingModal';

export default function BillSearch({ t = x => x }) {
  // Existing advanced search state
  const [form, setForm] = useState({
    unique_number: '',
    bl_number: '',
    customer_name: ''
  });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const role = localStorage.getItem('role');
  const username = localStorage.getItem('username');
  const navigate = useNavigate();

  // Simple search state for merged code
  const [query, setQuery] = useState('');
  const [bills, setBills] = useState([]);
  const [error, setError] = useState(null);

  // Simple search handler (merged code)
  const handleSimpleSearch = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/bill_search?q=${encodeURIComponent(query)}`, {
        credentials: 'include',
      });
      if (!response.ok) throw new Error('Failed to fetch bills');
      const data = await response.json();
      setBills(data.bills || []);
    } catch (err) {
      setError('Failed to fetch bills');
      setBills([]);
    } finally {
      setLoading(false);
    }
  };

  // Advanced search handler (existing)
  useEffect(() => {
    if (role === 'customer') {
      const token = localStorage.getItem('token');
      if (token) {
        handleSearch();
      } else {
        setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
        navigate('/login');
      }
    }
    // eslint-disable-next-line
  }, []);

  const handleChange = e => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSearch = async () => {
    setLoading(true);
    const token = localStorage.getItem('token');
    if (!token) {
      setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
      setLoading(false);
      navigate('/login');
      return;
    }
    let searchForm = { ...form };
    if (role === 'customer') {
      searchForm.username = username;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/search_bills`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(searchForm)
      });
      if (res.status === 401) {
        setSnackbar({ open: true, message: 'Session expired. Please log in again.', severity: 'error' });
        localStorage.clear();
        navigate('/login');
        return;
      }
      if (res.ok) {
        const data = await res.json();
        setResults(data);
      } else {
        const data = await res.json();
        setSnackbar({ open: true, message: data.error || 'Search failed', severity: 'error' });
      }
    } catch (error) {
      setSnackbar({ open: true, message: 'Search failed. Please try again.', severity: 'error' });
    } finally {
      setLoading(false);
    }
    if (role !== 'customer') {
      setForm({
        unique_number: '',
        bl_number: '',
        customer_name: ''
      });
    }
  };

  // Utility functions (existing)
  const getStatus = (record) => {
    if (record.status === t('invoiceSent')) return t('invoiceSent');
    if (record.status === t('awaitingBankIn')) return t('awaitingBankIn');
    if (record.status === t('paidAndCtnValid')) return t('paidAndCtnValid');
    if (record.status === t('pending')) return t('pending');
    if (record.status === 'Completed') return t('paidAndCtnValid');
    return record.status || t('pending');
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (error) {
      return dateString;
    }
  };

  return (
    <Container maxWidth="md" sx={{ py: { xs: 2, sm: 4 } }}>
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'flex-start' }}>
        <Button onClick={() => navigate('/dashboard')} variant="contained" color="primary">
          {t('backToDashboard')}
        </Button>
      </Box>
      <Typography variant="h4" align="center" gutterBottom>
        {t('yourBills')}
      </Typography>

      {role !== 'customer' && (
        <Box
          component="form"
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 2,
            alignItems: 'center',
            justifyContent: 'center',
            mb: 2
          }}
          onSubmit={e => { e.preventDefault(); handleSearch(); }}
        >
          <TextField
            label={t('ctnNumber')}
            name="unique_number"
            value={form.unique_number}
            onChange={handleChange}
            size="small"
          />
          <TextField
            label={t('billOfLadingNumber')}
            name="bl_number"
            value={form.bl_number}
            onChange={handleChange}
            size="small"
          />
          <TextField
            label={t('customerName')}
            name="customer_name"
            value={form.customer_name}
            onChange={handleChange}
            size="small"
          />
          <Button variant="contained" color="primary" type="submit" disabled={loading}>
            {t('search')}
          </Button>
        </Box>
      )}

      <Box sx={{ overflowX: 'auto', mt: 2 }}>
        <Table size="small" sx={{
          minWidth: 600,
          '& th, & td': {
            whiteSpace: { xs: 'nowrap', sm: 'normal' },
            fontSize: { xs: '0.85rem', sm: '1rem' },
            px: { xs: 1, sm: 2 },
            py: { xs: 0.5, sm: 1 }
          }
        }}>
          <TableHead>
            <TableRow>
              <TableCell>{t('ctnNumber')}</TableCell>
              <TableCell>{t('billOfLadingNumber')}</TableCell>
              <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>{t('customerName')}</TableCell>
              <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>{t('containerNo')}</TableCell>
              <TableCell>{t('status')}</TableCell>
              <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>{t('createdAt')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {results.map(row => (
              <TableRow key={row.id}>
                <TableCell>{row.unique_number}</TableCell>
                <TableCell>{row.bl_number}</TableCell>
                <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>{row.customer_name}</TableCell>
                <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>{row.container_numbers}</TableCell>
                <TableCell>{getStatus(row)}</TableCell>
                <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>{formatDate(row.created_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>

      <LoadingModal 
        open={loading} 
        message={t('loadingData')} 
      />

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert onClose={() => setSnackbar({ ...snackbar, open: false })} severity={snackbar.severity}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Container>
  );
}