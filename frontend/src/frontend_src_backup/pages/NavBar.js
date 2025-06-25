import React from 'react';
import { AppBar, Toolbar, Typography, Button, Select, MenuItem } from '@mui/material';
import { Link } from 'react-router-dom';

const NavBar = ({ lang, setLang, t }) => (
  <AppBar position="static">
    <Toolbar>
      <Typography variant="h6" sx={{ flexGrow: 1 }}>
        Logistics Company
      </Typography>
      <Button color="inherit" component={Link} to="/">{t('home')}</Button>
      <Button color="inherit" component={Link} to="/about">{t('about')}</Button>
      <Button color="inherit" component={Link} to="/services">{t('services')}</Button>
      <Button color="inherit" component={Link} to="/contact">{t('contact')}</Button>
      <Button color="inherit" component={Link} to="/faq">{t('faq')}</Button>
      <Button color="inherit" component={Link} to="/login">{t('login')}</Button>
      <Button color="inherit" component={Link} to="/register">{t('register')}</Button>
      <Select
        value={lang}
        onChange={e => {
          setLang(e.target.value);
          localStorage.setItem('lang', e.target.value);
        }}
        size="small"
        sx={{ ml: 2, color: 'white', borderColor: 'white' }}
      >
        <MenuItem value="en">EN</MenuItem>
        <MenuItem value="zh">中文</MenuItem>
        <MenuItem value="fr">FR</MenuItem>
      </Select>
    </Toolbar>
  </AppBar>
);

export default NavBar; 