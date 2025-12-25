/**
 * ACHNewPage - Create new ACH analysis
 *
 * Sub-route: /ach/new
 * This is a wrapper that redirects to the main ACHPage create view.
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export function ACHNewPage() {
  const navigate = useNavigate();

  useEffect(() => {
    // Redirect to main ACH page with new view
    navigate('/ach?view=new', { replace: true });
  }, [navigate]);

  return null;
}
