import React from 'react';
import { Modal, CircularProgress, Typography, Box } from '@mui/material';

const LoadingModal = ({ open, message = 'Loading, please wait...' }) => {
  return (
    <Modal
      open={open}
      aria-labelledby="loading-modal"
      aria-describedby="loading-modal-description"
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1300
      }}
    >
      <Box
        sx={{
          bgcolor: 'background.paper',
          p: { xs: 3, sm: 4 },
          borderRadius: 2,
          boxShadow: 3,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          minWidth: { xs: 200, sm: 300 }
        }}
      >
        <CircularProgress size={48} sx={{ mb: 2 }} />
        <Typography variant="h6" align="center">
          {message}
        </Typography>
      </Box>
    </Modal>
  );
};

export default LoadingModal;