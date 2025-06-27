import React from 'react';

const WhatsAppButton = () => {
  return (
    <a
      href="https://api.whatsapp.com/send?phone=85265381629"
      className="whatsapp-float"
      target="_blank"
      rel="noopener noreferrer"
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 1000,
        background: '#25D366',
        borderRadius: '50%',
        width: 56,
        height: 56,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: '0 2px 8px rgba(0,0,0,0.2)'
      }}
    >
      <img src="/whatsapp-icon.png" alt="WhatsApp" style={{ width: 32, height: 32 }} />
    </a>
  );
};

export default WhatsAppButton;
