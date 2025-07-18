import React, { useState } from 'react';
import {
  Box,
  Tabs,
  Tab,
  Paper,
  Typography,
  Container
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import LinkIcon from '@mui/icons-material/Link';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import DirectContentInput from './DirectContentInput';
import URLContentInput from './URLContentInput';
import BatchUpload from './BatchUpload';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`content-tabpanel-${index}`}
      aria-labelledby={`content-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

function a11yProps(index: number) {
  return {
    id: `content-tab-${index}`,
    'aria-controls': `content-tabpanel-${index}`,
  };
}

export default function ContentInputTabs() {
  const [value, setValue] = useState(0);

  const handleChange = (event: React.SyntheticEvent, newValue: number) => {
    setValue(newValue);
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Content Input
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        Submit content for LLM optimization through various methods
      </Typography>

      <Paper sx={{ width: '100%' }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={value} onChange={handleChange} aria-label="content input tabs">
            <Tab 
              icon={<EditIcon />} 
              label="Direct Input" 
              {...a11yProps(0)} 
              iconPosition="start"
            />
            <Tab 
              icon={<LinkIcon />} 
              label="URL Input" 
              {...a11yProps(1)} 
              iconPosition="start"
            />
            <Tab 
              icon={<UploadFileIcon />} 
              label="Batch Upload" 
              {...a11yProps(2)} 
              iconPosition="start"
            />
          </Tabs>
        </Box>
        <TabPanel value={value} index={0}>
          <DirectContentInput />
        </TabPanel>
        <TabPanel value={value} index={1}>
          <URLContentInput />
        </TabPanel>
        <TabPanel value={value} index={2}>
          <BatchUpload />
        </TabPanel>
      </Paper>
    </Container>
  );
}