import React, { useEffect, useState } from 'react';
import { Button, Modal, Table, Input, Pagination } from 'antd';
import { Snackbar, Alert } from '@mui/material';
import { API_BASE_URL } from '../config';
import { useNavigate } from 'react-router-dom';
import LoadingModal from '../components/LoadingModal';

function AccountingReview({ t = x => x }) {
  const [allBills, setAllBills] = useState([]);
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
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [total, setTotal] = useState(0);
  const [role, setRole] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    // Fetch user info from backend if needed
    const fetchUser = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/me`, { credentials: 'include' });
        if (res.ok) {
          const data = await res.json();
          setRole(data.role);
        }
      } catch {}
    };
    fetchUser();
    fetchBills();
  }, []);

  // Fetch all bills once
  const fetchBills = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/bills/awaiting_bank_in`, {
        credentials: 'include'
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      setAllBills(data.bills || []);
    } catch (error) {
      setSnackbar({ open: true, message: error.message, severity: 'error' });
      setAllBills([]);
    } finally {
      setLoading(false);
    }
  };

  // Filter bills as user types or changes page/pageSize
  useEffect(() => {
    // Only show bills with status "Awaiting Bank In" or (Allinpay + Paid 85%)
    let filtered = allBills.filter(bill =>
      bill.status === 'Awaiting Bank In' ||
      (bill.payment_method && bill.payment_method.toLowerCase() === 'allinpay' && bill.payment_status === 'Paid 85%')
    );
    if (blSearch) {
      filtered = filtered.filter(bill =>
        bill.bl_number && bill.bl_number.toLowerCase().includes(blSearch.toLowerCase())
      );
    }
    setTotal(filtered.length);
    // Pagination logic
    const startIdx = (page - 1) * pageSize;
    setBills(filtered.slice(startIdx, startIdx + pageSize));
  }, [allBills, blSearch, page, pageSize]);

  const handleClearBlSearch = () => {
    setBlSearch('');
    setPage(1);
  };

  const handlePageChange = (newPage, newPageSize) => {
    setPage(newPage);
    setPageSize(newPageSize);
  };

  const handleComplete = async (record) => {
    setConfirmModal({ visible: true, record });
  };

  const confirmComplete = async () => {
    const record = confirmModal.record;
    setConfirmModal({ visible: false, record: null });
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/bill/${record.id}/complete`, {
        method: 'POST',
        credentials: 'include'
      });
      if (!res.ok) throw new Error('Failed to mark as completed');
      setSnackbar({ open: true, message: t('markedCompleted'), severity: 'success' });
      await fetchBills();
    } catch (err) {
      setSnackbar({ open: true, message: err.message, severity: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleSendUniqueNumber = (record) => {
    setCurrentRecord(record);
    setUniqueEmailTo(record.customer_email);
    setUniqueEmailSubject(t('uniqueNumberSubject'));
    setUniqueEmailBody(`Dear ${record.customer_name},

Your unique number for customs declaration is: ${record.unique_number}

Thank you.`);
    setUniqueEmailModalVisible(true);
  };

  const handleSendUniqueEmail = async () => {
    setUniqueSending(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/send_unique_number_email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          to_email: uniqueEmailTo,
          subject: uniqueEmailSubject,
          body: uniqueEmailBody,
          bill_id: currentRecord?.id
        })
      });
      const data = await res.json();
      if (res.ok) {
        setSnackbar({ open: true, message: t('uniqueEmailSent'), severity: 'success' });
        setUniqueEmailModalVisible(false);
        setCurrentRecord(null);
      } else {
        setSnackbar({ open: true, message: data.error || t('emailFailed'), severity: 'error' });
      }
    } catch (err) {
      setSnackbar({ open: true, message: t('emailFailed'), severity: 'error' });
    } finally {
      setUniqueSending(false);
    }
  };

  const handleSettleReserve = async (record) => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/bill/${record.id}/settle_reserve`, {
        method: 'POST',
        credentials: 'include'
      });
      if (!res.ok) throw new Error('Failed to settle reserve');
      setSnackbar({ open: true, message: 'Reserve marked as settled', severity: 'success' });
      await fetchBills();
    } catch (err) {
      setSnackbar({ open: true, message: err.message, severity: 'error' });
    } finally {
      setSaving(false);
    }
  };

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
      title: t('reserveStatus'),
      key: 'reserve_status',
      dataIndex: 'reserve_status',
      render: (_, record) => (
        record.payment_method &&
        record.payment_method.toLowerCase() === 'allinpay' &&
        record.reserve_status &&
        record.reserve_status.toLowerCase() === 'unsettled' ? (
          <Button onClick={() => handleSettleReserve(record)} type="primary">
            Settle Reserve
          </Button>
        ) : (record.reserve_status || '')
      )
    },
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Button
          variant="contained"
          color="primary"
          style={{ color: '#fff', backgroundColor: '#1976d2' }}
          onClick={() => navigate('/dashboard')}
        >
          {t('backToDashboard')}
        </Button>
        <h2 style={{ margin: 0, textAlign: 'center', flex: 1 }}>{t('accountSettlementPage')}</h2>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Input
            placeholder={t('searchBlNumber')}
            value={blSearch}
            onChange={e => {
              setBlSearch(e.target.value);
              setPage(1);
            }}
            style={{ width: 200 }}
            allowClear
          />
          <Button onClick={handleClearBlSearch}>{t('clear')}</Button>
        </div>
      </div>

      <Table dataSource={bills} columns={columns} rowKey="id" loading={loading} pagination={false} />
      <Pagination
        current={page}
        pageSize={pageSize}
        total={total}
        showSizeChanger
        onChange={handlePageChange}
        onShowSizeChange={handlePageChange}
        style={{ marginTop: 16, textAlign: 'right' }}
      />

      <LoadingModal open={loading} message={t('loadingData')} />
      <LoadingModal open={saving} message={t('savingData')} />
      <LoadingModal open={uniqueSending} message={t('sendingEmail')} />

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
          setCurrentRecord(null);
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





