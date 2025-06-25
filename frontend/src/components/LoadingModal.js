import React from 'react';
import { Modal, CircularProgress, Typography } from '@mui/material';

const LoadingModal = ({ open, message = 'Loading, please wait...' }) => {
  return (
    <Modal 
      open={open} 
      aria-labelledby="loading-modal" 
      aria-describedby="loading-modal-description" 
      style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center' 
      }}
    >
      <div style={{ 
        background: 'rgba(255,255,255,0.95)', 
        padding: 32, 
        borderRadius: 8, 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center',
        boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
        minWidth: 200
      }}>
        <CircularProgress size={48} />
        <Typography variant="h6" style={{ marginTop: 16, textAlign: 'center' }}>
          {message}
        </Typography>
      </div>
    </Modal>
  );
};

export default LoadingModal; 