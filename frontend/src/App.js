import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import {
  Container, CssBaseline, Box, Typography, TextField, Button, CircularProgress,
  Paper, Grid, Link, Chip, Stack, Tooltip, keyframes, Stepper, Step, StepLabel,
  IconButton
} from '@mui/material';
import { createTheme, ThemeProvider, styled } from '@mui/material/styles';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import DownloadIcon from '@mui/icons-material/Download';
import DescriptionIcon from '@mui/icons-material/Description';
import WebIcon from '@mui/icons-material/Web';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';

// --- Animations ---
const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
`;

const pulse = keyframes`
  0% { box-shadow: 0 0 0 0 rgba(22, 163, 74, 0.7); }
  70% { box-shadow: 0 0 0 10px rgba(22, 163, 74, 0); }
  100% { box-shadow: 0 0 0 0 rgba(22, 163, 74, 0); }
`;

// --- Dynamic Theme ---
const getTheme = (mode) => createTheme({
  palette: {
    mode,
    ...(mode === 'light'
      ? {
          // Professional Light Theme
          primary: { main: '#16a34a' },
          secondary: { main: '#475569' },
          background: { default: '#f8fafc', paper: '#ffffff' },
          text: { primary: '#1e293b', secondary: '#64748b' },
        }
      : {
          // Professional Dark Theme
          primary: { main: '#22c55e' },
          secondary: { main: '#94a3b8' },
          background: { default: '#0f172a', paper: '#1e293b' },
          text: { primary: '#f1f5f9', secondary: '#cbd5e1' },
        }),
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h2: { fontWeight: 700, color: mode === 'light' ? '#0f172a' : '#f1f5f9' },
    h5: { fontWeight: 600, color: mode === 'light' ? '#334155' : '#e2e8f0' },
    body1: { color: mode === 'light' ? '#475569' : '#cbd5e1' },
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: '16px',
          backgroundImage: 'none', // Important for dark mode paper
          boxShadow: mode === 'light'
            ? '0 4px 12px rgba(0,0,0,0.05)'
            : '0 4px 12px rgba(0,0,0,0.2)',
          transition: 'transform 0.3s ease-in-out, box-shadow 0.3s ease-in-out',
          '&:hover': {
            transform: 'translateY(-4px)',
            boxShadow: mode === 'light'
              ? '0 8px 24px rgba(0,0,0,0.08)'
              : '0 8px 24px rgba(0,0,0,0.3)',
          }
        }
      }
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: '8px',
          textTransform: 'none',
          fontWeight: 600,
          padding: '10px 20px',
        },
        containedPrimary: {
          color: 'white',
        }
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: '8px',
          },
        },
      },
    },
  },
});


// --- Custom Stepper Styling ---
const ColorlibStepIconRoot = styled('div')(
  ({ theme, ownerState }) => ({
    backgroundColor: theme.palette.mode === 'dark' ? theme.palette.grey[700] : '#ccc',
    zIndex: 1,
    color: '#fff',
    width: 40,
    height: 40,
    display: 'flex',
    borderRadius: '50%',
    justifyContent: 'center',
    alignItems: 'center',
    ...(ownerState.active && {
      backgroundColor: theme.palette.primary.main,
      boxShadow: '0 4px 10px 0 rgba(0,0,0,.25)',
    }),
    ...(ownerState.completed && {
      backgroundColor: theme.palette.primary.main,
    }),
  }),
);

function ColorlibStepIcon(props) {
  const { active, completed, className } = props;
  const icons = {
    1: <UploadFileIcon />,
    2: <WebIcon />,
    3: <DownloadIcon />,
  };
  return (
    <ColorlibStepIconRoot ownerState={{ completed, active }} className={className}>
      {icons[String(props.icon)]}
    </ColorlibStepIconRoot>
  );
}

const API_BASE_URL = 'https://medical-data-generator.onrender.com';

function App() {
  const [mode, setMode] = useState('light');
  const theme = useMemo(() => getTheme(mode), [mode]);

  const [diseaseName, setDiseaseName] = useState('');
  const [url, setUrl] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [status, setStatus] = useState('Welcome! Please follow the steps to generate your dataset.');
  const [isLoading, setIsLoading] = useState(false);
  const [processedFileId, setProcessedFileId] = useState(null);
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    if (processedFileId) {
        setActiveStep(3);
    } else if (selectedFile && diseaseName && url) {
        setActiveStep(2);
    } else if (selectedFile) {
        setActiveStep(1);
    } else {
        setActiveStep(0);
    }
  }, [selectedFile, diseaseName, url, processedFileId]);


  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file && file.type === "text/csv") {
      setSelectedFile(file);
      setProcessedFileId(null);
      setStatus(`Base file selected: ${file.name}. Please provide the disease context.`);
    } else {
      setSelectedFile(null);
      setStatus("Invalid file. Please select a valid .csv file.");
    }
  };

  const handleProcess = async () => {
    if (!selectedFile || !diseaseName || !url) {
      setStatus('Error: You must complete all steps before processing.');
      return;
    }
    setIsLoading(true);
    setProcessedFileId(null);
    setStatus('Processing... This may take a moment.');

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('disease_name', diseaseName);
    formData.append('url', url);

    try {
      const response = await axios.post(`${API_BASE_URL}/process`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setProcessedFileId(response.data.file_id);
      setStatus(`✅ Success: ${response.data.message}`);
    } catch (error) {
      setStatus(`❌ Error: ${error.response?.data?.detail || error.message}`);
    }
    setIsLoading(false);
  };

  const handleDownload = () => {
    if (!processedFileId) return;
    window.open(`${API_BASE_URL}/download/${processedFileId}`, '_blank');
  };

  const handleDownloadTemplate = () => {
    window.open(`${API_BASE_URL}/template`, '_blank');
  };

  const steps = ['Upload Base File', 'Provide Context', 'Generate & Download'];

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ minHeight: '100vh', backgroundColor: 'background.default', p: { xs: 2, sm: 4 }, pb: 4 }}>
        <Container maxWidth="lg" sx={{position: 'relative'}}>
           <Box sx={{ position: 'absolute', top: { xs: -8, sm: 8 }, right: { xs: -8, sm: 0 }, zIndex: 1100 }}>
             <Tooltip title={`Switch to ${mode === 'light' ? 'dark' : 'light'} mode`}>
                <IconButton onClick={() => setMode(prev => prev === 'light' ? 'dark' : 'light')} sx={{ color: 'text.primary' }}>
                   {mode === 'dark' ? <Brightness7Icon /> : <Brightness4Icon />}
                </IconButton>
             </Tooltip>
          </Box>

          <Box sx={{ my: 4, textAlign: 'center', animation: `${fadeIn} 0.5s ease-out` }}>
            <Typography variant="h2" component="h1" gutterBottom>
              MedData Synthesizer
            </Typography>
            <Typography variant="h6" color="text.secondary">
              Turn medical articles into structured clinical datasets with AI.
            </Typography>
          </Box>

          {/* --- Status Log (now always on top) --- */}
          <Paper sx={{ p: 2, mb: 4, animation: `${fadeIn} 1.1s ease-out 0.6s`, animationFillMode: 'backwards' }}>
              <Typography variant="h6" gutterBottom>Status Log</Typography>
              <Box sx={{
                  p: 2,
                  backgroundColor: mode === 'dark' ? '#334155' : '#eef2f6',
                  color: mode === 'dark' ? '#cbd5e1' : '#334155',
                  borderRadius: '8px',
                  minHeight: 80,
                  fontFamily: 'monospace',
                  whiteSpace: 'pre-wrap',
              }}>
                  {status}
              </Box>
          </Paper>

          {/* --- Steps Content --- */}
          <Paper sx={{ p: { xs: 2, sm: 4 }, mb: 4, animation: `${fadeIn} 0.7s ease-out 0.2s`, animationFillMode: 'backwards' }}>
              <Stepper activeStep={activeStep} alternativeLabel sx={{ mb: 4 }}>
                  {steps.map((label) => (
                      <Step key={label}>
                          <StepLabel StepIconComponent={ColorlibStepIcon}>{label}</StepLabel>
                      </Step>
                  ))}
              </Stepper>

              <Grid container spacing={4} alignItems="center">
                  <Grid item xs={12} md={4}>
                      <Typography variant="h5" gutterBottom>Step 1: Base File</Typography>
                      <Typography variant="body1" sx={{ mb: 2 }}>
                          Select a CSV to append data to, or download a template to start fresh.
                      </Typography>
                      <Stack spacing={2}>
                          <Button variant="contained" component="label" startIcon={<UploadFileIcon />}>
                              Select CSV File
                              <input type="file" hidden accept=".csv" onChange={handleFileSelect} />
                          </Button>
                          <Button variant="outlined" onClick={handleDownloadTemplate} startIcon={<DescriptionIcon />}>
                              Download Template
                          </Button>
                          {selectedFile && <Chip label={selectedFile.name} onDelete={() => { setSelectedFile(null); setProcessedFileId(null); }} />}
                      </Stack>
                  </Grid>
                  <Grid item xs={12} md={8}>
                      <Typography variant="h5" gutterBottom>Step 2: Context</Typography>
                      <Typography variant="body1" sx={{ mb: 2 }}>
                          Provide the name of the disease and a trusted medical source URL.
                      </Typography>
                      <Stack spacing={2}>
                          <TextField fullWidth required label="Disease Name" variant="outlined" value={diseaseName} onChange={(e) => setDiseaseName(e.target.value)} disabled={isLoading} />
                          <TextField fullWidth required label="Medical Source URL" variant="outlined" value={url} onChange={(e) => setUrl(e.target.value)} disabled={isLoading} />
                      </Stack>
                  </Grid>
              </Grid>
          </Paper>

          <Paper sx={{ p: { xs: 2, sm: 4 }, mb: 4, textAlign: 'center', animation: `${fadeIn} 0.9s ease-out 0.4s`, animationFillMode: 'backwards' }}>
              <Typography variant="h5" gutterBottom>Step 3: Generate & Download</Typography>
              <Typography variant="body1" sx={{ mb: 2 }}>
                  Once all fields are complete, you can process the data and download the result.
              </Typography>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} justifyContent="center">
                  <Button
                      variant="contained"
                      size="large"
                      onClick={handleProcess}
                      disabled={isLoading || !selectedFile || !diseaseName || !url}
                      startIcon={isLoading ? <CircularProgress size={20} color="inherit" /> : null}
                      sx={{ animation: (!isLoading && selectedFile && diseaseName && url) ? `${pulse} 2s infinite` : 'none' }}
                  >
                      {isLoading ? 'Processing...' : 'Process & Append Data'}
                  </Button>
                  <Button
                      variant="outlined"
                      size="large"
                      onClick={handleDownload}
                      disabled={isLoading || !processedFileId}
                      startIcon={<DownloadIcon />}
                  >
                      Download Result
                  </Button>
              </Stack>
          </Paper>

        </Container>
      </Box>
    </ThemeProvider>
  );
}

export default App;