// import React, { useEffect, useState } from 'react';
// import { Button, Modal, Table, Input, Pagination } from 'antd';
// import { Snackbar, Alert } from '@mui/material';
// import { API_BASE_URL } from '../config';
// import { useNavigate } from 'react-router-dom';
// import LoadingModal from '../components/LoadingModal';

// function AccountingReview({ t = x => x }) {
//   const [allBills, setAllBills] = useState([]);
//   const [bills, setBills] = useState([]);
//   const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
//   const [confirmModal, setConfirmModal] = useState({ visible: false, record: null });
//   const [uniqueEmailModalVisible, setUniqueEmailModalVisible] = useState(false);
//   const [uniqueEmailBody, setUniqueEmailBody] = useState('');
//   const [uniqueEmailTo, setUniqueEmailTo] = useState('');
//   const [uniqueEmailSubject, setUniqueEmailSubject] = useState('');
//   const [uniqueSending, setUniqueSending] = useState(false);
//   const [blSearch, setBlSearch] = useState('');
//   const [loading, setLoading] = useState(false);
//   const [saving, setSaving] = useState(false);
//   const [currentRecord, setCurrentRecord] = useState(null);
//   const [page, setPage] = useState(1);
//   const [pageSize, setPageSize] = useState(50);
//   const [total, setTotal] = useState(0);
//   const navigate = useNavigate();
//   const role = localStorage.getItem('role');

//   // Fetch all bills once
//   const fetchBills = async () => {
//     setLoading(true);
//     try {
//       const token = localStorage.getItem('token');
//       if (!token) throw new Error('Authentication token not found');
//       const response = await fetch(`${API_BASE_URL}/api/bills/awaiting_bank_in`, {
//         headers: { Authorization: `Bearer ${token}` }
//       });
//       if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
//       const data = await response.json();
//       setAllBills(data.bills || []);
//     } catch (error) {
//       setSnackbar({ open: true, message: error.message, severity: 'error' });
//       setAllBills([]);
//     } finally {
//       setLoading(false);
//     }
//   };

