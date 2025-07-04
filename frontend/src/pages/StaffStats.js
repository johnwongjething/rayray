import React, { useEffect, useState } from 'react';
import { Container, Typography, Box, Grid, Paper, Button, CircularProgress, Alert, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Link } from '@mui/material';
import { DatePicker } from 'antd';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '../config';
import jsPDF from 'jspdf';
import 'jspdf-autotable';
import LoadingModal from '../components/LoadingModal';

function StaffStats({ t = x => x }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [outstanding, setOutstanding] = useState([]);
  const [loadingOutstanding, setLoadingOutstanding] = useState(true);
  const [date, setDate] = useState(null);
  const [bills, setBills] = useState([]);
  const [loadingBills, setLoadingBills] = useState(false);
  const navigate = useNavigate();

  // Fetch summary stats
  useEffect(() => {
    const fetchStats = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API_BASE_URL}/api/stats/summary`, {
          credentials: 'include'
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

  // Fetch outstanding payments
  useEffect(() => {
    const fetchOutstanding = async () => {
      setLoadingOutstanding(true);
      try {
        const res = await fetch(`${API_BASE_URL}/api/stats/outstanding_bills`, {
          credentials: 'include'
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

  // Fetch completed bills
  const fetchBills = async (searchDateString = null) => {
    setLoadingBills(true);
    try {
      let url = `${API_BASE_URL}/api/staff_stats`;
      if (searchDateString) url += `?completed_at=${searchDateString}`;
      const response = await fetch(url, {
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        setBills(data.bills || []);
      }
    } catch (e) {
      setBills([]);
    } finally {
      setLoadingBills(false);
    }
  };

  useEffect(() => {
    fetchBills();
  }, []);

  const handleDateSearch = () => {
    if (date) fetchBills(date.format('YYYY-MM-DD'));
  };

  const handleClearDateSearch = () => {
    setDate(null);
    fetchBills(null);
  };

  const handleExportPDF = () => {
    const doc = new jsPDF();
    doc.setFontSize(16);
    doc.text(t('staffStatsReport'), 20, 20);

    const tableColumn = [
      t('blNumber'),
      t('ctnFee'),
      t('serviceFee'),
      t('total'),
      t('customerName'),
      t('paymentType'),
      t('date')
    ];
    const tableRows = bills.map(bill => [
      bill.bl_number || '',
      `$${bill.display_ctn_fee || 0}`,
      `$${bill.display_service_fee || 0}`,
      `$${(parseFloat(bill.display_ctn_fee || 0) + parseFloat(bill.display_service_fee || 0)).toFixed(2)}`,
      bill.customer_name || '',
      bill.payment_method === 'Allinpay' ? 'Allinpay' : 'Bank Transfer',
      bill.completed_at ? new Date(bill.completed_at).toLocaleString('en-HK', { timeZone: 'Asia/Hong_Kong' }) : ''
    ]);

    doc.autoTable({
      head: [tableColumn],
      body: tableRows,
      startY: 40,
      styles: { fontSize: 10, cellPadding: 4, halign: 'center', valign: 'middle' },
      headStyles: { fillColor: [41, 128, 185], textColor: 255, fontStyle: 'bold' },
      alternateRowStyles: { fillColor: [245, 245, 245] },
      theme: 'grid',
    });
    doc.save('staff_stats.pdf');
  };

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
        ) : stats && (
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

        {/* Outstanding Payments Table */}
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
                    <TableCell>{t('ctnFee')}</TableCell>
                    <TableCell>{t('serviceFee')}</TableCell>
                    <TableCell>{t('total')}</TableCell>
                    <TableCell>{t('outstanding')}</TableCell>
                    <TableCell>{t('invoicePDF')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {outstanding.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell>{row.id}</TableCell>
                      <TableCell>{row.customer_name}</TableCell>
                      <TableCell>{row.bl_number}</TableCell>
                      <TableCell>${row.ctn_fee ? Number(row.ctn_fee).toFixed(2) : '0.00'}</TableCell>
                      <TableCell>${row.service_fee ? Number(row.service_fee).toFixed(2) : '0.00'}</TableCell>
                      <TableCell>${((Number(row.ctn_fee) || 0) + (Number(row.service_fee) || 0)).toFixed(2)}</TableCell>
                      <TableCell>
                        ${row.outstanding_amount !== undefined
                          ? Number(row.outstanding_amount).toFixed(2)
                          : ((Number(row.ctn_fee) || 0) + (Number(row.service_fee) || 0)).toFixed(2)
                        }
                      </TableCell>
                      <TableCell>
                        {row.invoice_filename ? (
                          <Link
                            href={`${API_BASE_URL}/uploads/${row.invoice_filename}`}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
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

        {/* Completed Bills Table */}
        <Box sx={{ mt: 6 }}>
          <Typography variant="h5" gutterBottom>{t('completedBills')}</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <DatePicker value={date} onChange={setDate} style={{ marginRight: 8 }} allowClear />
            <Button variant="outlined" onClick={handleDateSearch} sx={{ mr: 2 }}>{t('search')}</Button>
            <Button variant="outlined" onClick={handleClearDateSearch} sx={{ mr: 2 }}>{t('clearSearch')}</Button>
            <Button variant="outlined" onClick={handleExportPDF} sx={{ fontWeight: 'bold', ml: 2 }}>{t('exportToPDF')}</Button>
          </Box>
          {loadingBills ? (
            <CircularProgress />
          ) : (
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>{t('blNumber')}</TableCell>
                    <TableCell>{t('ctnFee')}</TableCell>
                    <TableCell>{t('serviceFee')}</TableCell>
                    <TableCell>{t('total')}</TableCell>
                    <TableCell>{t('customerName')}</TableCell>
                    <TableCell>{t('paymentType')}</TableCell>
                    <TableCell>{t('date')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {bills.map((row, idx) => (
                    <TableRow key={row.id || idx}>
                      <TableCell>{row.bl_number}</TableCell>
                      <TableCell>${row.display_ctn_fee}</TableCell>
                      <TableCell>${row.display_service_fee}</TableCell>
                      <TableCell>${(Number(row.display_ctn_fee) + Number(row.display_service_fee)).toFixed(2)}</TableCell>
                      <TableCell>{row.customer_name}</TableCell>
                      <TableCell>{row.payment_method === 'Allinpay' ? 'Allinpay' : 'Bank Transfer'}</TableCell>
                      <TableCell>{row.completed_at ? new Date(row.completed_at).toLocaleString('en-HK', { timeZone: 'Asia/Hong_Kong' }) : ''}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      </Box>
      <LoadingModal open={loading || loadingBills} message={t('loadingData')} />
    </Container>
  );
}

export default StaffStats;