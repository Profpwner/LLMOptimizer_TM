import React, { useState, useCallback } from 'react';
import {
  Box,
  Button,
  Paper,
  Typography,
  Alert,
  CircularProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  LinearProgress,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TableContainer
} from '@mui/material';
import GridLegacyLegacy from '@mui/material/GridLegacyLegacy';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import DeleteIcon from '@mui/icons-material/Delete';
import DownloadIcon from '@mui/icons-material/Download';
import { useUploadBatchMutation } from '../../services/contentApi';

interface FileItem {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'failed';
  progress: number;
  error?: string;
  itemCount?: number;
}

export default function BatchUpload() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [contentType, setContentType] = useState('article');
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [uploadBatch, { isLoading }] = useUploadBatchMutation();

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const validateFile = (file: File): string | null => {
    const validTypes = ['text/csv', 'text/plain', 'application/json'];
    const maxSize = 10 * 1024 * 1024; // 10MB

    if (!validTypes.includes(file.type)) {
      return 'Invalid file type. Please upload CSV, TXT, or JSON files.';
    }

    if (file.size > maxSize) {
      return 'File size exceeds 10MB limit.';
    }

    return null;
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    setError(null);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(Array.from(e.dataTransfer.files));
    }
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      handleFiles(Array.from(e.target.files));
    }
  };

  const handleFiles = (newFiles: File[]) => {
    const validFiles: FileItem[] = [];
    const errors: string[] = [];

    newFiles.forEach(file => {
      const error = validateFile(file);
      if (error) {
        errors.push(`${file.name}: ${error}`);
      } else {
        validFiles.push({
          id: Date.now().toString() + Math.random(),
          file,
          status: 'pending',
          progress: 0
        });
      }
    });

    if (errors.length > 0) {
      setError(errors.join('\n'));
    }

    if (validFiles.length > 0) {
      setFiles(prev => [...prev, ...validFiles]);
    }
  };

  const handleRemoveFile = (id: string) => {
    setFiles(prev => prev.filter(f => f.id !== id));
  };

  const handleUpload = async () => {
    setError(null);

    for (const fileItem of files) {
      if (fileItem.status !== 'pending') continue;

      try {
        // Update status to uploading
        setFiles(prev => prev.map(f => 
          f.id === fileItem.id ? { ...f, status: 'uploading', progress: 0 } : f
        ));

        const formData = new FormData();
        formData.append('file', fileItem.file);
        formData.append('content_type', contentType);

        // Simulate progress (in real app, use XMLHttpRequest or fetch with progress)
        const progressInterval = setInterval(() => {
          setFiles(prev => prev.map(f => 
            f.id === fileItem.id && f.progress < 90
              ? { ...f, progress: f.progress + 10 }
              : f
          ));
        }, 200);

        const response = await uploadBatch(formData).unwrap();

        clearInterval(progressInterval);

        // Update file status
        setFiles(prev => prev.map(f => 
          f.id === fileItem.id
            ? { 
                ...f, 
                status: 'completed', 
                progress: 100,
                itemCount: response.items_processed
              }
            : f
        ));

      } catch (err: any) {
        setFiles(prev => prev.map(f => 
          f.id === fileItem.id
            ? { 
                ...f, 
                status: 'failed', 
                error: err.data?.detail || 'Upload failed'
              }
            : f
        ));
      }
    }
  };

  const getFileIcon = (status: FileItem['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon color="success" />;
      case 'failed':
        return <ErrorIcon color="error" />;
      default:
        return <InsertDriveFileIcon />;
    }
  };

  const pendingFiles = files.filter(f => f.status === 'pending').length;
  const completedFiles = files.filter(f => f.status === 'completed').length;

  const downloadTemplate = () => {
    const csvContent = `title,content,keywords,target_audience
"Sample Article Title","This is the content of the article that needs optimization.","keyword1,keyword2","tech professionals"
"Another Article","More content here that will be optimized by the LLM.","seo,marketing","marketers"`;

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'content_template.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Box>
      <GridLegacyLegacy container spacing={3}>
        <GridLegacyLegacy item xs={12}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Upload CSV, TXT, or JSON files containing multiple content items for batch processing.
            Maximum file size: 10MB.
          </Typography>
          <Button
            size="small"
            startIcon={<DownloadIcon />}
            onClick={downloadTemplate}
            sx={{ mt: 1 }}
          >
            Download CSV Template
          </Button>
        </GridLegacy>

        <GridLegacy item xs={12} md={6}>
          <FormControl fullWidth>
            <InputLabel>Default Content Type</InputLabel>
            <Select
              value={contentType}
              onChange={(e) => setContentType(e.target.value)}
              label="Default Content Type"
            >
              <MenuItem value="article">Article</MenuItem>
              <MenuItem value="blog_post">Blog Post</MenuItem>
              <MenuItem value="product_description">Product Description</MenuItem>
              <MenuItem value="email">Email</MenuItem>
            </Select>
          </FormControl>
        </GridLegacy>

        <GridLegacy item xs={12}>
          <Paper
            variant="outlined"
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            sx={{
              p: 4,
              textAlign: 'center',
              cursor: 'pointer',
              backgroundColor: dragActive ? 'action.hover' : 'background.paper',
              border: dragActive ? '2px dashed primary.main' : '2px dashed grey.300'
            }}
          >
            <input
              type="file"
              id="file-upload"
              multiple
              accept=".csv,.txt,.json"
              onChange={handleFileInput}
              style={{ display: 'none' }}
            />
            <label htmlFor="file-upload">
              <CloudUploadIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" gutterBottom>
                Drag and drop files here
              </Typography>
              <Typography variant="body2" color="text.secondary">
                or click to browse
              </Typography>
              <Button
                variant="contained"
                component="span"
                sx={{ mt: 2 }}
                startIcon={<CloudUploadIcon />}
              >
                Choose Files
              </Button>
            </label>
          </Paper>
        </GridLegacy>

        {files.length > 0 && (
          <GridLegacy item xs={12}>
            <TableContainer component={Paper} variant="outlined">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>File Name</TableCell>
                    <TableCell>Size</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Items</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {files.map((fileItem) => (
                    <TableRow key={fileItem.id}>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {getFileIcon(fileItem.status)}
                          <Typography variant="body2">{fileItem.file.name}</Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        {(fileItem.file.size / 1024).toFixed(1)} KB
                      </TableCell>
                      <TableCell>
                        <Box>
                          <Chip
                            label={fileItem.status}
                            size="small"
                            color={
                              fileItem.status === 'completed' ? 'success' :
                              fileItem.status === 'failed' ? 'error' :
                              fileItem.status === 'uploading' || fileItem.status === 'processing' ? 'primary' :
                              'default'
                            }
                          />
                          {(fileItem.status === 'uploading' || fileItem.status === 'processing') && (
                            <LinearProgress
                              variant="determinate"
                              value={fileItem.progress}
                              sx={{ mt: 1, width: 100 }}
                            />
                          )}
                          {fileItem.error && (
                            <Typography variant="caption" color="error" display="block">
                              {fileItem.error}
                            </Typography>
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>
                        {fileItem.itemCount ? fileItem.itemCount : '-'}
                      </TableCell>
                      <TableCell align="right">
                        <IconButton
                          onClick={() => handleRemoveFile(fileItem.id)}
                          disabled={fileItem.status === 'uploading' || fileItem.status === 'processing'}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </GridLegacy>
        )}

        {error && (
          <GridLegacy item xs={12}>
            <Alert severity="error" onClose={() => setError(null)}>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{error}</pre>
            </Alert>
          </GridLegacy>
        )}

        {completedFiles > 0 && (
          <GridLegacy item xs={12}>
            <Alert severity="success">
              Successfully uploaded {completedFiles} file{completedFiles > 1 ? 's' : ''}!
            </Alert>
          </GridLegacy>
        )}

        <GridLegacy item xs={12}>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="contained"
              startIcon={isLoading ? <CircularProgress size={20} /> : <CloudUploadIcon />}
              onClick={handleUpload}
              disabled={isLoading || pendingFiles === 0}
            >
              {isLoading ? 'Uploading...' : `Upload ${pendingFiles} File${pendingFiles !== 1 ? 's' : ''}`}
            </Button>
          </Box>
        </GridLegacy>
      </GridLegacy>
    </Box>
  );
}