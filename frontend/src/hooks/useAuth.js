import { useContext } from 'react';
import { AuthContext } from '../contexts/AuthContext';

// Hook for reading auth state. Kept in its own file so the
// AuthContext file only exports the context and the provider
// component (react-refresh rule).
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
