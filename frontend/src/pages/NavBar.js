import React, { useState } from 'react';
import { AppBar, Toolbar, Typography, Button, Select, MenuItem, IconButton, Drawer, List, ListItem, ListItemText, Box } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import { Link } from 'react-router-dom';
import { useTheme, useMediaQuery } from '@mui/material';

const NavBar = ({ lang, setLang, t }) => {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const navLinks = [
    { to: '/', label: t('home') },
    { to: '/about', label: t('about') },
    { to: '/services', label: t('services') },
    { to: '/contact', label: t('contact') },
    { to: '/faq', label: t('faq') },
    { to: '/login', label: t('login') },
    { to: '/register', label: t('register') },
  ];

  return (
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" sx={{ flexGrow: 1 }}>
          Logistics Company
        </Typography>
        {isMobile ? (
          <>
            <IconButton
              color="inherit"
              edge="end"
              onClick={() => setDrawerOpen(true)}
              sx={{ ml: 1 }}
            >
              <MenuIcon />
            </IconButton>
            <Drawer
              anchor="right"
              open={drawerOpen}
              onClose={() => setDrawerOpen(false)}
            >
              <Box sx={{ width: 220 }}>
                <List>
                  {navLinks.map(link => (
                    <ListItem button component={Link} to={link.to} key={link.to} onClick={() => setDrawerOpen(false)}>
                      <ListItemText primary={link.label} />
                    </ListItem>
                  ))}
                  <ListItem>
                    <Select
                      value={lang}
                      onChange={e => {
                        setLang(e.target.value);
                        localStorage.setItem('lang', e.target.value);
                      }}
                      size="small"
                      sx={{ color: 'black', minWidth: 80 }}
                    >
                      <MenuItem value="en">EN</MenuItem>
                      <MenuItem value="zh">中文</MenuItem>
                      <MenuItem value="fr">FR</MenuItem>
                    </Select>
                  </ListItem>
                </List>
              </Box>
            </Drawer>
          </>
        ) : (
          <>
            {navLinks.map(link => (
              <Button color="inherit" component={Link} to={link.to} key={link.to}>
                {link.label}
              </Button>
            ))}
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
          </>
        )}
      </Toolbar>
    </AppBar>
  );
};

export default NavBar;