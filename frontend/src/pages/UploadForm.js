import React, { useState, useEffect } from 'react';
import { TextField, Button, Typography, Snackbar, Alert, CircularProgress } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '../config';
import LoadingModal from '../components/LoadingModal';

const { Title } = Typography;

function UploadForm({ t = x => x }) {
  const [billFiles, setBillFiles] = useState([]);
  const [invoiceFile, setInvoiceFile] = useState(null);
  const [packingFile, setPackingFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [formValues, setFormValues] = useState({ name: '', email: '', phone: '' });
  const navigate = useNavigate();
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  useEffect(() => {
    const fetchCustomerInfo = async () => {
      const token = localStorage.getItem('token');
      if (!token) return;
      try {
        const res = await fetch(`${API_BASE_URL}/api/me`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setFormValues({
            name: data.customer_name || '',
            email: data.customer_email || '',
            phone: data.customer_phone || ''
          });
        }
      } catch (err) {}
    };
    fetchCustomerInfo();
  }, []);

  const handleInputChange = (e) => {
    setFormValues({ ...formValues, [e.target.name]: e.target.value });
  };

  const handleBillFileChange = (e) => {
    const files = Array.from(e.target.files);
    const validFiles = files.filter(file => file.type === 'application/pdf');
    if (validFiles.length !== files.length) {
      setSnackbar({ open: true, message: t('onlyPDF'), severity: 'error' });
    }
    setBillFiles(validFiles);
  };
  const handleInvoiceFileChange = (e) => {
    const file = e.target.files[0];
    if (file && file.type !== 'application/pdf') {
      setSnackbar({ open: true, message: t('onlyPDF'), severity: 'error' });
      setInvoiceFile(null);
    } else {
      setInvoiceFile(file);
    }
  };
  const handlePackingFileChange = (e) => {
    const file = e.target.files[0];
    if (file && file.type !== 'application/pdf') {
      setSnackbar({ open: true, message: t('onlyPDF'), severity: 'error' });
      setPackingFile(null);
    } else {
      setPackingFile(file);
    }
  };

  const onFinish = async (e) => {
    e.preventDefault();
    if (billFiles.length === 0 && !invoiceFile && !packingFile) {
      setSnackbar({ open: true, message: t('pleaseUpload'), severity: 'error' });
      return;
    }
    if (!invoiceFile || !packingFile) {
      let msg = t('confirmOptionalFiles') || 'Invoice and/or Packing List not uploaded. Do you want to continue?';
      if (!msg || msg === 'confirmOptionalFiles') msg = 'Invoice and/or Packing List not uploaded. Do you want to continue?';
      if (!window.confirm(msg)) return;
    }
    setLoading(true);
    const token = localStorage.getItem('token');
    if (!token) {
      setSnackbar({ open: true, message: t('notLoggedIn'), severity: 'error' });
      setLoading(false);
      return;
    }
    const formData = new FormData();
    formData.append('name', formValues.name);
    formData.append('email', formValues.email);
    formData.append('phone', formValues.phone);
    billFiles.forEach((file, idx) => formData.append('bill_pdf', file));
    if (invoiceFile) formData.append('invoice_pdf', invoiceFile);
    if (packingFile) formData.append('packing_pdf', packingFile);
    try {
      const res = await fetch(`${API_BASE_URL}/api/upload`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`
        },
        body: formData
      });
      const data = await res.json();
      if (!res.ok) {
        setSnackbar({ open: true, message: data.error || t('failed'), severity: 'error' });
      } else {
        setSnackbar({ open: true, message: t('success'), severity: 'success' });
        setBillFiles([]);
        setInvoiceFile(null);
        setPackingFile(null);
        setFormValues({ name: '', email: '', phone: '' });
      }
    } catch (err) {
      setSnackbar({ open: true, message: t('failed'), severity: 'error' });
    }
    setLoading(false);
  };

  return (
    <div style={{ maxWidth: 500, margin: '40px auto', padding: 24, background: '#fff', borderRadius: 8 }}>
      <Button onClick={() => navigate('/dashboard')} variant="contained" color="primary" style={{ color: '#fff', marginBottom: 16 }}>
        {t('backToDashboard')}
      </Button>
      <Typography variant="h5" gutterBottom>{t('uploadTitle')}</Typography>
      <form onSubmit={onFinish}>
        <TextField label={t('name')} name="name" value={formValues.name} onChange={handleInputChange} required fullWidth margin="normal" />
        <TextField label={t('email')} name="email" value={formValues.email} onChange={handleInputChange} required type="email" fullWidth margin="normal" />
        <TextField label={t('phone')} name="phone" value={formValues.phone} onChange={handleInputChange} required fullWidth margin="normal" />
        <div style={{ margin: '16px 0' }}>
          <Button variant="outlined" component="label" fullWidth>
            {t('selectPDFBill')}
            <input type="file" accept="application/pdf" hidden multiple onChange={handleBillFileChange} />
          </Button>
          <div style={{ marginTop: 8, color: '#888', fontSize: 13 }}>
            {t('uploadLimit') !== 'uploadLimit' ? t('uploadLimit') : 'You can upload up to 5 files.'}
          </div>
          {billFiles.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {billFiles.map((file, idx) => <div key={idx}>{file.name}</div>)}
            </div>
          )}
        </div>
        <div style={{ margin: '16px 0' }}>
          <Button variant="outlined" component="label" fullWidth>
            {t('selectPDFInvoice')}
            <input type="file" accept="application/pdf" hidden onChange={handleInvoiceFileChange} />
          </Button>
          {invoiceFile && <div style={{ marginTop: 8 }}>{invoiceFile.name}</div>}
        </div>
        <div style={{ margin: '16px 0' }}>
          <Button variant="outlined" component="label" fullWidth>
            {t('selectPDFPacking')}
            <input type="file" accept="application/pdf" hidden onChange={handlePackingFileChange} />
          </Button>
          {packingFile && <div style={{ marginTop: 8 }}>{packingFile.name}</div>}
        </div>
        <Button type="submit" variant="contained" color="primary" fullWidth disabled={loading}>
          {loading ? <CircularProgress size={24} /> : t('submit')}
        </Button>
      </form>
      <LoadingModal 
        open={loading} 
        message={t('uploadingFiles')} 
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

export default UploadForm; 