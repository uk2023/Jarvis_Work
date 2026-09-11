import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Activity,
  Database,
  FileSearch,
  Layers,
  Search,
  Sparkles,
  Terminal,
  X,
  ScanSearch,
  ChevronDown,
} from 'lucide-react';
import '../styles/admin-shell-enhancer.css';

const ITEMS = [
  { label: 'Monitor', title: 'Monitor (System Telemetry & Vitals)', icon: Activity },
  { label: 'Trace', title: 'Trace Inspector (Turn Execution & Latency Waterfall)', icon: FileSearch },
  { label: 'Memory & DB', title: 'Memory & Database (Schema Contracts & Evolution DB)', icon: Database },
  { label: 'Reasoning', title: 'System Reasoning (Overnight Learning & Self-Improvement)', icon: Sparkles },
  { label: 'Organs', title: 'Organs (Organ Introspection & Heartbeat Network)', icon: Layers },
  { label: 'Virtual CLI', title: 'Virtual CLI (Diagnostic Shell & Terminal)', icon: Terminal },
];

function legacyButton(title: string) {
  return Array.from(document.querySelectorAll<HTMLButtonElement>('button[title]')).find(
    button => button.getAttribute('title') === title && !button.closest('[data-jarvis-enhancer]'),
  );
}

function legacySubheader() {
  const monitor = legacyButton(ITEMS[0].title);
  return monitor?.parentElement?.parentElement as HTMLElement | undefined;
}

function activeLegacyTitle() {
  return ITEMS.find(item => legacyButton(item.title)?.className.includes('bg-brand-600'))?.title || '';
}

export function AdminShellEnhancer() {
  const [isAdmin, setIsAdmin] = useState(false);
  const [sidebarMount, setSidebarMount] = useState<HTMLElement | null>(null);
  const [headerMount, setHeaderMount] = useState<HTMLElement | null>(null);
  const [inspectionOpen, setInspectionOpen] = useState(false);
  const [activeTitle, setActiveTitle] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const checkAuth = () => {
      const next = !!localStorage.getItem('jarvis_operator_token');
      setIsAdmin(next);
      if (!next) setInspectionOpen(false);
    };
    checkAuth();
    const timer = window.setInterval(checkAuth, 500);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const install = () => {
      const header = document.querySelector('header');
      const rightTools = header?.lastElementChild as HTMLElement | null;
      if (rightTools && !rightTools.querySelector('.jarvis-header-search-mount')) {
        const host = document.createElement('div');
        host.className = 'jarvis-header-search-mount';
        host.setAttribute('data-jarvis-enhancer', 'header-search-host');
        rightTools.insertBefore(host, rightTools.firstElementChild);
        setHeaderMount(host);
      }
    };
    install();
    const installTimer = window.setTimeout(install, 120);
    const resize = () => install();
    window.addEventListener('resize', resize);
    return () => {
      window.clearTimeout(installTimer);
      window.removeEventListener('resize', resize);
    };
  }, []);

  useEffect(() => {
    if (!isAdmin) {
      const subheader = legacySubheader();
      if (subheader) subheader.style.display = '';
      setSidebarMount(null);
      return;
    }

    const sync = () => {
      const subheader = legacySubheader();
      const active = activeLegacyTitle();
      setActiveTitle(active);
      if (subheader) subheader.style.display = active ? '' : 'none';
    };

    const install = () => {
      const aside = document.querySelector('aside');
      const newChat = aside
        ? Array.from(aside.querySelectorAll<HTMLButtonElement>('button')).find(
            button => button.getAttribute('title') === 'New Chat',
          )
        : undefined;

      if (newChat?.parentElement && !newChat.parentElement.querySelector('.jarvis-inspection-mount')) {
        const host = document.createElement('div');
        host.className = 'jarvis-inspection-mount';
        host.setAttribute('data-jarvis-enhancer', 'inspection-host');
        newChat.parentElement.insertAdjacentElement('afterend', host);
        setSidebarMount(host);
      }
      sync();
    };

    install();
    const installTimer = window.setTimeout(install, 120);
    const resize = () => install();
    window.addEventListener('resize', resize);

    const appRoot = document.getElementById('app-root') || document.body;
    const observer = new MutationObserver(() => {
      install();
      sync();
    });
    observer.observe(appRoot, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });

    return () => {
      window.clearTimeout(installTimer);
      window.removeEventListener('resize', resize);
      observer.disconnect();
      const subheader = legacySubheader();
      if (subheader) subheader.style.display = '';
      document.querySelectorAll('.jarvis-inspection-mount').forEach(el => el.remove());
      setSidebarMount(null);
    };
  }, [isAdmin]);

  const activate = (title: string) => {
    const button = legacyButton(title);
    if (!button) return;
    button.click();
    setInspectionOpen(false);
    window.setTimeout(() => {
      const active = activeLegacyTitle();
      setActiveTitle(active);
      const subheader = legacySubheader();
      if (subheader) subheader.style.display = active ? '' : 'none';
    }, 0);
  };

  useEffect(() => {
    if (!searchOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSearchOpen(false);
        setSearchQuery('');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [searchOpen]);

  return (
    <>
      {isAdmin && sidebarMount && createPortal(
        <div className="jarvis-inspection" data-jarvis-enhancer>
          <button
            type="button"
            className={`jarvis-inspection-trigger ${inspectionOpen ? 'is-open' : ''}`}
            onClick={() => setInspectionOpen(value => !value)}
            aria-expanded={inspectionOpen}
            title="Inspection navigation"
          >
            <span className="jarvis-inspection-trigger-main">
              <ScanSearch size={16} strokeWidth={1.9} />
              <span>Inspection</span>
            </span>
            <ChevronDown size={14} className="jarvis-inspection-chevron" strokeWidth={2} />
          </button>

          <div className={`jarvis-inspection-grid ${inspectionOpen ? 'is-open' : ''}`}>
            {ITEMS.map(({ label, title, icon: Icon }) => (
              <button
                key={title}
                type="button"
                onClick={() => activate(title)}
                className={`jarvis-inspection-item ${activeTitle === title ? 'is-active' : ''}`}
                title={title}
              >
                <Icon size={15} strokeWidth={1.9} />
                <span>{label}</span>
              </button>
            ))}
          </div>
        </div>,
        sidebarMount,
      )}

      {headerMount && createPortal(
        <div className={`jarvis-header-search ${searchOpen ? 'is-open' : ''}`} data-jarvis-enhancer>
          {searchOpen && (
            <input
              autoFocus
              value={searchQuery}
              onChange={event => setSearchQuery(event.target.value)}
              placeholder="Search JARVIS..."
              aria-label="Search JARVIS"
            />
          )}
          {searchOpen && searchQuery && (
            <button
              type="button"
              className="jarvis-header-search-clear"
              onClick={() => setSearchQuery('')}
              title="Clear search"
            >
              <X size={14} />
            </button>
          )}
          <button
            type="button"
            className="jarvis-header-search-button"
            onClick={() => {
              setSearchOpen(value => !value);
              if (searchOpen) setSearchQuery('');
            }}
            title={searchOpen ? 'Close search' : 'Search'}
            aria-label={searchOpen ? 'Close search' : 'Search'}
          >
            {searchOpen ? <X size={17} /> : <Search size={17} />}
          </button>
        </div>,
        headerMount,
      )}
    </>
  );
}
