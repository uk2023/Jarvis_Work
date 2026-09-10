import React, { useEffect, useRef, useState } from 'react';
import { ArrowUp, Maximize2, Minimize2, Mic, Plus } from 'lucide-react';
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
  const keyboardIntentRef = useRef(false);
  const imeWasVisibleRef = useRef(false);

  useEffect(() => {
    const viewport = window.visualViewport;
    const isMobile = window.matchMedia('(max-width: 640px)').matches;
    if (!isMobile) return;

    let settleTimer = 0;
    const update = () => {
      const visualHeight = viewport?.height ?? window.innerHeight;
      const keyboardOffset = Math.max(0, window.innerHeight - visualHeight);
      const focused = document.activeElement === textareaRef.current;
      const imeVisible = keyboardOffset > 80;

      if (imeVisible) {
        imeWasVisibleRef.current = true;
      } else if (imeWasVisibleRef.current) {
        // Android can keep the textarea focused after the Back gesture hides
        // the IME. Once the viewport is restored, release the keyboard latch.
        keyboardIntentRef.current = false;
        imeWasVisibleRef.current = false;
      }

      // During the initial focus transition, keep the hero compact until the
      // viewport reports the IME. After a real IME dismissal, focus alone must
      // never re-expand/re-shrink the landing hero.
      const open = keyboardIntentRef.current || imeVisible || (focused && !imeWasVisibleRef.current);

      setIsKeyboardOpen(open);
      document.documentElement.style.setProperty('--jarvis-keyboard-offset', `${open ? keyboardOffset : 0}px`);
      document.documentElement.style.setProperty('--jarvis-visual-height', `${visualHeight}px`);
      const composerHeight = composerRef.current?.getBoundingClientRect().height ?? 0;
      document.documentElement.style.setProperty('--jarvis-composer-height', `${Math.ceil(composerHeight)}px`);
      document.documentElement.style.setProperty('--jarvis-keyboard-hero-scale', open ? '0.40' : '1');
    };

    const handleFocus = () => {
      keyboardIntentRef.current = true;
      setIsKeyboardOpen(true);
      update();
    };

    const settleAfterKeyboard = () => {
      window.clearTimeout(settleTimer);
      let attempts = 0;
      const settle = () => {
        update();
        attempts += 1;
        if (attempts < 12) settleTimer = window.setTimeout(settle, 80);
      };
      settle();
    };

    update();
    viewport?.addEventListener('resize', update);
    viewport?.addEventListener('scroll', update);
    window.addEventListener('resize', update);
    window.addEventListener('orientationchange', settleAfterKeyboard);
    window.addEventListener('pageshow', update);
    document.addEventListener('visibilitychange', update);
    textareaRef.current?.addEventListener('focus', handleFocus);
    textareaRef.current?.addEventListener('blur', settleAfterKeyboard);

    return () => {
      window.clearTimeout(settleTimer);
      viewport?.removeEventListener('resize', update);
      viewport?.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
      window.removeEventListener('orientationchange', settleAfterKeyboard);
      window.removeEventListener('pageshow', update);
      document.removeEventListener('visibilitychange', update);
      textareaRef.current?.removeEventListener('focus', handleFocus);
      textareaRef.current?.removeEventListener('blur', settleAfterKeyboard);
      document.documentElement.style.removeProperty('--jarvis-keyboard-offset');
      document.documentElement.style.removeProperty('--jarvis-visual-height');
      document.documentElement.style.removeProperty('--jarvis-composer-height');
      document.documentElement.style.removeProperty('--jarvis-keyboard-hero-scale');
    };
  }, []);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;

    if (isExpanded) {
      el.style.removeProperty('height');
      el.style.removeProperty('overflow-y');
      setShowExpand(true);
      return;
    }

    const lineHeight = 24;
    const minHeight = lineHeight * 2;
    const maxHeight = lineHeight * 6;
    el.style.setProperty('height', `${minHeight}px`, 'important');
    el.style.setProperty('overflow-y', 'hidden', 'important');
    const contentHeight = el.scrollHeight;
    const nextHeight = Math.min(Math.max(contentHeight, minHeight), maxHeight);
    el.style.setProperty('height', `${nextHeight}px`, 'important');
    el.style.setProperty('overflow-y', contentHeight > maxHeight ? 'auto' : 'hidden', 'important');
    setShowExpand(contentHeight > lineHeight * 3 + 1);
  }, [prompt, isExpanded]);

  useEffect(() => {
    const el = composerRef.current;
    if (!el) return;
    const update = () => {
      const height = el.getBoundingClientRect().height;
      document.documentElement.style.setProperty('--jarvis-composer-height', `${Math.ceil(height)}px`);
      const viewport = window.visualViewport;
      if (viewport) {
        const keyboardOffset = Math.max(0, window.innerHeight - viewport.height);
        const focused = document.activeElement === textareaRef.current;
        const open = keyboardIntentRef.current || keyboardOffset > 80 || (focused && !imeWasVisibleRef.current);
        const heroScale = open ? 0.40 : 1;
        document.documentElement.style.setProperty('--jarvis-keyboard-hero-scale', String(heroScale));
      }
    };
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
    if (e.key === 'Enter' && !e.shiftKey && !isKeyboardOpen && window.innerWidth > 640) {
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
                  <button type="button" onClick={toggleExpand} aria-label={isExpanded ? 'Close expanded message box' : 'Expand message box'} title={isExpanded ? 'Close expanded composer' : 'Expand composer'} className={`jarvis-composer-icon jarvis-expand-button ${isExpanded ? 'is-active' : ''} ${!showExpand && !isExpanded ? 'is-placeholder' : ''}`} tabIndex={showExpand || isExpanded ? 0 : -1} aria-hidden={!showExpand && !isExpanded}>{isExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}</button>
                  <button type="button" onClick={toggleMic} aria-label={isListening ? 'Stop listening' : 'Voice input'} className={`jarvis-composer-icon jarvis-mic-button ${isListening ? 'is-listening' : ''}`}><Mic size={16} /></button>
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
