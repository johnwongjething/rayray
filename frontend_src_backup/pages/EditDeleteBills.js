import React, { useState, useEffect } from 'react';
import { Container, Typography, Box, TextField, Button, Snackbar, Alert } from '@mui/material';
import { Table as AntdTable, Button as AntdButton, Modal, message, DatePicker } from 'antd';
import { API_BASE_URL } from '../config';
import { ArrowBack as ArrowBackIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import moment from 'moment';

function EditDeleteBills({ t = x => x }) {
  const [search, setSearch] = useState({ customer_name: '', customer_id: '', created_at: '', bl_number: '' });
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const navigate = useNavigate();

  useEffect(() => {
    // Only allow staff/admin
    const role = localStorage.getItem('role');
    if (role !== 'staff' && role !== 'admin') {
      setSnackbar({ open: true, message: 'Unauthorized', severity: 'error' });
      navigate('/login');
      return;
    }
    // Fetch all bills on component mount
    fetchBills();
  }, [navigate]);

  const fetchBills = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
        navigate('/login');
        return;
      }

      const res = await fetch(`${API_BASE_URL}/api/search_bills`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(search)
      });

      if (res.status === 401) {
        setSnackbar({ open: true, message: 'Session expired. Please log in again.', severity: 'error' });
        localStorage.clear();
        navigate('/login');
        return;
      }

      if (res.ok) {
        const data = await res.json();
        setBills(data);
      } else {
        const data = await res.json();
        setSnackbar({ open: true, message: data.error || 'Failed to fetch bills', severity: 'error' });
        setBills([]);
      }
    } catch (error) {
      console.error('Error fetching bills:', error);
      setSnackbar({ open: true, message: 'Failed to fetch bills', severity: 'error' });
      setBills([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteConfirmed = async (id) => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
        navigate('/login');
        return;
      }

      const res = await fetch(`${API_BASE_URL}/api/bill/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });

      if (res.status === 401) {
        setSnackbar({ open: true, message: 'Session expired. Please log in again.', severity: 'error' });
        localStorage.clear();
        navigate('/login');
        return;
      }

      const data = await res.json();
      if (res.ok) {
        setSnackbar({ open: true, message: 'Deleted!', severity: 'success' });
        fetchBills();
      } else {
        setSnackbar({ open: true, message: data.error || 'Delete failed', severity: 'error' });
      }
    } catch (error) {
      console.error('Error deleting bill:', error);
      setSnackbar({ open: true, message: 'Delete failed', severity: 'error' });
    }
  };

  const handleDelete = (id) => {
    if (window.confirm('Are you sure you want to delete this bill?')) {
      handleDeleteConfirmed(id);
    }
  };

  const columns = [
    { title: t('id'), dataIndex: 'id' },
    { title: t('customerName'), dataIndex: 'customer_name' },
    { title: t('customerEmail'), dataIndex: 'customer_email' },
    { title: t('customerPhone'), dataIndex: 'customer_phone' },
    { title: t('blNumber'), dataIndex: 'bl_number' },
    { title: t('createdAt'), dataIndex: 'created_at' },
    { title: t('status'), dataIndex: 'status' },
    {
      title: t('actions'),
      render: (_, record) => (
        <>
          <AntdButton onClick={() => navigate(`/edit-bill/${record.id}`)} style={{ marginRight: 8 }}>{t('edit')}</AntdButton>
          <AntdButton danger onClick={() => handleDelete(record.id)}>{t('delete')}</AntdButton>
        </>
      )
    }
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'flex-start', alignItems: 'center' }}>
        <Button variant="contained" color="primary" style={{ color: '#fff' }} onClick={() => navigate('/dashboard')}>
          {t('backToDashboard')}
        </Button>
        <h1 style={{ marginLeft: 16 }}>{t('editDeleteBills')}</h1>
      </div>
      <form onSubmit={e => { e.preventDefault(); fetchBills(); }} style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <TextField placeholder={t('customerName')} value={search.customer_name} onChange={e => setSearch(s => ({ ...s, customer_name: e.target.value }))} size="small" />
        <TextField placeholder={t('customerID')} value={search.customer_id} onChange={e => setSearch(s => ({ ...s, customer_id: e.target.value }))} size="small" />
        <DatePicker placeholder={t('createDate')} value={search.created_at ? moment(search.created_at) : null} onChange={(_, dateString) => setSearch(s => ({ ...s, created_at: dateString }))} style={{ height: 40 }} />
        <TextField placeholder={t('blNumber')} value={search.bl_number} onChange={e => setSearch(s => ({ ...s, bl_number: e.target.value }))} size="small" />
        <Button type="submit" variant="contained">{t('search')}</Button>
      </form>
      <AntdTable
        style={{ marginTop: 24 }}
        dataSource={bills}
        rowKey="id"
        columns={columns}
        loading={loading}
        pagination={{ pageSize: 10 }}
      />
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
    </div>
  );
}

export default EditDeleteBills; 