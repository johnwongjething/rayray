// src/pages/WeChatButton.js
import React from 'react';

const WeChatButton = () => (
  <a
    href="weixin://dl/chat?dar4037" // Replace with your actual WeChat ID or QR code link
    className="wechat-float"
    target="_blank"
    rel="noopener noreferrer"
    style={{
      position: 'fixed',
      bottom: 90,
      right: 24,
      zIndex: 1000,
      background: '#09b83e',
      borderRadius: '50%',
      width: 56,
      height: 56,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: '0 2px 8px rgba(0,0,0,0.2)'
    }}
  >
    <img src="/wechat-icon.png" alt="WeChat" style={{ width: 32, height: 32 }} />
  </a>
);

export default WeChatButton;