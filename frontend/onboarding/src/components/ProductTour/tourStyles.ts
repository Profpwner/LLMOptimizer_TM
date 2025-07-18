export const tourStyles = {
  options: {
    arrowColor: '#fff',
    backgroundColor: '#fff',
    overlayColor: 'rgba(0, 0, 0, 0.5)',
    primaryColor: '#1976d2',
    textColor: '#333',
    width: undefined,
    zIndex: 10000,
  },
  beacon: {
    inner: {
      backgroundColor: '#1976d2',
    },
    outer: {
      backgroundColor: 'rgba(25, 118, 210, 0.2)',
      border: '2px solid #1976d2',
    },
  },
  tooltip: {
    borderRadius: 8,
    fontSize: 16,
  },
  tooltipContainer: {
    textAlign: 'left' as const,
  },
  tooltipContent: {
    padding: '20px 10px',
  },
  buttonNext: {
    backgroundColor: '#1976d2',
    borderRadius: 4,
    color: '#fff',
    fontFamily: 'inherit',
    fontSize: 14,
    padding: '8px 16px',
    '&:hover': {
      backgroundColor: '#1565c0',
    },
  },
  buttonBack: {
    color: '#1976d2',
    fontFamily: 'inherit',
    fontSize: 14,
    marginLeft: 'auto',
    marginRight: 5,
    padding: '8px 16px',
  },
  buttonClose: {
    color: '#666',
    fontFamily: 'inherit',
    fontSize: 14,
    padding: '8px 16px',
  },
  buttonSkip: {
    color: '#666',
    fontFamily: 'inherit',
    fontSize: 14,
    padding: '8px 16px',
  },
  spotlight: {
    backgroundColor: 'transparent',
    border: '2px solid #1976d2',
    borderRadius: 4,
  },
  overlay: {
    mixBlendMode: 'normal' as const,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
  },
};