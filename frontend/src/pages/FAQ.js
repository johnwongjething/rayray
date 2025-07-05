import React from 'react';
import { Typography, Box, Accordion, AccordionSummary, AccordionDetails } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

const faqs = [
  {
    question: 'What is the difference between CTN and BSC?',
    answer: 'CTN (Electronic Cargo Tracking Note) is the English name for BSC (Bordereau de Suivi des Cargaisons) in French. They serve the same purpose but are used in different regions.'
  },
  {
    question: 'Why is an ECTN Certificate required?',
    answer: 'An ECTN Certificate is required for cargo tracking and customs clearance in certain countries.'
  },
  {
    question: 'Which countries require an ECTN Certificate?',
    answer: 'Countries in West and Central Africa, among others, require an ECTN Certificate for imports.'
  },
  {
    question: 'How does the ECTN Certificate process work?',
    answer: 'The process involves submitting shipping documents, paying fees, and receiving the certificate for customs clearance.'
  },
  {
    question: 'How long does it take to get an ECTN Certificate?',
    answer: 'It usually takes 1-3 business days after submitting all required documents and payment.'
  },
  {
    question: 'What documents are needed for ECTN application?',
    answer: 'Typically, a Bill of Lading, Commercial Invoice, and Export Customs Declaration are required.'
  }
];

function FAQ({ t = x => x }) {
  return (
    <Box
      sx={{
        backgroundImage: 'url(/assets/faq.jpg)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        minHeight: '100vh',
        py: 8,
      }}
    >
      <Box maxWidth="md" sx={{ mx: 'auto', background: 'rgba(255,255,255,0.95)', borderRadius: 2, py: 4, px: 4, mt: 6 }}>
        <Typography variant="h3" component="h1" gutterBottom>
          {t('faqHeader')}
        </Typography>
        {faqs.map((faq, idx) => (
          <Accordion key={idx} sx={{ mb: 2 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1" fontWeight="bold">{faq.question}</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography>{faq.answer}</Typography>
            </AccordionDetails>
          </Accordion>
        ))}
      </Box>
    </Box>
  );
}

export default FAQ; 