//   useEffect(() => { fetchBills(); }, []);

//   // Filter bills as user types or changes page/pageSize
//   useEffect(() => {
//     let filtered = allBills;
//     if (blSearch) {
//       filtered = allBills.filter(bill =>
//         bill.bl_number && bill.bl_number.toLowerCase().includes(blSearch.toLowerCase())
//       );
//     }
//     setTotal(filtered.length);
//     // Pagination logic
//     const startIdx = (page - 1) * pageSize;
//     setBills(filtered.slice(startIdx, startIdx + pageSize));
//   }, [allBills, blSearch, page, pageSize]);

//   const handleClearBlSearch = () => {
//     setBlSearch('');
//     setPage(1);
//   };

//   const handlePageChange = (newPage, newPageSize) => {
//     setPage(newPage);
//     setPageSize(newPageSize);
//   };

//   const handleComplete = async (record) => {
//     setConfirmModal({ visible: true, record });
//   };

//   const confirmComplete = async () => {
//     const record = confirmModal.record;
//     setConfirmModal({ visible: false, record: null });
//     setSaving(true);
//     try {
//       const token = localStorage.getItem('token');
//       const res = await fetch(`${API_BASE_URL}/api/bill/${record.id}/complete`, {
//         method: 'POST',
//         headers: { Authorization: `Bearer ${token}` }
//       });
//       if (!res.ok) throw new Error('Failed to mark as completed');
//       setSnackbar({ open: true, message: t('markedCompleted'), severity: 'success' });
//       fetchBills();
//     } catch (err) {
//       setSnackbar({ open: true, message: err.message, severity: 'error' });
//     } finally {
//       setSaving(false);
//     }
//   };

//   const handleSendUniqueNumber = (record) => {
//     setCurrentRecord(record);
//     setUniqueEmailTo(record.customer_email);
//     setUniqueEmailSubject(t('uniqueNumberSubject'));
//     setUniqueEmailBody(`Dear ${record.customer_name},

// Your unique number for customs declaration is: ${record.unique_number}

// Thank you.`);
//     setUniqueEmailModalVisible(true);
//   };

//   const handleSendUniqueEmail = async () => {
//     setUniqueSending(true);
//     try {
//       const res = await fetch(`${API_BASE_URL}/api/send_unique_number_email`, {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({
//           to_email: uniqueEmailTo,
//           subject: uniqueEmailSubject,
//           body: uniqueEmailBody,
//           bill_id: currentRecord?.id
//         })
//       });
//       const data = await res.json();
//       if (res.ok) {
//         setSnackbar({ open: true, message: t('uniqueEmailSent'), severity: 'success' });
//         setUniqueEmailModalVisible(false);
//         setCurrentRecord(null);
//       } else {
//         setSnackbar({ open: true, message: data.error || t('emailFailed'), severity: 'error' });
//       }
//     } catch (err) {
//       setSnackbar({ open: true, message: t('emailFailed'), severity: 'error' });
//     } finally {
//       setUniqueSending(false);
//     }
//   };

//   const handleSettleReserve = async (record) => {
//     setSaving(true);
//     try {
//       const token = localStorage.getItem('token');
//       const res = await fetch(`${API_BASE_URL}/api/bill/${record.id}/settle_reserve`, {
//         method: 'POST',
//         headers: { Authorization: `Bearer ${token}` }
//       });
//       if (!res.ok) throw new Error('Failed to settle reserve');
//       setSnackbar({ open: true, message: 'Reserve marked as settled', severity: 'success' });
//       fetchBills();
//     } catch (err) {
//       setSnackbar({ open: true, message: err.message, severity: 'error' });
//     } finally {
//       setSaving(false);
//     }
//   };

//   const renderCTNNumber = (text, record) => (
//     <>
//       {text}
//       {role === 'staff' && (
//         <Button onClick={() => handleSendUniqueNumber(record)} style={{ marginLeft: 8 }}>
//           Send CTN Number
//         </Button>
//       )}
//     </>
//   );

