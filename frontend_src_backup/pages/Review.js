import React, { useEffect, useState } from 'react';
import { Button, Input, Modal, Upload, Table, Space, Card, DatePicker, Typography, Select } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { Snackbar, Alert } from '@mui/material';
import { API_BASE_URL } from '../config';
import LoadingModal from '../components/LoadingModal';
const { Link } = Typography;

console.log('Review component rendered');

function Review({ t = x => x }) {
  const [bills, setBills] = useState([]);
  const [selected, setSelected] = useState(null);
  const [fields, setFields] = useState({});
  const [serviceFee, setServiceFee] = useState('');
  const [ctnFee, setCtnFee] = useState('');
  const [paymentLink, setPaymentLink] = useState('');
  const [modalVisible, setModalVisible] = useState(false);
  const [uniqueNumber, setUniqueNumber] = useState('');
  const [blSearch, setBlSearch] = useState('');
  const [filteredBills, setFilteredBills] = useState(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();

  // For invoice email modal
  const [emailModalVisible, setEmailModalVisible] = useState(false);
  const [emailBody, setEmailBody] = useState('');
  const [emailTo, setEmailTo] = useState('');
  const [emailSubject, setEmailSubject] = useState('');
  const [emailPdfUrl, setEmailPdfUrl] = useState('');
  const [sendingEmail, setSendingEmail] = useState(false);

  // For unique number email modal
  const [uniqueEmailModalVisible, setUniqueEmailModalVisible] = useState(false);
  const [uniqueEmailBody, setUniqueEmailBody] = useState('');
  const [uniqueEmailTo, setUniqueEmailTo] = useState('');
  const [uniqueEmailSubject, setUniqueEmailSubject] = useState('');
  const [uniqueSending, setUniqueSending] = useState(false);

  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  // Filter bills by status
  const statusOptions = [
    { label: t('pending'), value: t('pending') },
    { label: t('invoiceSent'), value: t('invoiceSent') },
    { label: t('awaitingBankIn'), value: t('awaitingBankIn') },
    { label: t('paidAndCtnValid'), value: t('paidAndCtnValid') },
  ];
  const billsToShow = (filteredBills !== null ? filteredBills : bills).filter(bill =>
    !statusFilter || bill.status === statusFilter
  );

  // 获取所有提单
  const fetchBills = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
        navigate('/login');
        return;
      }

      const response = await fetch(`${API_BASE_URL}/api/bills`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      if (response.status === 401) {
        setSnackbar({ open: true, message: 'Session expired. Please log in again.', severity: 'error' });
        localStorage.clear();
        navigate('/login');
        return;
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log('Raw response data:', data);
      
      // Handle both formats: array of bills or object with bills and summary
      const billsArray = Array.isArray(data) 
        ? data 
        : data.bills || [];
      
      console.log('Processed bills:', billsArray);
      setBills(billsArray);
    } catch (error) {
      console.error('Error fetching bills:', error);
      setSnackbar({ open: true, message: error.message, severity: 'error' });
      setBills([]); // Set to empty array on error
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    console.log('useEffect running');
    fetchBills();
  }, []);

  // BL number search handler
  const handleBlSearch = () => {
    if (!blSearch) {
      setFilteredBills(null);
      return;
    }
    setFilteredBills(bills.filter(bill => (bill.bl_number || '').toLowerCase().includes(blSearch.toLowerCase())));
  };

  const showModal = (record) => {
    setSelected(record);
    setFields({
      shipper: record.shipper || '',
      consignee: record.consignee || '',
      port_of_loading: record.port_of_loading || '',
      port_of_discharge: record.port_of_discharge || '',
      bl_number: record.bl_number || '',
      container_numbers: record.container_numbers || ''
    });
    setServiceFee(record.service_fee || '');
    setCtnFee(record.ctn_fee || '');
    setPaymentLink(record.payment_link || '');
    setUniqueNumber(record.unique_number || '');
    setModalVisible(true);
  };

  const handleFieldChange = (key, value) => {
    setFields({ ...fields, [key]: value });
  };

  const handleOk = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
        navigate('/login');
        return;
      }

      // First update the basic bill information
      const updateData = {
        ...fields,
      };
      const res = await fetch(`${API_BASE_URL}/api/bills/${selected.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(updateData)
      });
      
      if (res.status === 401) {
        setSnackbar({ open: true, message: 'Session expired. Please log in again.', severity: 'error' });
        localStorage.clear();
        navigate('/login');
        return;
      }
      
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || t('failed'));
      }

      // Then update service fee, CTN fee, payment link and generate invoice
      const feeUpdateData = {
        service_fee: serviceFee,
        ctn_fee: ctnFee,
        payment_link: paymentLink,
        unique_number: uniqueNumber
      };

      const feeRes = await fetch(`${API_BASE_URL}/api/bill/${selected.id}/service_fee`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(feeUpdateData)
      });

      if (feeRes.status === 401) {
        setSnackbar({ open: true, message: 'Session expired. Please log in again.', severity: 'error' });
        localStorage.clear();
        navigate('/login');
        return;
      }

      const feeData = await feeRes.json();
      if (feeRes.ok) {
        setSnackbar({ open: true, message: t('success'), severity: 'success' });
        setModalVisible(false);
        fetchBills();
      } else {
        setSnackbar({ open: true, message: feeData.error || t('failed'), severity: 'error' });
      }
    } catch (err) {
      console.error('Error updating bill:', err);
      setSnackbar({ open: true, message: err.message || t('failed'), severity: 'error' });
    } finally {
      setSaving(false);
    }
  };

  // 上传收据
  const handleUpload = async (file, record) => {
    const formData = new FormData();
    formData.append('receipt', file);
    await fetch(`${API_BASE_URL}/api/bill/${record.id}/upload_receipt`, {
      method: 'POST',
      body: formData
    });
    setSnackbar({ open: true, message: t('receiptUploadSuccess'), severity: 'success' });
    fetchBills();
  };

  // Show email modal for invoice
  const showEmailModal = (record) => {
    console.log('Show invoice email modal');
    setEmailTo(record.customer_email);
    setEmailSubject(t('invoiceSubject'));
    const ctnFeeVal = record.ctn_fee || 0;
    const serviceFeeVal = record.service_fee || 0;
    const total = (parseFloat(ctnFeeVal) + parseFloat(serviceFeeVal)).toFixed(2);
    setEmailBody(
      `Dear ${record.customer_name},\n\nPlease find your invoice attached.\nCTN Fee: $${ctnFeeVal}\nService Fee: $${serviceFeeVal}\nTotal Amount: $${total}\n\nPlease follow the below link to make the payment:\n${record.payment_link || ''}\n\nThank you!`
    );
    setEmailPdfUrl(`${API_BASE_URL}/uploads/${record.invoice_filename}`);
    setSelected(record);
    setEmailModalVisible(true);
  };

  // Send invoice email after staff verification
  const handleSendInvoiceEmail = async () => {
    setSendingEmail(true);
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
        navigate('/login');
        return;
      }

      const res = await fetch(`${API_BASE_URL}/api/send_invoice_email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          to_email: emailTo,
          subject: emailSubject,
          body: emailBody,
          pdf_url: emailPdfUrl,
          bill_id: selected.id
        })
      });

      if (res.status === 401) {
        setSnackbar({ open: true, message: 'Session expired. Please log in again.', severity: 'error' });
        localStorage.clear();
        navigate('/login');
        return;
      }

      const data = await res.json();
      if (res.ok) {
        setSnackbar({ open: true, message: t('emailSent'), severity: 'success' });
        setEmailModalVisible(false);
        fetchBills();
      } else {
        setSnackbar({ open: true, message: data.error || t('emailFailed'), severity: 'error' });
      }
    } catch (err) {
      setSnackbar({ open: true, message: t('emailFailed'), severity: 'error' });
    } finally {
      setSendingEmail(false);
    }
  };

  // Show unique number email modal
  const showUniqueEmailModal = (record) => {
    setSelected(record);
    setUniqueEmailTo(record.customer_email);
    setUniqueEmailSubject(t('uniqueNumberSubject'));
    setUniqueEmailBody(t('uniqueNumberBody', { name: record.customer_name, number: record.unique_number }));
    setUniqueEmailModalVisible(true);
  };

  // Send unique number email
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
          bill_id: selected.id
        })
      });
      const data = await res.json();
      if (res.ok) {
        setSnackbar({ open: true, message: t('uniqueEmailSent'), severity: 'success' });
        setUniqueEmailModalVisible(false);
      } else {
        setSnackbar({ open: true, message: data.error || t('emailFailed'), severity: 'error' });
      }
    } catch (err) {
      setSnackbar({ open: true, message: t('emailFailed'), severity: 'error' });
    } finally {
      setUniqueSending(false);
    }
  };

  // Send CTN Number logic
  const handleSendUniqueNumber = (record) => {
    showUniqueEmailModal(record);
  };

  const columns = [
    { title: t('customerName'), dataIndex: 'customer_name', key: 'customer_name' },
    { title: t('blNumber'), dataIndex: 'bl_number', key: 'bl_number' },
    {
      title: t('shipperConsignee'),
      key: 'shipperConsignee',
      render: (_, record) => (
        <div>
          <div>{record.shipper}</div>
          <div>{record.consignee}</div>
        </div>
      ),
    },
    { title: t('status'), dataIndex: 'status', key: 'status' },
    {
      title: t('edit'),
      key: 'edit',
      width: 80,
      render: (_, record) => (
        <Button size="small" onClick={() => showModal(record)}>{t('edit')}</Button>
      ),
    },
    {
      title: t('invoice'),
      key: 'invoice',
      width: 120,
      render: (_, record) => record.invoice_filename ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Link
            href={`${API_BASE_URL}/uploads/${record.invoice_filename}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Button size="small">{t('viewInvoice')}</Button>
          </Link>
          <Button
            size="small"
            type="primary"
            onClick={() => showEmailModal(record)}
          >
            {t('sendInvoice')}
          </Button>
        </div>
      ) : t('noInvoice'),
    },
    {
      title: t('ctnServiceFee'),
      key: 'ctnServiceFee',
      render: (_, record) => (
        <span>{record.ctn_fee || 0} / {record.service_fee || 0}</span>
      ),
    },
    {
      title: t('uploadReceipt'),
      key: 'uploadReceipt',
      width: 120,
      render: (_, record) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Upload
            showUploadList={false}
            customRequest={({ file, onSuccess, onError }) => {
              handleUpload(file, record)
                .then(() => onSuccess && onSuccess())
                .catch(onError);
            }}
          >
            <Button size="small">{t('uploadReceipt')}</Button>
          </Upload>
          {record.receipt_filename && (
            <Link
              href={`${API_BASE_URL}/uploads/${record.receipt_filename}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button size="small">{t('viewReceipt')}</Button>
            </Link>
          )}
        </div>
      ),
    },
    {
      title: t('ctnNumber'),
      dataIndex: 'unique_number',
      key: 'unique_number',
      width: 120,
      render: (text, record) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span>{text}</span>
          <Button
            size="small"
            onClick={() => handleSendUniqueNumber(record)}
          >
            {t('sendCtnNumber')}
          </Button>
        </div>
      ),
    },
    {
      title: <span>Customer<br/>Document</span>,
      key: 'customerDocument',
      width: 120,
      render: (_, record) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Button
            size="small"
            disabled={!record.customer_invoice}
            href={record.customer_invoice ? `${API_BASE_URL}/uploads/${record.customer_invoice}` : undefined}
            target="_blank"
            rel="noopener noreferrer"
          >
            {t('invoice')}
          </Button>
          <Button
            size="small"
            disabled={!record.customer_packing_list}
            href={record.customer_packing_list ? `${API_BASE_URL}/uploads/${record.customer_packing_list}` : undefined}
            target="_blank"
            rel="noopener noreferrer"
          >
            {t('packingList')}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Button
          variant="contained"
          color="primary"
          style={{ color: '#fff', backgroundColor: '#1976d2' }}
          onClick={() => navigate('/dashboard')}
        >
          {t('backToDashboard')}
        </Button>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Input
            placeholder={t('blNumber')}
            value={blSearch}
            onChange={e => setBlSearch(e.target.value)}
            style={{ width: 200 }}
            allowClear
          />
          <Button type="primary" onClick={handleBlSearch}>{t('search')}</Button>
          <Button onClick={() => { setBlSearch(''); setFilteredBills(null); }}>{t('cancel')}</Button>
          <Select
            placeholder={t('filterByStatus')}
            style={{ width: 180 }}
            value={statusFilter || undefined}
            onChange={setStatusFilter}
            allowClear
            options={statusOptions}
          />
        </div>
      </div>
      <h2>{t('billReview')}</h2>
      
      {billsToShow.length > 0 ? (
        <Table dataSource={billsToShow} columns={columns} rowKey="id" />
      ) : (
        <div style={{ textAlign: 'center', padding: '20px' }}>No data available</div>
      )}
      
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
      {/* Modals */}
      <Modal
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleOk}
        okText={t('save')}
        cancelText={t('cancel')}
        title={t('editBill')}
        width={1100}
      >
        {selected && (
          <div style={{ display: 'flex', gap: 24 }}>
            <iframe
              src={`${API_BASE_URL}/uploads/${selected.pdf_filename}`}
              width="100%"
              height="500px"
              title={t('pdfPreview')}
            />
            <div style={{ flex: 1 }}>
              <div>
                <b>{t('shipper')}:</b>
                <Input.TextArea
                  value={fields.shipper}
                  onChange={e => handleFieldChange('shipper', e.target.value)}
                  autoSize={{ minRows: 2, maxRows: 4 }}
                />
              </div>
              <div>
                <b>{t('consignee')}:</b>
                <Input.TextArea
                  value={fields.consignee}
                  onChange={e => handleFieldChange('consignee', e.target.value)}
                  autoSize={{ minRows: 2, maxRows: 4 }}
                />
              </div>
              <div>
                <b>{t('portOfLoading')}:</b>
                <Input
                  value={fields.port_of_loading}
                  onChange={e => handleFieldChange('port_of_loading', e.target.value)}
                />
              </div>
              <div>
                <b>{t('portOfDischarge')}:</b>
                <Input
                  value={fields.port_of_discharge}
                  onChange={e => handleFieldChange('port_of_discharge', e.target.value)}
                />
              </div>
              <div>
                <b>{t('blNumber')}:</b>
                <Input
                  value={fields.bl_number}
                  onChange={e => handleFieldChange('bl_number', e.target.value)}
                />
              </div>
              <div>
                <b>{t('containerNumbers')}:</b>
                <Input
                  value={fields.container_numbers}
                  onChange={e => handleFieldChange('container_numbers', e.target.value)}
                />
              </div>
              <Input
                style={{ width: 200, marginTop: 16 }}
                addonBefore={t('ctnFee') + '(USD)'}
                value={ctnFee}
                onChange={e => setCtnFee(e.target.value)}
              />
              <Input
                style={{ width: 200, marginTop: 16 }}
                addonBefore={t('serviceFee') + '(USD)'}
                value={serviceFee}
                onChange={e => setServiceFee(e.target.value)}
              />
              <Input
                style={{ width: 200, marginTop: 16 }}
                addonBefore={t('paymentLink')}
                value={paymentLink}
                onChange={e => setPaymentLink(e.target.value)}
                placeholder="https://..."
              />
              <Input
                value={uniqueNumber}
                onChange={e => setUniqueNumber(e.target.value)}
                placeholder={t('ctnNumber')}
              />
            </div>
          </div>
        )}
      </Modal>
      <Modal
        open={emailModalVisible}
        onCancel={() => setEmailModalVisible(false)}
        onOk={handleSendInvoiceEmail}
        okText={t('send')}
        cancelText={t('cancel')}
        title={t('verifyInvoiceEmail')}
        confirmLoading={sendingEmail}
      >
        <div>
          <div><strong>{t('to')}:</strong> {emailTo}</div>
          <div><strong>{t('subject')}:</strong> {emailSubject}</div>
          <div style={{ margin: '12px 0' }}>
            <strong>{t('emailBody')}:</strong>
            <Input.TextArea
              value={emailBody}
              onChange={e => setEmailBody(e.target.value)}
              autoSize={{ minRows: 6 }}
            />
          </div>
          <div>
            <Link 
              href={emailPdfUrl}
              target="_blank" 
              rel="noopener noreferrer"
              style={{ textDecoration: 'none' }}
            >
              <Button variant="outlined" size="small">
                {t('previewPDF')}
              </Button>
            </Link>
          </div>
        </div>
      </Modal>
      <Modal
        open={uniqueEmailModalVisible}
        onCancel={() => setUniqueEmailModalVisible(false)}
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
            <Input.TextArea
              value={uniqueEmailBody}
              onChange={e => setUniqueEmailBody(e.target.value)}
              autoSize={{ minRows: 6 }}
            />
          </div>
        </div>
      </Modal>
      <LoadingModal open={loading} message={t('loadingData')} />
      <LoadingModal open={saving} message={t('savingData')} />
      <LoadingModal open={sendingEmail} message={t('sendingEmail')} />
      <LoadingModal open={uniqueSending} message={t('sendingEmail')} />
    </div>
  );
}

export default Review; 