import React, { useState } from 'react';
import {
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
} from '@mui/material';
import {
  Download as DownloadIcon,
  PictureAsPdf as PdfIcon,
  Image as ImageIcon,
  TableChart as CsvIcon,
  Print as PrintIcon,
} from '@mui/icons-material';
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';
import { format } from 'date-fns';

const ExportMenu: React.FC = () => {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const exportToPDF = async () => {
    const dashboardElement = document.querySelector('.layout');
    if (!dashboardElement) return;

    const canvas = await html2canvas(dashboardElement as HTMLElement, {
      scale: 2,
      useCORS: true,
      logging: false,
    });

    const imgData = canvas.toDataURL('image/png');
    const pdf = new jsPDF({
      orientation: 'landscape',
      unit: 'px',
      format: [canvas.width, canvas.height],
    });

    pdf.addImage(imgData, 'PNG', 0, 0, canvas.width, canvas.height);
    pdf.save(`dashboard-${format(new Date(), 'yyyy-MM-dd-HHmm')}.pdf`);
    handleClose();
  };

  const exportToPNG = async () => {
    const dashboardElement = document.querySelector('.layout');
    if (!dashboardElement) return;

    const canvas = await html2canvas(dashboardElement as HTMLElement, {
      scale: 2,
      useCORS: true,
      logging: false,
    });

    const link = document.createElement('a');
    link.download = `dashboard-${format(new Date(), 'yyyy-MM-dd-HHmm')}.png`;
    link.href = canvas.toDataURL();
    link.click();
    handleClose();
  };

  const exportToCSV = () => {
    // This would export the current data to CSV
    // Implementation would depend on the current data structure
    console.log('Export to CSV');
    handleClose();
  };

  const handlePrint = () => {
    window.print();
    handleClose();
  };

  return (
    <>
      <IconButton
        aria-label="export menu"
        aria-controls="export-menu"
        aria-haspopup="true"
        onClick={handleClick}
        color="inherit"
      >
        <DownloadIcon />
      </IconButton>
      <Menu
        id="export-menu"
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        MenuListProps={{
          'aria-labelledby': 'export-button',
        }}
      >
        <MenuItem onClick={exportToPDF}>
          <ListItemIcon>
            <PdfIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Export as PDF</ListItemText>
        </MenuItem>
        <MenuItem onClick={exportToPNG}>
          <ListItemIcon>
            <ImageIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Export as PNG</ListItemText>
        </MenuItem>
        <MenuItem onClick={exportToCSV}>
          <ListItemIcon>
            <CsvIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Export as CSV</ListItemText>
        </MenuItem>
        <Divider />
        <MenuItem onClick={handlePrint}>
          <ListItemIcon>
            <PrintIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Print</ListItemText>
        </MenuItem>
      </Menu>
    </>
  );
};

export default ExportMenu;