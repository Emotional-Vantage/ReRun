import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Landing from './pages/Landing';
import NewProject from './pages/NewProject';
import Dashboard from './pages/Dashboard';
import Report from './pages/Report';
import DevTear from './pages/DevTear';
import NotFound from './pages/NotFound';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/new" element={<NewProject />} />
        <Route path="/p/:id" element={<Dashboard />} />
        <Route path="/p/:id/report" element={<Report />} />
        <Route path="/dev/tear" element={<DevTear />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
