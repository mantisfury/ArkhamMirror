/**
 * ACHListPage - List of all ACH matrices
 *
 * Sub-route: /ach/matrices
 * This is a wrapper that redirects to the main ACHPage list view.
 */

import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

export function ACHListPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    // Redirect to main ACH page with list view
    // Preserve any existing query params
    const params = new URLSearchParams(searchParams);
    params.delete('matrixId'); // Ensure we show the list
    params.set('view', 'list');
    navigate(`/ach?${params.toString()}`, { replace: true });
  }, [navigate, searchParams]);

  return null;
}