//   const columns = [
//     { title: t('blNumber'), dataIndex: 'bl_number', key: 'bl_number' },
//     { title: t('receiptUploadedAt'), dataIndex: 'receipt_uploaded_at', key: 'receipt_uploaded_at', render: (text) => text ? new Date(text).toLocaleString() : '' },
//     { title: t('ctnNumber'), dataIndex: 'unique_number', key: 'unique_number', render: renderCTNNumber },
//     {
//       title: t('reserveStatus'),
//       key: 'reserve_status',
//       dataIndex: 'reserve_status',
//       render: (_, record) => (
//         record.payment_method &&
//         record.payment_method.toLowerCase() === 'allinpay' &&
//         record.reserve_status &&
//         record.reserve_status.toLowerCase() === 'unsettled' ? (
//           <Button onClick={() => handleSettleReserve(record)} type="primary">
//             Settle Reserve
//           </Button>
//         ) : (record.reserve_status || '')
//       )
//     },
//     {
//       title: t('complete'),
//       key: 'complete',
//       render: (_, record) => (
//         role === 'staff' ? (
//           <Button type="primary" onClick={() => handleComplete(record)}>
//             {t('complete')}
//           </Button>
//         ) : null
//       )
//     }
//   ];

//   return (
//     <div style={{ maxWidth: 900, margin: '0 auto', padding: '20px' }}>
//       <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
//         <Button
//           variant="contained"
//           color="primary"
//           style={{ color: '#fff', backgroundColor: '#1976d2' }}
//           onClick={() => navigate('/dashboard')}
//         >
//           {t('backToDashboard')}
//         </Button>
//         <h2 style={{ margin: 0, textAlign: 'center', flex: 1 }}>{t('accountSettlementPage')}</h2>
//         <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
//           <Input
//             placeholder={t('searchBlNumber')}
//             value={blSearch}
//             onChange={e => {
//               setBlSearch(e.target.value);
//               setPage(1);
//             }}
//             style={{ width: 200 }}
//             allowClear
//           />
//           <Button onClick={handleClearBlSearch}>{t('clear')}</Button>
//         </div>
//       </div>

//       <Table dataSource={bills} columns={columns} rowKey="id" loading={loading} pagination={false} />
//       <Pagination
//         current={page}
//         pageSize={pageSize}
//         total={total}
//         showSizeChanger
//         onChange={handlePageChange}
//         onShowSizeChange={handlePageChange}
//         style={{ marginTop: 16, textAlign: 'right' }}
//       />

//       <LoadingModal open={loading} message={t('loadingData')} />
//       <LoadingModal open={saving} message={t('savingData')} />
//       <LoadingModal open={uniqueSending} message={t('sendingEmail')} />

//       <Snackbar
//         open={snackbar.open}
//         autoHideDuration={4000}
//         onClose={() => setSnackbar({ ...snackbar, open: false })}
//         anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
//       >
//         <Alert onClose={() => setSnackbar({ ...snackbar, open: false })} severity={snackbar.severity} sx={{ width: '100%' }}>
//           {snackbar.message}
//         </Alert>
//       </Snackbar>

//       <Modal
//         open={confirmModal.visible}
//         onCancel={() => setConfirmModal({ visible: false, record: null })}
//         onOk={confirmComplete}
//         okText={t('yes')}
//         cancelText={t('no')}
//         title={t('haveYouSentCtnEmail')}
//       >
//         <div>{t('confirmCompleteBill')}</div>
//       </Modal>

