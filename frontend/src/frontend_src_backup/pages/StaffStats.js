import React, { useEffect, useState } from 'react';
import { Container, Typography, Box, Grid, Paper, Button, CircularProgress, Alert, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Link } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '../config';

function StaffStats({ t = x => x }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [outstanding, setOutstanding] = useState([]);
  const [loadingOutstanding, setLoadingOutstanding] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchStats = async () => {
      setLoading(true);
      setError(null);
      try {
        const token = localStorage.getItem('token');
        if (!token) {
          setError('Authentication required. Please log in again.');
          navigate('/login');
          return;
        }

        const res = await fetch(`${API_BASE_URL}/api/stats/summary`, {
          headers: { Authorization: `Bearer ${token}` }
        });

        if (res.status === 401) {
          setError('Session expired. Please log in again.');
          localStorage.clear();
          navigate('/login');
          return;
        }

        if (res.ok) {
          const data = await res.json();
          setStats(data);
        } else {
          setError(t('failedToFetchStats'));
        }
      } catch (err) {
        setError(t('failedToFetchStats'));
      }
      setLoading(false);
    };
    fetchStats();
  }, [t, navigate]);

  useEffect(() => {
    const fetchOutstanding = async () => {
      setLoadingOutstanding(true);
      try {
        const token = localStorage.getItem('token');
        if (!token) {
          navigate('/login');
          return;
        }

        const res = await fetch(`${API_BASE_URL}/api/stats/outstanding_bills`, {
          headers: { Authorization: `Bearer ${token}` }
        });

        if (res.status === 401) {
          localStorage.clear();
          navigate('/login');
          return;
        }

        const data = await res.json();
        if (res.ok) {
          setOutstanding(data);
        }
      } catch (err) {}
      setLoadingOutstanding(false);
    };
    fetchOutstanding();
  }, [t, navigate]);

  return (
    <Container>
      <Box sx={{ my: 4 }}>
        <Button onClick={() => navigate('/dashboard')} variant="contained" color="primary" style={{ color: '#fff', marginBottom: 16 }}>
          {t('backToDashboard')}
        </Button>
        <Typography variant="h3" component="h1" gutterBottom>
          {t('staffStats')}
        </Typography>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>
        ) : error ? (
          <Alert severity="error" sx={{ mt: 4 }}>{error}</Alert>
        ) : (
          <Grid container spacing={3}>
            <Grid item xs={12} sm={6} md={4}>
              <Paper sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="h5" component="h2" gutterBottom>
                  {t('totalBills')}
                </Typography>
                <Typography variant="h4" component="p">
                  {stats.total_bills}
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Paper sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="h5" component="h2" gutterBottom>
                  {t('completedBills')}
                </Typography>
                <Typography variant="h4" component="p">
                  {stats.completed_bills}
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Paper sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="h5" component="h2" gutterBottom>
                  {t('pendingBills')}
                </Typography>
                <Typography variant="h4" component="p">
                  {stats.pending_bills}
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Paper sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="h5" component="h2" gutterBottom>
                  {t('totalInvoiceAmount')}
                </Typography>
                <Typography variant="h4" component="p">
                  {stats.total_invoice_amount}
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Paper sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="h5" component="h2" gutterBottom>
                  {t('totalPaymentReceived')}
                </Typography>
                <Typography variant="h4" component="p">
                  {stats.total_payment_received}
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Paper sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="h5" component="h2" gutterBottom>
                  {t('totalPaymentOutstanding')}
                </Typography>
                <Typography variant="h4" component="p">
                  {stats.total_payment_outstanding}
                </Typography>
              </Paper>
            </Grid>
          </Grid>
        )}
        <Box sx={{ mt: 6 }}>
          <Typography variant="h5" gutterBottom>{t('outstandingPayments')}</Typography>
          {loadingOutstanding ? (
            <CircularProgress />
          ) : (
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>{t('id')}</TableCell>
                    <TableCell>{t('customerName')}</TableCell>
                    <TableCell>{t('blNumber')}</TableCell>
                    <TableCell>{t('invoiceAmount')}</TableCell>
                    <TableCell>{t('invoicePDF')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {outstanding.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell>{row.id}</TableCell>
                      <TableCell>{row.customer_name}</TableCell>
                      <TableCell>{row.bl_number}</TableCell>
                      <TableCell>${row.service_fee ? Number(row.service_fee).toFixed(2) : '0.00'}</TableCell>
                      <TableCell>
                        {row.invoice_filename ? (
                          <Link href={`${API_BASE_URL}/uploads/${row.invoice_filename}`} target="_blank" rel="noopener noreferrer">
                            {t('viewPDF')}
                          </Link>
                        ) : 'N/A'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      </Box>
    </Container>
  );
}

export default StaffStats; 