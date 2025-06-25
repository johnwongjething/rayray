import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import NavBar from './NavBar';
import Home from './Home';
import About from './About';
import Services from './Services';
import Contact from './Contact';
import Login from './Login';
import Register from './Register';
import StaffStats from './StaffStats';
import UserApproval from './UserApproval';
import Review from './Review';
import UploadForm from './UploadForm';
import BillSearch from './BillSearch';
import WhatsAppButton from './WhatsAppButton';
import WeChatButton from './WeChatButton';
import Dashboard from './Dashboard';
import FAQ from './FAQ';
import EditBill from './EditBill';
import EditDeleteBills from './EditDeleteBills';
import translations from './translations';
import ForgotPassword from './ForgotPassword';
import ResetPassword from './ResetPassword';
import AccountPage from './AccountPage';
import NotFound from './NotFound';
import AccountingReview from './AccountingReview';
import './App.css';

const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
  },
});

function App() {
  const [lang, setLang] = useState(localStorage.getItem('lang') || 'en');
  const t = (key, params) => {
    let str = translations[lang][key] || key;
    if (params) {
      Object.keys(params).forEach(k => {
        str = str.replace(new RegExp(`{${k}}`, 'g'), params[k]);
      });
    }
    return str;
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <div className="App">
          <NavBar lang={lang} setLang={setLang} t={t} />
          <Routes>
            <Route path="/" element={<Home t={t} />} />
            <Route path="/about" element={<About t={t} />} />
            <Route path="/services" element={<Services t={t} />} />
            <Route path="/contact" element={<Contact t={t} />} />
            <Route path="/login" element={<Login t={t} />} />
            <Route path="/register" element={<Register t={t} />} />
            <Route path="/staff-stats" element={<StaffStats t={t} />} />
            <Route path="/user-approval" element={<UserApproval t={t} />} />
            <Route path="/review" element={<Review t={t} />} />
            <Route path="/upload" element={<UploadForm t={t} />} />
            <Route path="/search" element={<BillSearch t={t} />} />
            <Route path="/dashboard" element={<Dashboard t={t} />} />
            <Route path="/faq" element={<FAQ t={t} />} />
            <Route path="/edit-bill/:id" element={<EditBill t={t} />} />
            <Route path="/edit-delete-bills" element={<EditDeleteBills t={t} />} />
            <Route path="/account-page" element={<AccountPage t={t} />} />
            <Route path="/forgot-password" element={<ForgotPassword t={t} />} />
            <Route path="/reset-password/:token" element={<ResetPassword t={t} />} />
            <Route path="/accounting-review" element={<AccountingReview t={t} />} />
            <Route path="*" element={<NotFound t={t} />} />
          </Routes>
          <WeChatButton />
          <WhatsAppButton />
        </div>
      </Router>
    </ThemeProvider>
  );
}

export default App;