//       <Modal
//         open={uniqueEmailModalVisible}
//         onCancel={() => {
//           setUniqueEmailModalVisible(false);
//           setCurrentRecord(null);
//         }}
//         onOk={handleSendUniqueEmail}
//         okText={t('send')}
//         cancelText={t('cancel')}
//         title={t('verifyUniqueNumberEmail')}
//         confirmLoading={uniqueSending}
//       >
//         <div>
//           <div><strong>{t('to')}:</strong> {uniqueEmailTo}</div>
//           <div><strong>{t('subject')}:</strong> {uniqueEmailSubject}</div>
//           <div style={{ margin: '12px 0' }}>
//             <strong>{t('emailBody')}:</strong>
//             <textarea
//               value={uniqueEmailBody}
//               onChange={e => setUniqueEmailBody(e.target.value)}
//               rows={6}
//               style={{ width: '100%' }}
//             />
//           </div>
//         </div>
//       </Modal>
//     </div>
//   );
// }

// export default AccountingReview;







// // import React, { useEffect, useState } from 'react';
// // import { Button, Modal, Table, Input, Pagination } from 'antd';
// // import { Snackbar, Alert } from '@mui/material';
// // import { API_BASE_URL } from '../config';
// // import { useNavigate } from 'react-router-dom';
// // import LoadingModal from '../components/LoadingModal';

// // function AccountingReview({ t = x => x }) {
// //   const [bills, setBills] = useState([]);
// //   const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
// //   const [confirmModal, setConfirmModal] = useState({ visible: false, record: null });
// //   const [uniqueEmailModalVisible, setUniqueEmailModalVisible] = useState(false);
// //   const [uniqueEmailBody, setUniqueEmailBody] = useState('');
// //   const [uniqueEmailTo, setUniqueEmailTo] = useState('');
// //   const [uniqueEmailSubject, setUniqueEmailSubject] = useState('');
// //   const [uniqueSending, setUniqueSending] = useState(false);
// //   const [blSearch, setBlSearch] = useState('');
// //   const [loading, setLoading] = useState(false);
// //   const [saving, setSaving] = useState(false);
// //   const [currentRecord, setCurrentRecord] = useState(null);
// //   const [page, setPage] = useState(1);
// //   const [pageSize, setPageSize] = useState(50);
// //   const [total, setTotal] = useState(0);
// //   const navigate = useNavigate();
// //   const role = localStorage.getItem('role');

// //   const fetchBills = async (params = {}) => {
// //     setLoading(true);
// //     try {
// //       const token = localStorage.getItem('token');
// //       if (!token) throw new Error('Authentication token not found');
// //       const query = new URLSearchParams({
// //         page: params.page || page,
// //         page_size: params.pageSize || pageSize,
// //         bl_number: params.blSearch !== undefined ? params.blSearch : blSearch
// //       });
// //       const response = await fetch(`${API_BASE_URL}/api/bills/awaiting_bank_in?${query.toString()}`, {
// //         headers: { Authorization: `Bearer ${token}` }
// //       });
// //       if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
// //       const data = await response.json();
// //       setBills(data.bills || []);
// //       setTotal(data.total || 0);
// //       setPage(data.page || 1);
// //       setPageSize(data.page_size || 50);
// //     } catch (error) {
// //       setSnackbar({ open: true, message: error.message, severity: 'error' });
// //       setBills([]);
// //       setTotal(0);
// //     } finally {
// //       setLoading(false);
// //     }
// //   };

// //   useEffect(() => { fetchBills({ page: 1 }); }, []);

// //   const handleBlSearch = () => {
// //     setPage(1);
// //     fetchBills({ page: 1, blSearch });
// //   };

// //   const handleClearBlSearch = () => {
// //     setBlSearch('');
// //     setPage(1);
// //     fetchBills({ page: 1 });
// //   };

// //   const handlePageChange = (newPage, newPageSize) => {
// //     setPage(newPage);
// //     setPageSize(newPageSize);
// //     fetchBills({ page: newPage, pageSize: newPageSize });
// //   };

// //   const handleComplete = async (record) => {
// //     setConfirmModal({ visible: true, record });
// //   };

