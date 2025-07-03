import React, { useEffect, useState } from 'react';
import { Button, Input, Modal, Upload, Table, Space, Card, DatePicker, Typography, Select, Pagination } from 'antd';
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
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [total, setTotal] = useState(0);
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
  const billsToShow = bills.filter(bill =>
    !statusFilter || bill.status === statusFilter
  );

  // Fetch bills
  const fetchBills = async (params = {}) => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
        navigate('/login');
        return;
      }
      const query = new URLSearchParams({
        page: params.page || page,
        page_size: params.pageSize || pageSize,
        bl_number: params.blSearch !== undefined ? params.blSearch : blSearch,
        status: params.statusFilter !== undefined ? params.statusFilter : statusFilter
      });
      const response = await fetch(`${API_BASE_URL}/api/bills?${query.toString()}`, {
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
      setBills(data.bills || []);
      setTotal(data.total || 0);
      setPage(data.page || 1);
      setPageSize(data.page_size || 50);
    } catch (error) {
      setSnackbar({ open: true, message: error.message, severity: 'error' });
      setBills([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBills({ page: 1 });
  }, []);

  // BL number search handler
  const handleBlSearch = () => {
    setPage(1);
    fetchBills({ page: 1, blSearch });
  };

  // Status filter handler
  const handleStatusFilter = (value) => {
    setStatusFilter(value);
    setPage(1);
    fetchBills({ page: 1, statusFilter: value });
  };

  // Pagination handler
  const handlePageChange = (newPage, newPageSize) => {
    setPage(newPage);
    setPageSize(newPageSize);
    fetchBills({ page: newPage, pageSize: newPageSize });
  };

  const showModal = (record) => {
    setSelected(record);
    setFields({
      shipper: record.shipper || '',
      consignee: record.consignee || '',
      port_of_loading: record.port_of_loading || '',
      port_of_discharge: record.port_of_discharge || '',
      bl_number: record.bl_number || '',
      container_numbers: record.container_numbers || '',
      flight_or_vessel: record.flight_or_vessel || '',
      product_description: record.product_description || '',
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

      const updateData = {
        ...fields,
        service_fee: serviceFee,
        ctn_fee: ctnFee,
        payment_link: fields.payment_link || paymentLink,
        unique_number: uniqueNumber,
        payment_method: selected?.payment_method || '',
        payment_status: selected?.payment_status || '',
        reserve_status: selected?.reserve_status || ''
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

      setSnackbar({ open: true, message: t('success'), severity: 'success' });
      setModalVisible(false);
      fetchBills();
    } catch (err) {
      console.error('Error updating bill:', err);
      setSnackbar({ open: true, message: err.message || t('failed'), severity: 'error' });
    } finally {
      setSaving(false);
    }
  };

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

  const showUniqueEmailModal = (record) => {
    setSelected(record);
    setUniqueEmailTo(record.customer_email);
    setUniqueEmailSubject(t('uniqueNumberSubject'));
    setUniqueEmailBody(t('uniqueNumberBody', { name: record.customer_name, number: record.unique_number }));
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

  const handleSendUniqueNumber = (record) => {
    showUniqueEmailModal(record);
  };

  const handleGeneratePaymentLink = async () => {
    if (!selected || !uniqueNumber) {
      setSnackbar({ open: true, message: 'Please enter a CTN number.', severity: 'error' });
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/api/generate_payment_link/${selected.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount: 0, // Let backend calculate 15% reserve
          currency: 'USD',
          customer_email: selected.customer_email,
          description: `Reserve payment for CTN ${uniqueNumber}`,
          success_url: 'https://yourdomain.com/success',
          cancel_url: 'https://yourdomain.com/cancel',
        }),
      });

      const data = await res.json();
      if (res.ok && data.payment_link) {
        setFields(prev => ({ ...prev, payment_link: data.payment_link }));
        setPaymentLink(data.payment_link);
        setSnackbar({ open: true, message: 'Payment link generated successfully.', severity: 'success' });
      } else {
        setSnackbar({ open: true, message: `Failed to generate payment link: ${data.error}`, severity: 'error' });
      }
    } catch (err) {
      console.error('Error generating payment link:', err);
      setSnackbar({ open: true, message: `Error generating link: ${err.message}`, severity: 'error' });
    }
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
          <Button onClick={() => { setBlSearch(''); fetchBills({ page: 1 }); }}>{t('cancel')}</Button>
          <Select
            placeholder={t('filterByStatus')}
            style={{ width: 180 }}
            value={statusFilter || undefined}
            onChange={handleStatusFilter}
            allowClear
            options={statusOptions}
          />
        </div>
      </div>
      <h2>{t('billReview')}</h2>
      
      {billsToShow.length > 0 ? (
        <Table dataSource={billsToShow} columns={columns} rowKey="id" pagination={false} />
      ) : (
        <div style={{ textAlign: 'center', padding: '20px' }}>No data available</div>
      )}
      
      <Pagination
        current={page}
        pageSize={pageSize}
        total={total}
        showSizeChanger
        onChange={handlePageChange}
        onShowSizeChange={handlePageChange}
        style={{ marginTop: 16, textAlign: 'right' }}
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
              <div>
                <b>{t('flightOrVessel') || 'Flight or Vessel'}:</b>
                <Input
                  value={fields.flight_or_vessel}
                  onChange={e => handleFieldChange('flight_or_vessel', e.target.value)}
                />
              </div>
              <div>
                <b>{t('productDescription') || 'Product Description'}:</b>
                <Input.TextArea
                  value={fields.product_description}
                  onChange={e => handleFieldChange('product_description', e.target.value)}
                  autoSize={{ minRows: 2, maxRows: 4 }}
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
              <div style={{ marginTop: 16 }}>
                <b>{t('paymentLink') || 'Payment Link'}:</b>{' '}
                {fields.payment_link ? (
                  <a href={fields.payment_link} target="_blank" rel="noopener noreferrer">
                    {fields.payment_link}
                  </a>
                ) : (
                  <Button type="primary" onClick={handleGeneratePaymentLink}>
                    {t('generatePaymentLink') || 'Generate Payment Link'}
                  </Button>
                )}
              </div>
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

// import React, { useEffect, useState } from 'react';
// import { Button, Input, Modal, Upload, Table, Space, Card, DatePicker, Typography, Select, Pagination } from 'antd';
// import { UploadOutlined } from '@ant-design/icons';
// import { useNavigate } from 'react-router-dom';
// import { Snackbar, Alert } from '@mui/material';
// import { API_BASE_URL } from '../config';
// import LoadingModal from '../components/LoadingModal';
// const { Link } = Typography;

// console.log('Review component rendered');

// function Review({ t = x => x }) {
//   const [bills, setBills] = useState([]);
//   const [selected, setSelected] = useState(null);
//   const [fields, setFields] = useState({});
//   const [serviceFee, setServiceFee] = useState('');
//   const [ctnFee, setCtnFee] = useState('');
//   const [paymentLink, setPaymentLink] = useState('');
//   const [modalVisible, setModalVisible] = useState(false);
//   const [uniqueNumber, setUniqueNumber] = useState('');
//   const [blSearch, setBlSearch] = useState('');
//   const [statusFilter, setStatusFilter] = useState('');
//   const [loading, setLoading] = useState(false);
//   const [saving, setSaving] = useState(false);
//   const [page, setPage] = useState(1);
//   const [pageSize, setPageSize] = useState(50);
//   const [total, setTotal] = useState(0);
//   const navigate = useNavigate();

//   // For invoice email modal
//   const [emailModalVisible, setEmailModalVisible] = useState(false);
//   const [emailBody, setEmailBody] = useState('');
//   const [emailTo, setEmailTo] = useState('');
//   const [emailSubject, setEmailSubject] = useState('');
//   const [emailPdfUrl, setEmailPdfUrl] = useState('');
//   const [sendingEmail, setSendingEmail] = useState(false);

//   // For unique number email modal
//   const [uniqueEmailModalVisible, setUniqueEmailModalVisible] = useState(false);
//   const [uniqueEmailBody, setUniqueEmailBody] = useState('');
//   const [uniqueEmailTo, setUniqueEmailTo] = useState('');
//   const [uniqueEmailSubject, setUniqueEmailSubject] = useState('');
//   const [uniqueSending, setUniqueSending] = useState(false);

//   const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

//   // Filter bills by status
//   const statusOptions = [
//     { label: t('pending'), value: t('pending') },
//     { label: t('invoiceSent'), value: t('invoiceSent') },
//     { label: t('awaitingBankIn'), value: t('awaitingBankIn') },
//     { label: t('paidAndCtnValid'), value: t('paidAndCtnValid') },
//   ];
//   const billsToShow = (bills).filter(bill =>
//     !statusFilter || bill.status === statusFilter
//   );

//   // 获取所有提单
//   const fetchBills = async (params = {}) => {
//     setLoading(true);
//     try {
//       const token = localStorage.getItem('token');
//       if (!token) {
//         setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
//         navigate('/login');
//         return;
//       }
//       const query = new URLSearchParams({
//         page: params.page || page,
//         page_size: params.pageSize || pageSize,
//         bl_number: params.blSearch !== undefined ? params.blSearch : blSearch,
//         status: params.statusFilter !== undefined ? params.statusFilter : statusFilter
//       });
//       const response = await fetch(`${API_BASE_URL}/api/bills?${query.toString()}`, {
//         headers: { Authorization: `Bearer ${token}` }
//       });
//       if (response.status === 401) {
//         setSnackbar({ open: true, message: 'Session expired. Please log in again.', severity: 'error' });
//         localStorage.clear();
//         navigate('/login');
//         return;
//       }
//       if (!response.ok) {
//         throw new Error(`HTTP error! status: ${response.status}`);
//       }
//       const data = await response.json();
//       setBills(data.bills || []);
//       setTotal(data.total || 0);
//       setPage(data.page || 1);
//       setPageSize(data.page_size || 50);
//     } catch (error) {
//       setSnackbar({ open: true, message: error.message, severity: 'error' });
//       setBills([]);
//       setTotal(0);
//     } finally {
//       setLoading(false);
//     }
//   };

//   useEffect(() => {
//     fetchBills({ page: 1 });
//     // eslint-disable-next-line
//   }, []);

//   // BL number search handler
//   const handleBlSearch = () => {
//     setPage(1);
//     fetchBills({ page: 1, blSearch });
//   };

//   // Status filter handler
//   const handleStatusFilter = (value) => {
//     setStatusFilter(value);
//     setPage(1);
//     fetchBills({ page: 1, statusFilter: value });
//   };

//   // Pagination handler
//   const handlePageChange = (newPage, newPageSize) => {
//     setPage(newPage);
//     setPageSize(newPageSize);
//     fetchBills({ page: newPage, pageSize: newPageSize });
//   };

//   const showModal = (record) => {
//     setSelected(record);
//     setFields({
//       shipper: record.shipper || '',
//       consignee: record.consignee || '',
//       port_of_loading: record.port_of_loading || '',
//       port_of_discharge: record.port_of_discharge || '',
//       bl_number: record.bl_number || '',
//       container_numbers: record.container_numbers || '',
//       flight_or_vessel: record.flight_or_vessel || '',           // <-- add this
//       product_description: record.product_description || '',      // <-- add this
//     });
//     setServiceFee(record.service_fee || '');
//     setCtnFee(record.ctn_fee || '');
//     setPaymentLink(record.payment_link || '');
//     setUniqueNumber(record.unique_number || '');
//     setModalVisible(true);
//   };

//   const handleFieldChange = (key, value) => {
//     setFields({ ...fields, [key]: value });
//   };

//   const handleOk = async () => {
//     setSaving(true);
//     try {
//       const token = localStorage.getItem('token');
//       if (!token) {
//         setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
//         navigate('/login');
//         return;
//       }

//       // Combine all necessary fields into one update payload
//       const updateData = {
//         ...fields,
//         service_fee: serviceFee,
//         ctn_fee: ctnFee,
//         payment_link: fields.payment_link || paymentLink,
//         unique_number: uniqueNumber,
//         // If you want to ensure these are always sent, include them:
//         payment_method: selected?.payment_method || '',
//         payment_status: selected?.payment_status || '',
//         reserve_status: selected?.reserve_status || ''
//       };

//       const res = await fetch(`${API_BASE_URL}/api/bills/${selected.id}`, {
//         method: 'PUT',
//         headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
//         body: JSON.stringify(updateData)
//       });

//       if (res.status === 401) {
//         setSnackbar({ open: true, message: 'Session expired. Please log in again.', severity: 'error' });
//         localStorage.clear();
//         navigate('/login');
//         return;
//       }

//       if (!res.ok) {
//         const data = await res.json();
//         throw new Error(data.error || t('failed'));
//       }

//       setSnackbar({ open: true, message: t('success'), severity: 'success' });
//       setModalVisible(false);
//       fetchBills();
//     } catch (err) {
//       console.error('Error updating bill:', err);
//       setSnackbar({ open: true, message: err.message || t('failed'), severity: 'error' });
//     } finally {
//       setSaving(false);
//     }
//   };

//   // 上传收据
//   const handleUpload = async (file, record) => {
//     const formData = new FormData();
//     formData.append('receipt', file);
//     await fetch(`${API_BASE_URL}/api/bill/${record.id}/upload_receipt`, {
//       method: 'POST',
//       body: formData
//     });
//     setSnackbar({ open: true, message: t('receiptUploadSuccess'), severity: 'success' });
//     fetchBills();
//   };

//   // Show email modal for invoice
//   const showEmailModal = (record) => {
//     console.log('Show invoice email modal');
//     setEmailTo(record.customer_email);
//     setEmailSubject(t('invoiceSubject'));
//     const ctnFeeVal = record.ctn_fee || 0;
//     const serviceFeeVal = record.service_fee || 0;
//     const total = (parseFloat(ctnFeeVal) + parseFloat(serviceFeeVal)).toFixed(2);
//     setEmailBody(
//       `Dear ${record.customer_name},\n\nPlease find your invoice attached.\nCTN Fee: $${ctnFeeVal}\nService Fee: $${serviceFeeVal}\nTotal Amount: $${total}\n\nPlease follow the below link to make the payment:\n${record.payment_link || ''}\n\nThank you!`
//     );
//     setEmailPdfUrl(`${API_BASE_URL}/uploads/${record.invoice_filename}`);
//     setSelected(record);
//     setEmailModalVisible(true);
//   };

//   // Send invoice email after staff verification
//   const handleSendInvoiceEmail = async () => {
//     setSendingEmail(true);
//     try {
//       const token = localStorage.getItem('token');
//       if (!token) {
//         setSnackbar({ open: true, message: 'Authentication required. Please log in again.', severity: 'error' });
//         navigate('/login');
//         return;
//       }

//       const res = await fetch(`${API_BASE_URL}/api/send_invoice_email`, {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
//         body: JSON.stringify({
//           to_email: emailTo,
//           subject: emailSubject,
//           body: emailBody,
//           pdf_url: emailPdfUrl,
//           bill_id: selected.id
//         })
//       });

//       if (res.status === 401) {
//         setSnackbar({ open: true, message: 'Session expired. Please log in again.', severity: 'error' });
//         localStorage.clear();
//         navigate('/login');
//         return;
//       }

//       const data = await res.json();
//       if (res.ok) {
//         setSnackbar({ open: true, message: t('emailSent'), severity: 'success' });
//         setEmailModalVisible(false);
//         fetchBills();
//       } else {
//         setSnackbar({ open: true, message: data.error || t('emailFailed'), severity: 'error' });
//       }
//     } catch (err) {
//       setSnackbar({ open: true, message: t('emailFailed'), severity: 'error' });
//     } finally {
//       setSendingEmail(false);
//     }
//   };

//   // Show unique number email modal
//   const showUniqueEmailModal = (record) => {
//     setSelected(record);
//     setUniqueEmailTo(record.customer_email);
//     setUniqueEmailSubject(t('uniqueNumberSubject'));
//     setUniqueEmailBody(t('uniqueNumberBody', { name: record.customer_name, number: record.unique_number }));
//     setUniqueEmailModalVisible(true);
//   };

//   // Send unique number email
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
//           bill_id: selected.id
//         })
//       });
//       const data = await res.json();
//       if (res.ok) {
//         setSnackbar({ open: true, message: t('uniqueEmailSent'), severity: 'success' });
//         setUniqueEmailModalVisible(false);
//       } else {
//         setSnackbar({ open: true, message: data.error || t('emailFailed'), severity: 'error' });
//       }
//     } catch (err) {
//       setSnackbar({ open: true, message: t('emailFailed'), severity: 'error' });
//     } finally {
//       setUniqueSending(false);
//     }
//   };

//   // Send CTN Number logic
//   const handleSendUniqueNumber = (record) => {
//     showUniqueEmailModal(record);
//   };

//   const columns = [
//     { title: t('customerName'), dataIndex: 'customer_name', key: 'customer_name' },
//     { title: t('blNumber'), dataIndex: 'bl_number', key: 'bl_number' },
//     {
//       title: t('shipperConsignee'),
//       key: 'shipperConsignee',
//       render: (_, record) => (
//         <div>
//           <div>{record.shipper}</div>
//           <div>{record.consignee}</div>
//         </div>
//       ),
//     },
//     { title: t('status'), dataIndex: 'status', key: 'status' },
//     {
//       title: t('edit'),
//       key: 'edit',
//       width: 80,
//       render: (_, record) => (
//         <Button size="small" onClick={() => showModal(record)}>{t('edit')}</Button>
//       ),
//     },
//     {
//       title: t('invoice'),
//       key: 'invoice',
//       width: 120,
//       render: (_, record) => record.invoice_filename ? (
//         <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
//           <Link
//             href={`${API_BASE_URL}/uploads/${record.invoice_filename}`}
//             target="_blank"
//             rel="noopener noreferrer"
//           >
//             <Button size="small">{t('viewInvoice')}</Button>
//           </Link>
//           <Button
//             size="small"
//             type="primary"
//             onClick={() => showEmailModal(record)}
//           >
//             {t('sendInvoice')}
//           </Button>
//         </div>
//       ) : t('noInvoice'),
//     },
//     {
//       title: t('ctnServiceFee'),
//       key: 'ctnServiceFee',
//       render: (_, record) => (
//         <span>{record.ctn_fee || 0} / {record.service_fee || 0}</span>
//       ),
//     },
//     {
//       title: t('uploadReceipt'),
//       key: 'uploadReceipt',
//       width: 120,
//       render: (_, record) => (
//         <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
//           <Upload
//             showUploadList={false}
//             customRequest={({ file, onSuccess, onError }) => {
//               handleUpload(file, record)
//                 .then(() => onSuccess && onSuccess())
//                 .catch(onError);
//             }}
//           >
//             <Button size="small">{t('uploadReceipt')}</Button>
//           </Upload>
//           {record.receipt_filename && (
//             <Link
//               href={`${API_BASE_URL}/uploads/${record.receipt_filename}`}
//               target="_blank"
//               rel="noopener noreferrer"
//             >
//               <Button size="small">{t('viewReceipt')}</Button>
//             </Link>
//           )}
//         </div>
//       ),
//     },
//     {
//       title: t('ctnNumber'),
//       dataIndex: 'unique_number',
//       key: 'unique_number',
//       width: 120,
//       render: (text, record) => (
//         <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
//           <span>{text}</span>
//           <Button
//             size="small"
//             onClick={() => handleSendUniqueNumber(record)}
//           >
//             {t('sendCtnNumber')}
//           </Button>
//         </div>
//       ),
//     },
//     {
//       title: <span>Customer<br/>Document</span>,
//       key: 'customerDocument',
//       width: 120,
//       render: (_, record) => (
//         <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
//           <Button
//             size="small"
//             disabled={!record.customer_invoice}
//             href={record.customer_invoice ? `${API_BASE_URL}/uploads/${record.customer_invoice}` : undefined}
//             target="_blank"
//             rel="noopener noreferrer"
//           >
//             {t('invoice')}
//           </Button>
//           <Button
//             size="small"
//             disabled={!record.customer_packing_list}
//             href={record.customer_packing_list ? `${API_BASE_URL}/uploads/${record.customer_packing_list}` : undefined}
//             target="_blank"
//             rel="noopener noreferrer"
//           >
//             {t('packingList')}
//           </Button>
//         </div>
//       ),
//     },
//   ];

//   return (
//     <div style={{ maxWidth: 1200, margin: '0 auto', padding: '20px' }}>
//       <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
//         <Button
//           variant="contained"
//           color="primary"
//           style={{ color: '#fff', backgroundColor: '#1976d2' }}
//           onClick={() => navigate('/dashboard')}
//         >
//           {t('backToDashboard')}
//         </Button>
//         <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
//           <Input
//             placeholder={t('blNumber')}
//             value={blSearch}
//             onChange={e => setBlSearch(e.target.value)}
//             style={{ width: 200 }}
//             allowClear
//           />
//           <Button type="primary" onClick={handleBlSearch}>{t('search')}</Button>
//           <Button onClick={() => { setBlSearch(''); fetchBills({ page: 1 }); }}>{t('cancel')}</Button>
//           <Select
//             placeholder={t('filterByStatus')}
//             style={{ width: 180 }}
//             value={statusFilter || undefined}
//             onChange={handleStatusFilter}
//             allowClear
//             options={statusOptions}
//           />
//         </div>
//       </div>
//       <h2>{t('billReview')}</h2>
      
//       {billsToShow.length > 0 ? (
//         <Table dataSource={billsToShow} columns={columns} rowKey="id" pagination={false} />
//       ) : (
//         <div style={{ textAlign: 'center', padding: '20px' }}>No data available</div>
//       )}
      
//       <Pagination
//         current={page}
//         pageSize={pageSize}
//         total={total}
//         showSizeChanger
//         onChange={handlePageChange}
//         onShowSizeChange={handlePageChange}
//         style={{ marginTop: 16, textAlign: 'right' }}
//       />
      
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
//       {/* Modals */}
//       <Modal
//         open={modalVisible}
//         onCancel={() => setModalVisible(false)}
//         onOk={handleOk}
//         okText={t('save')}
//         cancelText={t('cancel')}
//         title={t('editBill')}
//         width={1100}
//       >
//         {selected && (
//           <div style={{ display: 'flex', gap: 24 }}>
//             <iframe
//               src={`${API_BASE_URL}/uploads/${selected.pdf_filename}`}
//               width="100%"
//               height="500px"
//               title={t('pdfPreview')}
//             />
//             <div style={{ flex: 1 }}>
//               <div>
//                 <b>{t('shipper')}:</b>
//                 <Input.TextArea
//                   value={fields.shipper}
//                   onChange={e => handleFieldChange('shipper', e.target.value)}
//                   autoSize={{ minRows: 2, maxRows: 4 }}
//                 />
//               </div>
//               <div>
//                 <b>{t('consignee')}:</b>
//                 <Input.TextArea
//                   value={fields.consignee}
//                   onChange={e => handleFieldChange('consignee', e.target.value)}
//                   autoSize={{ minRows: 2, maxRows: 4 }}
//                 />
//               </div>
//               <div>
//                 <b>{t('portOfLoading')}:</b>
//                 <Input
//                   value={fields.port_of_loading}
//                   onChange={e => handleFieldChange('port_of_loading', e.target.value)}
//                 />
//               </div>
//               <div>
//                 <b>{t('portOfDischarge')}:</b>
//                 <Input
//                   value={fields.port_of_discharge}
//                   onChange={e => handleFieldChange('port_of_discharge', e.target.value)}
//                 />
//               </div>
//               <div>
//                 <b>{t('blNumber')}:</b>
//                 <Input
//                   value={fields.bl_number}
//                   onChange={e => handleFieldChange('bl_number', e.target.value)}
//                 />
//               </div>
//               <div>
//                 <b>{t('containerNumbers')}:</b>
//                 <Input
//                   value={fields.container_numbers}
//                   onChange={e => handleFieldChange('container_numbers', e.target.value)}
//                 />
//               </div>
//               <div>
//                 <b>{t('flightOrVessel') || 'Flight or Vessel'}:</b>
//                 <Input
//                   value={fields.flight_or_vessel}
//                   onChange={e => handleFieldChange('flight_or_vessel', e.target.value)}
//                 />
//               </div>
//               <div>
//                 <b>{t('productDescription') || 'Product Description'}:</b>
//                 <Input.TextArea
//                   value={fields.product_description}
//                   onChange={e => handleFieldChange('product_description', e.target.value)}
//                   autoSize={{ minRows: 2, maxRows: 4 }}
//                 />
//               </div>
//               <Input
//                 style={{ width: 200, marginTop: 16 }}
//                 addonBefore={t('ctnFee') + '(USD)'}
//                 value={ctnFee}
//                 onChange={e => setCtnFee(e.target.value)}
//               />
//               <Input
//                 style={{ width: 200, marginTop: 16 }}
//                 addonBefore={t('serviceFee') + '(USD)'}
//                 value={serviceFee}
//                 onChange={e => setServiceFee(e.target.value)}
//               />
//               <div style={{ marginTop: 16 }}>
//                 <b>{t('paymentLink') || 'Payment Link'}:</b>{' '}
//                 {fields.payment_link ? (
//                   <a href={fields.payment_link} target="_blank" rel="noopener noreferrer">
//                     {fields.payment_link}
//                   </a>
//                 ) : (
//                   <Button type="primary" onClick={async () => {
//                     try {
//                       const res = await fetch(`${API_BASE_URL}/api/generate_payment_link/${selected.id}`, {
//                         method: 'POST',
//                         headers: { 'Content-Type': 'application/json' }
//                       });
//                       const data = await res.json();
//                       if (res.ok && data.payment_link) {
//                         setFields(prev => ({ ...prev, payment_link: data.payment_link }));
//                       } else {
//                         window.message && window.message.error
//                           ? window.message.error('Failed to generate payment link')
//                           : alert('Failed to generate payment link');
//                       }
//                     } catch (err) {
//                       console.error(err);
//                       window.message && window.message.error
//                         ? window.message.error('Error generating link')
//                         : alert('Error generating link');
//                     }
//                   }}>
//                     {t('generatePaymentLink') || 'Generate Payment Link'}
//                   </Button>
//                 )}
//               </div>
//               <Input
//                 value={uniqueNumber}
//                 onChange={e => setUniqueNumber(e.target.value)}
//                 placeholder={t('ctnNumber')}
//               />
//             </div>
//           </div>
//         )}
//       </Modal>
//       <Modal
//         open={emailModalVisible}
//         onCancel={() => setEmailModalVisible(false)}
//         onOk={handleSendInvoiceEmail}
//         okText={t('send')}
//         cancelText={t('cancel')}
//         title={t('verifyInvoiceEmail')}
//         confirmLoading={sendingEmail}
//       >
//         <div>
//           <div><strong>{t('to')}:</strong> {emailTo}</div>
//           <div><strong>{t('subject')}:</strong> {emailSubject}</div>
//           <div style={{ margin: '12px 0' }}>
//             <strong>{t('emailBody')}:</strong>
//             <Input.TextArea
//               value={emailBody}
//               onChange={e => setEmailBody(e.target.value)}
//               autoSize={{ minRows: 6 }}
//             />
//           </div>
//           <div>
//             <Link 
//               href={emailPdfUrl}
//               target="_blank" 
//               rel="noopener noreferrer"
//               style={{ textDecoration: 'none' }}
//             >
//               <Button variant="outlined" size="small">
//                 {t('previewPDF')}
//               </Button>
//             </Link>
//           </div>
//         </div>
//       </Modal>
//       <Modal
//         open={uniqueEmailModalVisible}
//         onCancel={() => setUniqueEmailModalVisible(false)}
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
//             <Input.TextArea
//               value={uniqueEmailBody}
//               onChange={e => setUniqueEmailBody(e.target.value)}
//               autoSize={{ minRows: 6 }}
//             />
//           </div>
//         </div>
//       </Modal>
//       <LoadingModal open={loading} message={t('loadingData')} />
//       <LoadingModal open={saving} message={t('savingData')} />
//       <LoadingModal open={sendingEmail} message={t('sendingEmail')} />
//       <LoadingModal open={uniqueSending} message={t('sendingEmail')} />
//     </div>
//   );
// }

// export default Review;