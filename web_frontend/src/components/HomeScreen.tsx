import React, { useEffect, useRef, useState } from 'react';
import { Sparkles, ArrowUp, Mic, MicOff, Terminal, Maximize2, Minimize2 } from 'lucide-react';
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
  const [canExpand, setCanExpand] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;

    const update = () => {
      const keyboardOffset = Math.max(0, window.innerHeight - viewport.height);
      const open = keyboardOffset > 120;
      setIsKeyboardOpen(open);
      document.documentElement.style.setProperty('--jarvis-keyboard-offset', `${open ? keyboardOffset : 0}px`);
    };

    update();
    viewport.addEventListener('resize', update);
    viewport.addEventListener('scroll', update);
    return () => {
      viewport.removeEventListener('resize', update);
      viewport.removeEventListener('scroll', update);
      document.documentElement.style.removeProperty('--jarvis-keyboard-offset');
    };
  }, []);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const lineHeight = 24;
    const collapsedMax = lineHeight * 5;
    const expandedMax = lineHeight * 12;
    const naturalHeight = Math.max(el.scrollHeight, lineHeight * 2);
    setCanExpand(el.scrollHeight > lineHeight * 2 + 1);
    el.style.height = `${Math.min(naturalHeight, isExpanded ? expandedMax : collapsedMax)}px`;
    el.style.overflowY = el.scrollHeight > (isExpanded ? expandedMax : collapsedMax) ? 'auto' : 'hidden';
  }, [prompt, isExpanded]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    onStartChatWithPrompt(prompt.trim());
    setPrompt('');
    setIsExpanded(false);
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
    } else {
      setIsListening(false);
    }
  };

  return (
    <div className={`jarvis-home ${isKeyboardOpen ? 'keyboard-open' : ''} ${isDark ? 'jarvis-home-dark' : 'jarvis-home-light'}`}>
      <div className="jarvis-space-field" aria-hidden="true">
        <span className="jarvis-star s1" />
        <span className="jarvis-star s2" />
        <span className="jarvis-star s3" />
        <span className="jarvis-star s4" />
        <span className="jarvis-nebula n1" />
        <span className="jarvis-nebula n2" />
      </div>

      <main className="jarvis-home-main">
        <div className="jarvis-home-content">
          <section className="jarvis-hero">
            <div className="jarvis-black-hole" aria-label="JARVIS cognitive core">
              <div className="jarvis-orbit orbit-a" />
              <div className="jarvis-orbit orbit-b" />
              <div className="jarvis-orbit orbit-c" />
              <div className="jarvis-accretion" />
              <div className="jarvis-core-glow" />
              <div className="jarvis-core-void"><span /><span /><span /></div>
            </div>

            <div className="jarvis-identity">
              <h1>JARVIS</h1>
              <p>Namaste! Aaj kya help karu?</p>
            </div>
          </section>

          <section className={`jarvis-command-zone ${isExpanded ? 'is-expanded' : ''}`}>
            <form onSubmit={handleSubmit} className="jarvis-composer">
              <div className="jarvis-input-wrap">
                <Sparkles size={14} className="jarvis-input-spark" />
                <textarea
                  ref={textareaRef}
                  value={prompt}
                  onChange={e => setPrompt(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={2}
                  maxLength={4000}
                  placeholder="Message JARVIS..."
                  aria-label="Message JARVIS"
                  aria-multiline="true"
                  className="jarvis-prompt-input"
                />
              </div>
              <div className="jarvis-composer-footer">
                <span className="jarvis-native-badge"><Terminal size={11} /> {isExpanded ? 'EXPANDED' : canExpand ? 'MULTI-LINE' : 'READY'}</span>
                <div className="jarvis-command-actions">
                  {canExpand && (
                    <button
                      type="button"
                      onClick={() => setIsExpanded(value => !value)}
                      aria-label={isExpanded ? 'Collapse composer' : 'Expand composer'}
                      title={isExpanded ? 'Collapse' : 'Expand'}
                      className="jarvis-composer-icon jarvis-expand-button"
                    >
                      {isExpanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
                    </button>
                  )}
                  <button type="button" onClick={toggleMic} aria-label={isListening ? 'Stop listening' : 'Voice input'} className={`jarvis-composer-icon ${isListening ? 'is-listening' : ''}`}>
                    {isListening ? <MicOff size={16} /> : <Mic size={16} />}
                  </button>
                  <button type="submit" disabled={!prompt.trim()} aria-label="Send" className="jarvis-send-button">
                    <ArrowUp size={17} />
                  </button>
                </div>
              </div>
            </form>
          </section>

          <section className="jarvis-intelligence-panel" aria-label="JARVIS ambient intelligence visualization">
            <div className="jarvis-intelligence-grid" />
            <div className="jarvis-intelligence-wave wave-a" />
            <div className="jarvis-intelligence-wave wave-b" />
            <div className="jarvis-intelligence-wave wave-c" />
            <div className="jarvis-intelligence-orb orb-a" />
            <div className="jarvis-intelligence-orb orb-b" />
            <div className="jarvis-intelligence-orb orb-c" />
            <div className="jarvis-intelligence-sweep" />
          </section>
        </div>
      </main>
    </div>
  );
}
