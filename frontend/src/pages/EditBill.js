import React, { useEffect, useState } from 'react';
import { TextField, Button, Snackbar, Alert, CircularProgress } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '../config';
import LoadingModal from '../components/LoadingModal';

function EditBill({ t = x => x }) {
  const { id } = useParams();
  const [formValues, setFormValues] = useState({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const navigate = useNavigate();

  useEffect(() => {
    // Only allow staff/admin
    const role = localStorage.getItem('role');
    console.log('role:', role);
    if (role !== 'staff' && role !== 'admin') {
      setSnackbar({ open: true, message: 'Unauthorized', severity: 'error' });
      navigate('/login');
      return;
    }
    // Fetch bill data
    const fetchBill = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/bills/${id}`);
        if (res.ok) {
          const data = await res.json();
          setFormValues(data);
        } else {
          setSnackbar({ open: true, message: 'Bill not found', severity: 'error' });
          navigate('/edit-delete-bills');
        }
      } catch (error) {
        console.error('Error fetching bill:', error);
        setSnackbar({ open: true, message: error.message, severity: 'error' });
        navigate('/edit-delete-bills');
      } finally {
        setLoading(false);
      }
    };
    fetchBill();
  }, [id, navigate]);

  const handleChange = (e) => {
    setFormValues({ ...formValues, [e.target.name]: e.target.value });
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const token = localStorage.getItem('token');
      // Update all fields in one request
      const updateData = {
        customer_name: formValues.customer_name,
        customer_email: formValues.customer_email,
        customer_phone: formValues.customer_phone,
        bl_number: formValues.bl_number,
        shipper: formValues.shipper,
        consignee: formValues.consignee,
        port_of_loading: formValues.port_of_loading,
        port_of_discharge: formValues.port_of_discharge,
        container_numbers: formValues.container_numbers,
        service_fee: formValues.service_fee,
        ctn_fee: formValues.ctn_fee,
        payment_link: formValues.payment_link,
        unique_number: formValues.unique_number
      };
      const res = await fetch(`${API_BASE_URL}/api/bills/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(updateData)
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Update failed');
      }
      setSnackbar({ open: true, message: 'Bill updated successfully!', severity: 'success' });
      navigate('/edit-delete-bills');
    } catch (error) {
      console.error('Error updating bill:', error);
      setSnackbar({ open: true, message: error.message || 'Update failed', severity: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <CircularProgress style={{ margin: 40 }} />;

  return (
    <div style={{ maxWidth: 600, margin: '40px auto', padding: 24, background: '#fff', borderRadius: 8 }}>
      <h2>{t('editBill')}</h2>
      <form onSubmit={onSubmit}>
        <TextField label={t('customerName')} name="customer_name" value={formValues.customer_name || ''} onChange={handleChange} fullWidth margin="normal" />
        <TextField label={t('customerEmail')} name="customer_email" value={formValues.customer_email || ''} onChange={handleChange} fullWidth margin="normal" />
        <TextField label={t('customerPhone')} name="customer_phone" value={formValues.customer_phone || ''} onChange={handleChange} fullWidth margin="normal" />
        <TextField label={t('blNumber')} name="bl_number" value={formValues.bl_number || ''} onChange={handleChange} fullWidth margin="normal" />
        <TextField label={t('shipper')} name="shipper" value={formValues.shipper || ''} onChange={handleChange} fullWidth margin="normal" />
        <TextField label={t('consignee')} name="consignee" value={formValues.consignee || ''} onChange={handleChange} fullWidth margin="normal" />
        <TextField label={t('portOfLoading')} name="port_of_loading" value={formValues.port_of_loading || ''} onChange={handleChange} fullWidth margin="normal" />
        <TextField label={t('portOfDischarge')} name="port_of_discharge" value={formValues.port_of_discharge || ''} onChange={handleChange} fullWidth margin="normal" />
        <TextField label={t('containerNumbers')} name="container_numbers" value={formValues.container_numbers || ''} onChange={handleChange} fullWidth margin="normal" />
        <TextField label={t('serviceFee')} name="service_fee" value={formValues.service_fee || ''} onChange={handleChange} fullWidth margin="normal" type="number" />
        <TextField label={t('ctnFee')} name="ctn_fee" value={formValues.ctn_fee || ''} onChange={handleChange} fullWidth margin="normal" type="number" />
        <TextField label={t('paymentLink')} name="payment_link" value={formValues.payment_link || ''} onChange={handleChange} fullWidth margin="normal" />
        <TextField label={t('uniqueNumber')} name="unique_number" value={formValues.unique_number || ''} onChange={handleChange} fullWidth margin="normal" />
        <div style={{ marginTop: 16 }}>
          <Button type="submit" variant="contained" color="primary" disabled={submitting}>{t('save')}</Button>
          <Button style={{ marginLeft: 8 }} onClick={() => navigate('/edit-delete-bills')}>{t('cancel')}</Button>
        </div>
      </form>
      
      {/* Loading Modal for Saving */}
      <LoadingModal 
        open={submitting} 
        message={t('savingData')} 
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

export default EditBill;
