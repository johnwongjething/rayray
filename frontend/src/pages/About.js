import React from 'react';
import { Container, Typography, Box } from '@mui/material';

function About({ t = x => x }) {
  return (
    <Box
      sx={{
        backgroundImage: 'url(/assets/about.jpg)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        minHeight: '100vh',
        py: 8,
      }}
    >
      <Container maxWidth="md">
        <Box sx={{ maxWidth: 700, mx: 'auto', background: 'rgba(255,255,255,0.95)', borderRadius: 2, py: 4, px: 4, mt: 6 }}>
          <Typography variant="h3" component="h1" gutterBottom>
            {t('about')}
          </Typography>
          <Typography variant="body1" paragraph>
            {t('aboutContent')}
          </Typography>
        </Box>
      </Container>
    </Box>
  );
}

export default About; 