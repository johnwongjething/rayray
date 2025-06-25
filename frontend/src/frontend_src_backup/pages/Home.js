import React from 'react';
import { Container, Typography, Button, Box } from '@mui/material';
import { useNavigate } from 'react-router-dom';

function Home({ t = x => x }) {
  const navigate = useNavigate();
  return (
    <Box
      sx={{
        backgroundImage: 'url(/images/seaport.jpg)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'white',
        textAlign: 'center',
      }}
    >
      <Container>
        <Typography variant="h2" component="h1" gutterBottom>
          {t('welcomeTitle')}
        </Typography>
        <Typography variant="h5" component="h2" gutterBottom>
          {t('welcomeSubtitle')}
        </Typography>
        <Button variant="contained" color="primary" size="large" sx={{ mt: 2 }} onClick={() => navigate('/about')}>
          {t('learnMore')}
        </Button>
      </Container>
    </Box>
  );
}

export default Home;