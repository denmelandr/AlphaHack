import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './style.css';
import './mobile.css';
import { TooltipProvider } from './components/ui/tooltip';
import { MotionConfig } from 'motion/react';
createRoot(document.getElementById('root')!).render(<React.StrictMode><MotionConfig reducedMotion="user"><TooltipProvider delayDuration={250}><App /></TooltipProvider></MotionConfig></React.StrictMode>);
