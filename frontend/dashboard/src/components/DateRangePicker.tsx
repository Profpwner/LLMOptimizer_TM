import React, { useState } from 'react';
import {
  Button,
  Popover,
  Box,
  TextField,
  Stack,
  ButtonGroup,
  Typography,
} from '@mui/material';
import { CalendarMonth as CalendarIcon } from '@mui/icons-material';
import { format, subDays, startOfDay, endOfDay } from 'date-fns';
import { useAppSelector, useAppDispatch } from '../hooks/redux';
import { setDateRange } from '../store/slices/dashboardSlice';

const DateRangePicker: React.FC = () => {
  const dispatch = useAppDispatch();
  const { dateRange } = useAppSelector((state) => state.dashboard);
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleQuickSelect = (days: number) => {
    const end = endOfDay(new Date());
    const start = startOfDay(subDays(end, days));
    dispatch(setDateRange({
      start: start.toISOString(),
      end: end.toISOString(),
    }));
    handleClose();
  };

  const handleCustomRange = (field: 'start' | 'end', value: string) => {
    const date = new Date(value);
    dispatch(setDateRange({
      ...dateRange,
      [field]: field === 'start' ? startOfDay(date).toISOString() : endOfDay(date).toISOString(),
    }));
  };

  const open = Boolean(anchorEl);
  const id = open ? 'date-range-popover' : undefined;

  const formatDisplay = () => {
    const start = new Date(dateRange.start);
    const end = new Date(dateRange.end);
    return `${format(start, 'MMM d, yyyy')} - ${format(end, 'MMM d, yyyy')}`;
  };

  return (
    <>
      <Button
        aria-describedby={id}
        variant="outlined"
        onClick={handleClick}
        startIcon={<CalendarIcon />}
        size="small"
        sx={{ mr: 2, color: 'inherit', borderColor: 'inherit' }}
      >
        {formatDisplay()}
      </Button>
      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
      >
        <Box sx={{ p: 3, minWidth: 320 }}>
          <Typography variant="h6" gutterBottom>
            Select Date Range
          </Typography>
          
          <Stack spacing={2}>
            <ButtonGroup orientation="vertical" fullWidth>
              <Button onClick={() => handleQuickSelect(0)}>Today</Button>
              <Button onClick={() => handleQuickSelect(7)}>Last 7 days</Button>
              <Button onClick={() => handleQuickSelect(30)}>Last 30 days</Button>
              <Button onClick={() => handleQuickSelect(90)}>Last 90 days</Button>
            </ButtonGroup>

            <TextField
              label="Start Date"
              type="datetime-local"
              value={format(new Date(dateRange.start), "yyyy-MM-dd'T'HH:mm")}
              onChange={(e) => handleCustomRange('start', e.target.value)}
              fullWidth
              InputLabelProps={{ shrink: true }}
            />

            <TextField
              label="End Date"
              type="datetime-local"
              value={format(new Date(dateRange.end), "yyyy-MM-dd'T'HH:mm")}
              onChange={(e) => handleCustomRange('end', e.target.value)}
              fullWidth
              InputLabelProps={{ shrink: true }}
            />

            <Button variant="contained" onClick={handleClose} fullWidth>
              Apply
            </Button>
          </Stack>
        </Box>
      </Popover>
    </>
  );
};

export default DateRangePicker;