// //   const confirmComplete = async () => {
// //     const record = confirmModal.record;
// //     setConfirmModal({ visible: false, record: null });
// //     setSaving(true);
// //     try {
// //       const token = localStorage.getItem('token');
// //       const res = await fetch(`${API_BASE_URL}/api/bill/${record.id}/complete`, {
// //         method: 'POST',
// //         headers: { Authorization: `Bearer ${token}` }
// //       });
// //       if (!res.ok) throw new Error('Failed to mark as completed');
// //       setSnackbar({ open: true, message: t('markedCompleted'), severity: 'success' });
// //       fetchBills();
// //     } catch (err) {
// //       setSnackbar({ open: true, message: err.message, severity: 'error' });
// //     } finally {
// //       setSaving(false);
// //     }
// //   };

// //   const handleSendUniqueNumber = (record) => {
// //     setCurrentRecord(record);
// //     setUniqueEmailTo(record.customer_email);
// //     setUniqueEmailSubject(t('uniqueNumberSubject'));
// //     setUniqueEmailBody(`Dear ${record.customer_name},

// // Your unique number for customs declaration is: ${record.unique_number}

// // Thank you.`);
// //     setUniqueEmailModalVisible(true);
// //   };

// //   const handleSendUniqueEmail = async () => {
// //     setUniqueSending(true);
// //     try {
// //       const res = await fetch(`${API_BASE_URL}/api/send_unique_number_email`, {
// //         method: 'POST',
// //         headers: { 'Content-Type': 'application/json' },
// //         body: JSON.stringify({
// //           to_email: uniqueEmailTo,
// //           subject: uniqueEmailSubject,
// //           body: uniqueEmailBody,
// //           bill_id: currentRecord?.id
// //         })
// //       });
// //       const data = await res.json();
// //       if (res.ok) {
// //         setSnackbar({ open: true, message: t('uniqueEmailSent'), severity: 'success' });
// //         setUniqueEmailModalVisible(false);
// //         setCurrentRecord(null);
// //       } else {
// //         setSnackbar({ open: true, message: data.error || t('emailFailed'), severity: 'error' });
// //       }
// //     } catch (err) {
// //       setSnackbar({ open: true, message: t('emailFailed'), severity: 'error' });
// //     } finally {
// //       setUniqueSending(false);
// //     }
// //   };

// //   const handleSettleReserve = async (record) => {
// //     setSaving(true);
// //     try {
// //       const token = localStorage.getItem('token');
// //       const res = await fetch(`${API_BASE_URL}/api/bill/${record.id}/settle_reserve`, {
// //         method: 'POST',
// //         headers: { Authorization: `Bearer ${token}` }
// //       });
// //       if (!res.ok) throw new Error('Failed to settle reserve');
// //       setSnackbar({ open: true, message: 'Reserve marked as settled', severity: 'success' });
// //       fetchBills();
// //     } catch (err) {
// //       setSnackbar({ open: true, message: err.message, severity: 'error' });
// //     } finally {
// //       setSaving(false);
// //     }
// //   };

// //   const renderCTNNumber = (text, record) => (
// //     <>
// //       {text}
// //       {role === 'staff' && (
// //         <Button onClick={() => handleSendUniqueNumber(record)} style={{ marginLeft: 8 }}>
// //           Send CTN Number
// //         </Button>
// //       )}
// //     </>
// //   );

// //   const columns = [
// //     { title: t('blNumber'), dataIndex: 'bl_number', key: 'bl_number' },
// //     { title: t('receiptUploadedAt'), dataIndex: 'receipt_uploaded_at', key: 'receipt_uploaded_at', render: (text) => text ? new Date(text).toLocaleString() : '' },
// //     { title: t('ctnNumber'), dataIndex: 'unique_number', key: 'unique_number', render: renderCTNNumber },
// //     {
// //       title: t('reserveStatus'),
// //       key: 'reserve_status',
// //       dataIndex: 'reserve_status',
// //       render: (_, record) => (
// //         record.payment_method &&
// //         record.payment_method.toLowerCase() === 'allinpay' &&
// //         record.reserve_status &&
// //         record.reserve_status.toLowerCase() === 'unsettled' ? (
// //           <Button onClick={() => handleSettleReserve(record)} type="primary">
// //             Settle Reserve
// //           </Button>
// //         ) : (record.reserve_status || '')
// //       )
// //     },
// //     {
// //       title: t('complete'),
// //       key: 'complete',
// //       render: (_, record) => (
// //         role === 'staff' ? (
// //           <Button type="primary" onClick={() => handleComplete(record)}>
// //             {t('complete')}
// //           </Button>
// //         ) : null
// //       )
// //     }
// //   ];

