import React, { useEffect, useRef, useState } from 'react';
import { ArrowUp, Maximize2, Minimize2, Mic, MicOff, Plus } from 'lucide-react';
import { AppTheme } from '../types';
import '../styles/dashboard-tables.css';
import '../styles/jarvis-home.css';
import '../styles/jarvis-home-mobile.css';

interface HomeScreenProps {
  theme: AppTheme;
  onNavigateToView: (view: 'user_chat' | 'dashboard' | 'cli' | 'inspector') => void;
  onStartChatWithPrompt: (prompt: string) => void;
  isAdmin: boolean;
  onOpenAuth: () => void;
}

export function HomeScreen({ theme, onStartChatWithPrompt }: HomeScreenProps) {
  const isDark = theme === 'dark';
  const [prompt, setPrompt] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isKeyboardOpen, setIsKeyboardOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [showExpand, setShowExpand] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const composerRef = useRef<HTMLFormElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const update = () => {
      const keyboardOffset = Math.max(0, window.innerHeight - viewport.height);
      const open = keyboardOffset > 120;
      setIsKeyboardOpen(open);
      document.documentElement.style.setProperty('--jarvis-keyboard-offset', `${open ? keyboardOffset : 0}px`);
      document.documentElement.style.setProperty('--jarvis-visual-height', `${viewport.height}px`);
    };
    update();
    viewport.addEventListener('resize', update);
    viewport.addEventListener('scroll', update);
    return () => {
      viewport.removeEventListener('resize', update);
      viewport.removeEventListener('scroll', update);
      document.documentElement.style.removeProperty('--jarvis-keyboard-offset');
      document.documentElement.style.removeProperty('--jarvis-visual-height');
      document.documentElement.style.removeProperty('--jarvis-composer-height');
    };
  }, []);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el || isExpanded) return;

    const lineHeight = 24;
    const minHeight = lineHeight * 2;
    const maxHeight = lineHeight * 5;

    // Reset only for measurement, then clamp to exactly 2–5 visible lines.
    el.style.height = `${minHeight}px`;
    el.style.overflowY = 'hidden';
    const contentHeight = el.scrollHeight;
    const nextHeight = Math.min(Math.max(contentHeight, minHeight), maxHeight);
    el.style.height = `${nextHeight}px`;
    el.style.overflowY = contentHeight > maxHeight ? 'auto' : 'hidden';
    setShowExpand(contentHeight > minHeight + 1);
  }, [prompt, isExpanded]);

  useEffect(() => {
    const el = composerRef.current;
    if (!el) return;
    const update = () => document.documentElement.style.setProperty('--jarvis-composer-height', `${Math.ceil(el.getBoundingClientRect().height)}px`);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    window.addEventListener('resize', update);
    return () => { observer.disconnect(); window.removeEventListener('resize', update); };
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    onStartChatWithPrompt(prompt.trim());
    setPrompt('');
    setIsExpanded(false);
    setShowExpand(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const toggleMic = () => {
    if (!isListening) {
      setIsListening(true);
      window.setTimeout(() => {
        setPrompt('JARVIS, check system status');
        setIsListening(false);
        textareaRef.current?.focus();
      }, 1800);
    } else setIsListening(false);
  };

  const handleFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPrompt(current => current ? `${current}\n${file.name}` : file.name);
    e.target.value = '';
    textareaRef.current?.focus();
  };

  const toggleExpand = () => {
    setIsExpanded(value => !value);
    window.requestAnimationFrame(() => textareaRef.current?.focus());
  };

  return (
    <div className={`jarvis-home ${isKeyboardOpen ? 'keyboard-open' : ''} ${isExpanded ? 'composer-expanded' : ''} ${isDark ? 'jarvis-home-dark' : 'jarvis-home-light'}`}>
      <div className="jarvis-space-field" aria-hidden="true">
        <span className="jarvis-star s1" /><span className="jarvis-star s2" /><span className="jarvis-star s3" /><span className="jarvis-star s4" />
        <span className="jarvis-nebula n1" /><span className="jarvis-nebula n2" />
      </div>
      <main className="jarvis-home-main">
        <div className="jarvis-home-content">
          <section className="jarvis-hero">
            <div className="jarvis-black-hole" aria-label="JARVIS cognitive core">
              <div className="jarvis-orbit orbit-a" /><div className="jarvis-orbit orbit-b" /><div className="jarvis-orbit orbit-c" />
              <div className="jarvis-accretion" /><div className="jarvis-core-glow" />
              <div className="jarvis-core-void"><span /><span /><span /></div>
            </div>
            <div className="jarvis-identity">
              <h1>नमस्ते</h1>
              <p>Aaj, Kya HELP Karu?</p>
            </div>
          </section>

          <section className="jarvis-command-zone">
            <form ref={composerRef} onSubmit={handleSubmit} className="jarvis-composer">
              <div className="jarvis-input-wrap">
                <textarea ref={textareaRef} value={prompt} onChange={e => setPrompt(e.target.value)} onKeyDown={handleKeyDown} rows={2} maxLength={4000} placeholder="Message JARVIS..." aria-label="Message JARVIS" aria-multiline="true" className="jarvis-prompt-input" />
              </div>
              <div className="jarvis-composer-footer">
                <div className="jarvis-composer-tools">
                  <button type="button" onClick={() => fileInputRef.current?.click()} aria-label="Upload file" title="Upload file" className="jarvis-composer-icon jarvis-upload-button"><Plus size={17} /></button>
                  <input ref={fileInputRef} type="file" hidden onChange={handleFilePick} />
                </div>
                <div className="jarvis-command-actions">
                  {showExpand && <button type="button" onClick={toggleExpand} aria-label={isExpanded ? 'Close expanded message box' : 'Expand message box'} title={isExpanded ? 'Close expanded composer' : 'Expand composer'} className={`jarvis-composer-icon jarvis-expand-button ${isExpanded ? 'is-active' : ''}`}>{isExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}</button>}
                  <button type="button" onClick={toggleMic} aria-label={isListening ? 'Stop listening' : 'Voice input'} className={`jarvis-composer-icon ${isListening ? 'is-listening' : ''}`}>{isListening ? <MicOff size={16} /> : <Mic size={16} />}</button>
                  <button type="submit" disabled={!prompt.trim()} aria-label="Send" className="jarvis-send-button"><ArrowUp size={17} /></button>
                </div>
              </div>
            </form>
          </section>
        </div>
      </main>
    </div>
  );
}
