import React, { useEffect, useRef, useState } from 'react';
import { Activity, Shield, Sparkles, ArrowUp, Mic, MicOff, Cpu, Brain, Zap, Command, ChevronDown, ChevronUp, Radio, Terminal } from 'lucide-react';
import { AppTheme } from '../types';
import '../styles/dashboard-tables.css';
import '../styles/jarvis-home.css';

interface HomeScreenProps {
  theme: AppTheme;
  onNavigateToView: (view: 'user_chat' | 'dashboard' | 'cli' | 'inspector') => void;
  onStartChatWithPrompt: (prompt: string) => void;
  isAdmin: boolean;
  onOpenAuth: () => void;
}

const QUICK_PROMPTS = [
  { label: 'Check status', meta: 'SYSTEM', icon: Zap, query: 'Show me current organism vitals and CPU status' },
  { label: 'Memory recall', meta: 'MEMORY', icon: Brain, query: 'Survey FAISS episodic memory for recent context' },
  { label: 'Overnight learning', meta: 'LEARNING', icon: Cpu, query: 'What was discovered during overnight idle learning?' },
];

const LOG_LINES = [
  'CORE ONLINE · native-first cognition ready',
  'MEMORY GRAPH · semantic index synchronized',
  'ORGANISM · heartbeat monitor active',
  'JARVIS · awaiting operator input',
];

export function HomeScreen({ theme, onNavigateToView, onStartChatWithPrompt, isAdmin, onOpenAuth }: HomeScreenProps) {
  const isDark = theme === 'dark';
  const [prompt, setPrompt] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isKeyboardOpen, setIsKeyboardOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [canExpand, setCanExpand] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const update = () => {
      const open = window.innerHeight - viewport.height > 120;
      setIsKeyboardOpen(open);
      if (open) setExpanded(false);
    };
    update();
    viewport.addEventListener('resize', update);
    viewport.addEventListener('scroll', update);
    return () => { viewport.removeEventListener('resize', update); viewport.removeEventListener('scroll', update); };
  }, []);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const lineHeight = 24;
    const maxHeight = lineHeight * 5;
    const naturalHeight = Math.max(el.scrollHeight, lineHeight * 2);
    setCanExpand(el.scrollHeight > lineHeight * 2 + 1);
    el.style.height = `${Math.min(naturalHeight, maxHeight)}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? 'auto' : 'hidden';
  }, [prompt, expanded]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    onStartChatWithPrompt(prompt.trim());
    setPrompt('');
    setExpanded(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(e); }
  };

  const toggleMic = () => {
    if (!isListening) {
      setIsListening(true);
      setTimeout(() => { setPrompt('JARVIS, check system status'); setIsListening(false); }, 1800);
    } else setIsListening(false);
  };

  return (
    <div className={`jarvis-home ${isKeyboardOpen ? 'keyboard-open' : ''} ${isDark ? 'jarvis-home-dark' : 'jarvis-home-light'}`}>
      <div className="jarvis-space-field" aria-hidden="true"><span className="jarvis-star s1" /><span className="jarvis-star s2" /><span className="jarvis-star s3" /><span className="jarvis-star s4" /><span className="jarvis-nebula n1" /><span className="jarvis-nebula n2" /></div>
      <main className="jarvis-home-main">
        <div className="jarvis-home-content">
          <section className="jarvis-hero">
            <div className="jarvis-black-hole" aria-label="JARVIS core">
              <div className="jarvis-orbit orbit-a" /><div className="jarvis-orbit orbit-b" /><div className="jarvis-orbit orbit-c" />
              <div className="jarvis-accretion" /><div className="jarvis-core-glow" /><div className="jarvis-core-void"><span /><span /><span /></div>
            </div>
            <div className="jarvis-identity">
              <div className="jarvis-eyebrow"><Radio size={11} /> JARVIS COGNITIVE OS <span>•</span> ONLINE</div>
              <h1>JARVIS</h1>
              <p>Intelligent, local-first cognition — ready when you are.</p>
            </div>
          </section>

          <section className={`jarvis-command-zone ${expanded ? 'is-expanded' : ''} ${isKeyboardOpen ? 'is-keyboard-collapsed' : ''}`}>
            <form onSubmit={handleSubmit} className="jarvis-composer" style={{ backgroundColor: 'var(--jarvis-surface)', borderColor: 'var(--jarvis-border)' }}>
              <div className="jarvis-input-wrap">
                <Sparkles size={14} className="jarvis-input-spark" />
                <textarea ref={textareaRef} value={prompt} onChange={e => setPrompt(e.target.value)} onKeyDown={handleKeyDown} rows={2} maxLength={4000} placeholder="Message JARVIS..." aria-label="Message JARVIS" aria-multiline="true" className="jarvis-prompt-input" style={{ color: 'var(--jarvis-text)' }} />
                {canExpand && !isKeyboardOpen && <button type="button" className="jarvis-expand-button" onClick={() => setExpanded(v => !v)} aria-label={expanded ? 'Collapse message box' : 'Expand message box'}>{expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</button>}
              </div>
              <div className="jarvis-composer-footer" style={{ borderColor: 'var(--jarvis-border)' }}>
                <span className="jarvis-native-badge"><Terminal size={11} /> {expanded ? 'EXPANDED · 5 LINE MAX' : 'NATIVE-FIRST'}</span>
                <div className="jarvis-command-actions">
                  <button type="button" onClick={toggleMic} aria-label={isListening ? 'Stop listening' : 'Voice input'} className={`jarvis-composer-icon ${isListening ? 'is-listening' : ''}`}>{isListening ? <MicOff size={16} /> : <Mic size={16} />}</button>
                  <button type="submit" disabled={!prompt.trim()} aria-label="Send" className="jarvis-send-button" style={{ backgroundColor: prompt.trim() ? 'var(--jarvis-accent)' : 'var(--jarvis-border)', color: prompt.trim() ? 'white' : 'var(--jarvis-text-muted)' }}><ArrowUp size={17} /></button>
                </div>
              </div>
            </form>
            <div className={`jarvis-quick-rail ${isKeyboardOpen ? 'is-hidden' : ''}`} aria-label="JARVIS quick actions">
              {QUICK_PROMPTS.map(item => { const Icon = item.icon; return <button key={item.label} type="button" onClick={() => onStartChatWithPrompt(item.query)} className="jarvis-quick-card"><span className="jarvis-quick-icon"><Icon size={14} /></span><span className="jarvis-quick-copy"><small>{item.meta}</small><strong>{item.label}</strong></span></button>; })}
            </div>
          </section>

          <section className={`jarvis-log-panel ${isKeyboardOpen ? 'is-expanded' : ''}`} aria-label="JARVIS live log">
            <div className="jarvis-log-head"><div><Activity size={13} /><span>JARVIS LIVE LOG</span></div><span className="jarvis-log-live"><i /> LIVE</span></div>
            <div className="jarvis-log-body">{LOG_LINES.map((line, index) => <div key={line} className="jarvis-log-line" style={{ animationDelay: `${index * 180}ms` }}><span>{String(index + 1).padStart(2, '0')}</span><b>›</b>{line}</div>)}</div>
          </section>

          <div className="jarvis-home-actions">
            {isAdmin ? <button onClick={() => onNavigateToView('dashboard')}><Activity size={13} /> Open systems dashboard</button> : <button onClick={onOpenAuth}><Shield size={13} /> Operator sign in</button>}
            <span><Command size={11} /> ENTER TO SEND</span>
          </div>
        </div>
      </main>
    </div>
  );
}
