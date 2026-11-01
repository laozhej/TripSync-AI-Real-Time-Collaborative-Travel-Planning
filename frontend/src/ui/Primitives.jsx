import React, {useEffect, useRef, useState} from 'react';

export function Badge({children, tone = 'neutral'}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function SectionTitle({title, description, children}) {
  return <div className="sectionTitle"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{children}</div>;
}

export function ThemeToggle() {
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('tripsync-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'); }
    catch { return 'light'; }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('tripsync-theme', theme); } catch { /* Storage is optional. */ }
  }, [theme]);
  return <button className="themeToggle secondary" aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`} onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>{theme === 'light' ? 'Dark theme' : 'Light theme'}</button>;
}

export function ConfirmDialog({title, children, confirmLabel, busy, onConfirm, onClose}) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement;
    dialog.showModal();
    return () => { dialog.close(); previous?.focus(); };
  }, []);
  return <dialog ref={ref} className="confirmDialog" aria-labelledby="confirmation-title" onCancel={event => {event.preventDefault(); if (!busy) onClose();}}>
    <h2 id="confirmation-title">{title}</h2>{children}
    <div className="actions"><button className="secondary" disabled={busy} onClick={onClose} autoFocus>Cancel</button><button className="primary" disabled={busy} onClick={onConfirm}>{busy ? 'Activating…' : confirmLabel}</button></div>
  </dialog>;
}