// //   return (
// //     <div style={{ maxWidth: 900, margin: '0 auto', padding: '20px' }}>
// //       <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
// //         <Button
// //           variant="contained"
// //           color="primary"
// //           style={{ color: '#fff', backgroundColor: '#1976d2' }}
// //           onClick={() => navigate('/dashboard')}
// //         >
// //           {t('backToDashboard')}
// //         </Button>
// //         <h2 style={{ margin: 0, textAlign: 'center', flex: 1 }}>{t('accountSettlementPage')}</h2>
// //         <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
// //           <Input
// //             placeholder={t('searchBlNumber')}
// //             value={blSearch}
// //             onChange={e => setBlSearch(e.target.value)}
// //             style={{ width: 200 }}
// //             allowClear
// //           />
// //           <Button type="primary" onClick={handleBlSearch}>{t('search')}</Button>
// //           <Button onClick={handleClearBlSearch}>{t('clear')}</Button>
// //         </div>
// //       </div>

// //       <Table dataSource={bills} columns={columns} rowKey="id" loading={loading} pagination={false} />
// //       <Pagination
// //         current={page}
// //         pageSize={pageSize}
// //         total={total}
// //         showSizeChanger
// //         onChange={handlePageChange}
// //         onShowSizeChange={handlePageChange}
// //         style={{ marginTop: 16, textAlign: 'right' }}
// //       />

// //       <LoadingModal open={loading} message={t('loadingData')} />
// //       <LoadingModal open={saving} message={t('savingData')} />
// //       <LoadingModal open={uniqueSending} message={t('sendingEmail')} />

// //       <Snackbar
// //         open={snackbar.open}
// //         autoHideDuration={4000}
// //         onClose={() => setSnackbar({ ...snackbar, open: false })}
// //         anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
// //       >
// //         <Alert onClose={() => setSnackbar({ ...snackbar, open: false })} severity={snackbar.severity} sx={{ width: '100%' }}>
// //           {snackbar.message}
// //         </Alert>
// //       </Snackbar>

// //       <Modal
// //         open={confirmModal.visible}
// //         onCancel={() => setConfirmModal({ visible: false, record: null })}
// //         onOk={confirmComplete}
// //         okText={t('yes')}
// //         cancelText={t('no')}
// //         title={t('haveYouSentCtnEmail')}
// //       >
// //         <div>{t('confirmCompleteBill')}</div>
// //       </Modal>

// //       <Modal
// //         open={uniqueEmailModalVisible}
// //         onCancel={() => {
// //           setUniqueEmailModalVisible(false);
// //           setCurrentRecord(null);
// //         }}
// //         onOk={handleSendUniqueEmail}
// //         okText={t('send')}
// //         cancelText={t('cancel')}
// //         title={t('verifyUniqueNumberEmail')}
// //         confirmLoading={uniqueSending}
// //       >
// //         <div>
// //           <div><strong>{t('to')}:</strong> {uniqueEmailTo}</div>
// //           <div><strong>{t('subject')}:</strong> {uniqueEmailSubject}</div>
// //           <div style={{ margin: '12px 0' }}>
// //             <strong>{t('emailBody')}:</strong>
// //             <textarea
// //               value={uniqueEmailBody}
// //               onChange={e => setUniqueEmailBody(e.target.value)}
// //               rows={6}
// //               style={{ width: '100%' }}
// //             />
// //           </div>
// //         </div>
// //       </Modal>
// //     </div>
// //   );
// // }

// // export default AccountingReview;
