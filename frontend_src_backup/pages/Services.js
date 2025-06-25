import React from 'react';
import { Container, Typography, Box, Grid, Card, CardContent } from '@mui/material';

function Services({ t = x => x }) {
  const services = [
    {
      title: t('globalShipping'),
      description: t('globalShippingDesc'),
    },
    {
      title: t('logisticsManagement'),
      description: t('logisticsManagementDesc'),
    },
    {
      title: t('cargoTracking'),
      description: t('cargoTrackingDesc'),
    },
  ];

  return (
    <Box
      sx={{
        backgroundImage: 'url(/assets/service.jpg)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        minHeight: '100vh',
        py: 8,
      }}
    >
      <Container sx={{ background: 'rgba(255,255,255,0.95)', borderRadius: 2, py: 4, mt: 6 }}>
        <Typography variant="h3" component="h1" gutterBottom>
          {t('services')}
        </Typography>
        <Typography variant="body1" sx={{ mt: 2 }}>
          {t('servicesContent')}
        </Typography>
        <Grid container spacing={3}>
          {services.map((service, index) => (
            <Grid item xs={12} sm={6} md={4} key={index}>
              <Card>
                <CardContent>
                  <Typography variant="h5" component="h2" gutterBottom>
                    {service.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {service.description}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Container>
    </Box>
  );
}

export default Services;