import React from 'react';
import { Button } from 'antd';
import { useNavigate } from 'react-router-dom';
import PropTypes from 'prop-types';

const NavigationButtons = ({ t }) => {
  const navigate = useNavigate();

  return (
    <div style={{ marginBottom: '20px' }}>
      <Button onClick={() => navigate('/review')}>
        Review Bill
      </Button>
      <Button onClick={() => navigate('/bill-search')}>
        Bill Search
      </Button>
      <Button onClick={() => navigate('/staff-stats')}>
        Staff Stats
      </Button>
    </div>
  );
};

NavigationButtons.propTypes = {
  t: PropTypes.func.isRequired
};

export default NavigationButtons;
