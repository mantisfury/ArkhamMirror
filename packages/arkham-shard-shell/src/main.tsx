/**
 * Main entry point for the UI Shell
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';

// Local fonts (air-gap safe - no external CDN requests)
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';

import './styles/index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
