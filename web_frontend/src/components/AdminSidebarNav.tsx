import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Activity, FileSearch, Database, Sparkles, Layers, Terminal } from 'lucide-react';
import '../styles/admin-sidebar-nav.css';

const items = [
  { label: 'Monitor', title: 'Monitor (System Telemetry & Vitals)', icon: Activity },
  { label: 'Trace', title: 'Trace Inspector (Turn Execution & Latency Waterfall)', icon: FileSearch },
  { label: 'Memory & DB', title: 'Memory & Database (Schema Contracts & Evolution DB)', icon: Database },
  { label: 'Reasoning', title: 'System Reasoning (Overnight Learning & Self-Improvement)', icon: Sparkles },
  { label: 'Organs', title: 'Organs (Organ Introspection & Heartbeat Network)', icon: Layers },
  { label: 'Virtual CLI', title: 'Virtual CLI (Diagnostic Shell & Terminal)', icon: Terminal },
];

export function AdminSidebarNav() {
  const [mount, setMount] = useState<HTMLElement | null>(null);
  const [adminVisible, setAdminVisible] = useState(false);
  const [activeTitle, setActiveTitle] = useState('');

  useEffect(() => {
    const sync = () => {
      const monitorButton = Array.from(document.querySelectorAll('button[title]')).find(
        button => button.getAttribute('title') === items[0].title,
      );
      setAdminVisible(Boolean(monitorButton));
    };
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(document.getElementById('app-root') || document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!adminVisible) {
      setMount(null);
      return;
    }
    const aside = document.querySelector('aside');
    if (!aside) return;
    const host = document.createElement('div');
    host.className = 'jarvis-admin-sidebar-nav-host';
    const bottom = aside.lastElementChild;
    if (bottom) aside.insertBefore(host, bottom);
    else aside.appendChild(host);
    setMount(host);

    const syncActive = () => {
      const active = Array.from(aside.querySelectorAll('button[title]')).find(button => {
        const title = button.getAttribute('title') || '';
        return items.some(item => item.title === title) && button.className.includes('bg-brand-600');
      });
      setActiveTitle(active?.getAttribute('title') || '');
    };
    syncActive();
    const observer = new MutationObserver(syncActive);
    observer.observe(aside, { subtree: true, attributes: true, attributeFilter: ['class'] });
    return () => {
      observer.disconnect();
      host.remove();
      setMount(null);
    };
  }, [adminVisible]);

  const activate = (title: string) => {
    const button = Array.from(document.querySelectorAll('button[title]')).find(
      candidate => candidate.getAttribute('title') === title,
    ) as HTMLButtonElement | undefined;
    button?.click();
  };

  if (!mount || !adminVisible) return null;

  return createPortal(
    <div className="jarvis-admin-sidebar-nav" aria-label="JARVIS admin navigation">
      {items.map(({ label, title, icon: Icon }) => {
        const active = activeTitle === title;
        return (
          <button
            key={title}
            type="button"
            onClick={() => activate(title)}
            title={label}
            className={`jarvis-admin-sidebar-nav-item ${active ? 'is-active' : ''}`}
          >
            <Icon size={16} strokeWidth={1.9} />
            <span>{label}</span>
          </button>
        );
      })}
    </div>,
    mount,
  );
}
