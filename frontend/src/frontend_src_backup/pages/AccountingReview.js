import React, { useEffect, useState } from 'react';
import { Button, Modal, Table, Input } from 'antd';
import { Snackbar, Alert } from '@mui/material';
import { API_BASE_URL } from '../config';
import { useNavigate } from 'react-router-dom';
import LoadingModal from '../components/LoadingModal';

function AccountingReview({ t = x => x }) {
  const [bills, setBills] = useState([]);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [confirmModal, setConfirmModal] = useState({ visible: false, record: null });
  const [uniqueEmailModalVisible, setUniqueEmailModalVisible] = useState(false);
  const [uniqueEmailBody, setUniqueEmailBody] = useState('');
  const [uniqueEmailTo, setUniqueEmailTo] = useState('');
  const [uniqueEmailSubject, setUniqueEmailSubject] = useState('');
  const [uniqueSending, setUniqueSending] = useState(false);
  const [blSearch, setBlSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [currentRecord, setCurrentRecord] = useState(null);
  const navigate = useNavigate();
  const role = localStorage.getItem('role');

  // Fetch bills with status 'Awaiting Bank In'
  const fetchBills = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      if (!token) throw new Error('Authentication token not found');
      const response = await fetch(`${API_BASE_URL}/api/bills/awaiting_bank_in`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      // The new endpoint returns an array directly, no need for filtering
      setBills(Array.isArray(data) ? data : []);
    } catch (error) {
      setSnackbar({ open: true, message: error.message, severity: 'error' });
      setBills([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchBills(); }, []);

  // Filtered bills by search
  const filteredBills = bills.filter(bill =>
    (!blSearch || (bill.bl_number || '').toLowerCase().includes(blSearch.toLowerCase()))
  );

  // B/L number search handler
  const handleBlSearch = () => {
    // The search is already real-time, but we can add additional logic here if needed
    // For now, just trigger a re-render
    setBills([...bills]);
  };

  // Clear B/L search
  const handleClearBlSearch = () => {
    setBlSearch('');
  };

  // Complete handler with confirmation
  const handleComplete = async (record) => {
    setConfirmModal({ visible: true, record });
  };

  const confirmComplete = async () => {
    const record = confirmModal.record;
    setConfirmModal({ visible: false, record: null });
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_BASE_URL}/api/bill/${record.id}/complete`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Failed to mark as completed');
      setSnackbar({ open: true, message: t('markedCompleted'), severity: 'success' });
      fetchBills();
    } catch (err) {
      setSnackbar({ open: true, message: err.message, severity: 'error' });
    } finally {
      setSaving(false);
    }
  };

  // Send CTN Number logic (copied from Review.js)
  const handleSendUniqueNumber = (record) => {
    setCurrentRecord(record); // Store the current record
    setUniqueEmailTo(record.customer_email);
    setUniqueEmailSubject(t('uniqueNumberSubject'));
    setUniqueEmailBody(t('uniqueNumberBody', { name: record.customer_name, number: record.unique_number }) || `Dear ${record.customer_name}, your CTN Number is ${record.unique_number}`);
    setUniqueEmailModalVisible(true);
  };

  const handleSendUniqueEmail = async () => {
    setUniqueSending(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/send_unique_number_email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to_email: uniqueEmailTo,
          subject: uniqueEmailSubject,
          body: uniqueEmailBody,
          bill_id: currentRecord?.id // Use the stored current record
        })
      });
      const data = await res.json();
      if (res.ok) {
        setSnackbar({ open: true, message: t('uniqueEmailSent'), severity: 'success' });
        setUniqueEmailModalVisible(false);
        setCurrentRecord(null); // Clear the stored record
      } else {
        setSnackbar({ open: true, message: data.error || t('emailFailed'), severity: 'error' });
      }
    } catch (err) {
      setSnackbar({ open: true, message: t('emailFailed'), severity: 'error' });
    } finally {
      setUniqueSending(false);
    }
  };

  // CTN Number column logic (reuse from Review.js)
  const renderCTNNumber = (text, record) => (
    <>
      {text}
      {role === 'staff' && (
        <Button onClick={() => handleSendUniqueNumber(record)} style={{ marginLeft: 8 }}>
          Send CTN Number
        </Button>
      )}
    </>
  );

  const columns = [
    { title: t('blNumber'), dataIndex: 'bl_number', key: 'bl_number' },
    { title: t('receiptUploadedAt'), dataIndex: 'receipt_uploaded_at', key: 'receipt_uploaded_at', render: (text) => text ? new Date(text).toLocaleString() : '' },
    { title: t('ctnNumber'), dataIndex: 'unique_number', key: 'unique_number', render: renderCTNNumber },
    {
      title: t('complete'),
      key: 'complete',
      render: (_, record) => (
        role === 'staff' ? (
          <Button type="primary" onClick={() => handleComplete(record)}>
            {t('complete')}
          </Button>
        ) : null
      )
    }
  ];

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '20px' }}>
      {/* Top row with back button, header, and search */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        {/* Back button on left */}
        <Button
          variant="contained"
          color="primary"
          style={{ color: '#fff', backgroundColor: '#1976d2' }}
          onClick={() => navigate('/dashboard')}
        >
          {t('backToDashboard')}
        </Button>
        
        {/* Header in center */}
        <h2 style={{ margin: 0, textAlign: 'center', flex: 1 }}>{t('accountSettlementPage')}</h2>
        
        {/* Search field on right */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Input
            placeholder={t('searchBlNumber')}
            value={blSearch}
            onChange={e => setBlSearch(e.target.value)}
            style={{ width: 200 }}
            allowClear
          />
          <Button type="primary" onClick={handleBlSearch}>{t('search')}</Button>
          <Button onClick={handleClearBlSearch}>{t('clear')}</Button>
        </div>
      </div>
      
      <Table dataSource={filteredBills} columns={columns} rowKey="id" loading={loading} />
      
      {/* Loading Modals */}
      <LoadingModal 
        open={loading} 
        message={t('loadingData')} 
      />
      
      <LoadingModal 
        open={saving} 
        message={t('savingData')} 
      />
      
      <LoadingModal 
        open={uniqueSending} 
        message={t('sendingEmail')} 
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
      <Modal
        open={confirmModal.visible}
        onCancel={() => setConfirmModal({ visible: false, record: null })}
        onOk={confirmComplete}
        okText={t('yes')}
        cancelText={t('no')}
        title={t('haveYouSentCtnEmail')}
      >
        <div>{t('confirmCompleteBill')}</div>
      </Modal>
      <Modal
        open={uniqueEmailModalVisible}
        onCancel={() => {
          setUniqueEmailModalVisible(false);
          setCurrentRecord(null); // Clear the stored record when canceling
        }}
        onOk={handleSendUniqueEmail}
        okText={t('send')}
        cancelText={t('cancel')}
        title={t('verifyUniqueNumberEmail')}
        confirmLoading={uniqueSending}
      >
        <div>
          <div><strong>{t('to')}:</strong> {uniqueEmailTo}</div>
          <div><strong>{t('subject')}:</strong> {uniqueEmailSubject}</div>
          <div style={{ margin: '12px 0' }}>
            <strong>{t('emailBody')}:</strong>
            <textarea
              value={uniqueEmailBody}
              onChange={e => setUniqueEmailBody(e.target.value)}
              rows={6}
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default AccountingReview; 