import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Container, Typography, Box, TextField, Button, Snackbar, Alert } from '@mui/material';
import { API_BASE_URL } from '../config';
import LoadingModal from '../components/LoadingModal';

export default function BillSearch({ t = x => x }) {
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

  useEffect(() => {
    // For customers, automatically fetch their bills when component mounts
    if (role === 'customer') {
      const token = localStorage.getItem('token');
      if (token) {
      handleSearch();
      } else {
        setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
        navigate('/login');
      }
    }
  }, []);

  const handleChange = e => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSearch = async () => {
    setLoading(true);
    const token = localStorage.getItem('token');
    
    // Check if token exists
    if (!token) {
      setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
      setLoading(false);
      navigate('/login');
      return;
    }
    
    let searchForm = { ...form };
    
    // Always include username for customers
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
        // Token is invalid or expired
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
      console.error('Search error:', error);
      setSnackbar({ open: true, message: 'Search failed. Please try again.', severity: 'error' });
    } finally {
      setLoading(false);
    }
    
    // Only clear form if it's not an automatic customer fetch
    if (role !== 'customer') {
      setForm({
        unique_number: '',
        bl_number: '',
        customer_name: ''
      });
    }
  };

  const getStatus = (record) => {
    if (record.status === t('invoiceSent')) return t('invoiceSent');
    if (record.status === t('awaitingBankIn')) return t('awaitingBankIn');
    if (record.status === t('paidAndCtnValid')) return t('paidAndCtnValid');
    if (record.status === t('pending')) return t('pending');
    if (record.status === 'Completed') return t('paidAndCtnValid');
    return record.status || t('pending');
  };

  const columns = [
    // ... other columns ...
    {
      title: t('status'),
      dataIndex: 'status',
      key: 'status',
      render: (_, record) => getStatus(record)
    },
    // ... other columns ...
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 16 }}>
        <Button onClick={() => navigate('/dashboard')} variant="contained" color="primary" style={{ color: '#fff' }}>
          {t('backToDashboard')}
        </Button>
      </div>
      <h2 style={{ textAlign: 'center' }}>{t('yourBills')}</h2>
      
      {role !== 'customer' && (
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
          <TextField label={t('ctnNumber')} name="unique_number" value={form.unique_number} onChange={handleChange} />
          <TextField label={t('billOfLadingNumber')} name="bl_number" value={form.bl_number} onChange={handleChange} />
          <TextField label={t('customerName')} name="customer_name" value={form.customer_name} onChange={handleChange} />
          <Button variant="contained" color="primary" onClick={handleSearch} disabled={loading}>{t('search')}</Button>
        </div>
      )}
      
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <table border="1" cellPadding="4" style={{ marginTop: 16 }}>
          <thead>
            <tr>
              <th>{t('ctnNumber')}</th>
              <th>{t('billOfLadingNumber')}</th>
              <th>{t('customerName')}</th>
              <th>{t('containerNo')}</th>
              <th>{t('status')}</th>
            </tr>
          </thead>
          <tbody>
            {results.map(row => (
              <tr key={row.id}>
                <td>{row.unique_number}</td>
                <td>{row.bl_number}</td>
                <td>{row.customer_name}</td>
                <td>{row.container_numbers}</td>
                <td>{getStatus(row)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {/* Loading Modal for Data Loading */}
      <LoadingModal 
        open={loading} 
        message={t('loadingData')} 
      />
      
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert onClose={() => setSnackbar({ ...snackbar, open: false })} severity={snackbar.severity}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </div>
  );
}