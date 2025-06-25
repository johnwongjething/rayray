import React, { useState, useEffect } from 'react';
import { Button, DatePicker, Table, Typography } from 'antd';
import jsPDF from 'jspdf';
import 'jspdf-autotable';
import { API_BASE_URL } from '../config';
import { useNavigate } from 'react-router-dom';
import LoadingModal from '../components/LoadingModal';

const { Title } = Typography;

const AccountPage = ({ t = x => x }) => {
  const [date, setDate] = useState(null);
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState({ totalCtnFee: 0, totalServiceFee: 0, totalEntries: 0 });
  const navigate = useNavigate();

  // Move columns definition here so t is always defined
  const columns = [
    { title: t('blNumber'), dataIndex: 'bl_number', key: 'bl_number' },
    { title: t('ctnFee'), dataIndex: 'ctn_fee', key: 'ctn_fee', render: v => `$${v}` },
    { title: t('serviceFee'), dataIndex: 'service_fee', key: 'service_fee', render: v => `$${v}` },
    { title: t('total'), key: 'total', render: r => `$${parseFloat(r.ctn_fee) + parseFloat(r.service_fee)}` },
    { title: t('customerName'), dataIndex: 'customer_name', key: 'customer_name' },
    { title: t('date'), dataIndex: 'completed_at', key: 'completed_at', render: v => v ? new Date(v).toLocaleString('en-HK', { timeZone: 'Asia/Hong_Kong' }) : '' },
  ];

  // Fetch bills, optionally filtered by date string (YYYY-MM-DD)
  const fetchAccountBills = async (searchDateString = null) => {
    setLoading(true);
    try {
      let url = `${API_BASE_URL}/api/account_bills`;
      if (searchDateString) {
        url += `?completed_at=${searchDateString}`;
      }
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        setBills(data.bills || []);
        setSummary(data.summary || {});
      }
    } catch (error) {
      setBills([]);
      setSummary({ totalCtnFee: 0, totalServiceFee: 0, totalEntries: 0 });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAccountBills(); }, []);

  // Date search handler
  const handleDateSearch = () => {
    if (date) {
      const hkDateString = date.format('YYYY-MM-DD'); // moment object from AntD DatePicker
      fetchAccountBills(hkDateString);
    }
  };

  // Clear date search
  const handleClearDateSearch = () => {
    setDate(null);
    fetchAccountBills(null);
  };

  // Export to PDF with static imports
  const handleExportPDF = () => {
    const doc = new jsPDF();
    const title = date
      ? `Account Page Report - ${date.format('YYYY-MM-DD')}`
      : 'Account Page Report - All Completed Bills';
    doc.setFontSize(16);
    doc.text(title, 20, 20);
    doc.setFontSize(12);
    doc.text(`Total Entries: ${summary.totalEntries}`, 20, 35);
    doc.text(`Total CTN Fees: $${summary.totalCtnFee}`, 20, 45);
    doc.text(`Total Service Fee: $${summary.totalServiceFee}`, 20, 55);
    const tableColumn = ['BL Number', 'ctnFee', 'Service Fee', 'total', 'Customer Name', 'date'];
    const tableRows = bills.map(bill => [
      bill.bl_number || '',
      `$${bill.ctn_fee || 0}`,
      `$${bill.service_fee || 0}`,
      `$${parseFloat(bill.ctn_fee || 0) + parseFloat(bill.service_fee || 0)}`,
      bill.customer_name || '',
      bill.completed_at ? new Date(bill.completed_at).toLocaleString('en-HK', { timeZone: 'Asia/Hong_Kong' }) : ''
    ]);
    doc.autoTable({
      head: [tableColumn],
      body: tableRows,
      startY: 70,
      styles: {
        fontSize: 10,
        cellPadding: 4,
        lineWidth: 0.5,
        lineColor: [0, 0, 0],
        halign: 'center',
        valign: 'middle',
      },
      headStyles: {
        fillColor: [41, 128, 185],
        textColor: 255,
        fontStyle: 'bold',
        lineWidth: 0.5,
        lineColor: [0, 0, 0],
      },
      alternateRowStyles: { fillColor: [245, 245, 245] },
      tableLineWidth: 0.5,
      tableLineColor: [0, 0, 0],
      theme: 'grid',
    });
    doc.save('account_page.pdf');
  };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '20px' }}>
      {/* Top bar: Back to Dashboard (left), Export to PDF (right) */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Button
          variant="contained"
          color="primary"
          style={{ color: '#fff', backgroundColor: '#1976d2' }}
          onClick={() => navigate('/dashboard')}
        >
          {t('backToDashboard')}
        </Button>
        <Button type="link" onClick={handleExportPDF} style={{ fontWeight: 'bold' }}>
          {t('exportToPDF')}
        </Button>
      </div>
      {/* Header */}
      <h2 style={{ margin: 0, textAlign: 'center' }}>{t('completedBillsAccountPage')}</h2>
      {/* Date search row below header, centered */}
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', margin: '16px 0' }}>
        <DatePicker
          value={date}
          onChange={setDate}
          style={{ marginRight: 8 }}
          allowClear
        />
        <Button type="primary" onClick={handleDateSearch} style={{ marginRight: 8 }}>
          {t('search')}
        </Button>
        <Button onClick={handleClearDateSearch}>
          {t('clearSearch')}
        </Button>
      </div>
      {/* Summary */}
      <div className="summary" style={{ display: 'flex', justifyContent: 'center', marginBottom: 24 }}>
        <div style={{ margin: '0 32px', textAlign: 'center' }}>
          <h3>{t('totalEntries')}</h3>
          <div style={{ fontSize: 24 }}>{summary.totalEntries}</div>
        </div>
        <div style={{ margin: '0 32px', textAlign: 'center' }}>
          <h3>{t('totalCtnFees')}</h3>
          <div style={{ fontSize: 24 }}>${summary.totalCtnFee}</div>
        </div>
        <div style={{ margin: '0 32px', textAlign: 'center' }}>
          <h3>{t('totalServiceFee')}</h3>
          <div style={{ fontSize: 24 }}>${summary.totalServiceFee}</div>
        </div>
      </div>
      {/* Table of results */}
      <Table dataSource={bills} columns={columns} rowKey="id" loading={loading} />
      
      {/* Loading Modal for Data Loading */}
      <LoadingModal 
        open={loading} 
        message={t('loadingData')} 
      />
    </div>
  );
};

export default AccountPage;
