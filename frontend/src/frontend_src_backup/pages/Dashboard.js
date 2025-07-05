import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Box, Typography, Stack } from '@mui/material';

function Dashboard({ t = x => x }) {
  const role = localStorage.getItem('role');
  const navigate = useNavigate();

  return (
    <Box sx={{ my: 4, textAlign: 'center' }}>
      <Typography variant="h3" gutterBottom>
        {t('dashboard')}
      </Typography>
      <Typography variant="h6" gutterBottom>
        {t('welcome')}, {localStorage.getItem('username')} ({t(role)})
      </Typography>
      
      {/* First Row - Primary Navigation */}
      <Stack direction="row" spacing={2} justifyContent="center" sx={{ my: 2 }}>
        <Stack direction="row" spacing={2} justifyContent="center" sx={{ my: 2 }}>
        {role !== 'customer' && (
          <>
            <Button variant="contained" onClick={() => navigate('/review')}>{t('reviewBills')}</Button>
            <Button variant="contained" onClick={() => navigate('/staff-stats')}>{t('staffStats')}</Button>
          </>
        )}
        <Button variant="contained" onClick={() => navigate('/search')}>{t('billSearch')}</Button>
      </Stack>
      </Stack>

      {/* Second Row - Document Management */}
      <Stack direction="row" spacing={2} justifyContent="center" sx={{ my: 2 }}>
        {role !== 'customer' && (
          <>
            <Button variant="contained" onClick={() => navigate('/edit-delete-bills')}>{t('editDeleteBills')}</Button>
            <Button variant="contained" onClick={() => navigate('/account-page')}>{t('accountPage')}</Button>
          </>
        )}
        <Button variant="contained" onClick={() => navigate('/upload')}>{t('uploadBill')}</Button>
      </Stack>

      {/* Third Row - User Management */}
      <Stack direction="row" spacing={2} justifyContent="center" sx={{ my: 2 }}>
        {role === 'staff' || role === 'admin' ? (
          <>
            <Button variant="contained" onClick={() => navigate('/register')}>{t('registerUser')}</Button>
            <Button variant="contained" onClick={() => navigate('/user-approval')}>{t('userApproval')}</Button>
            <Button variant="contained" onClick={() => navigate('/accounting-review')}>{t('accountSettlement')}</Button>
          </>
        ) : (
          <></>
        )}
      </Stack>

      {/* Logout button */}
      <Stack direction="row" spacing={2} justifyContent="center" sx={{ mt: 4 }}>
        <Button
          variant="outlined"
          color="secondary"
          onClick={() => {
            localStorage.clear();
            navigate('/login');
          }}
        >
          {t('logout')}
        </Button>
      </Stack>
    </Box>
  );
}

export default Dashboard;