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
  const textareaTouchingRef = useRef(false);

  // Landing-page keyboard state must react to resize only. Android can emit
  // visualViewport scroll events while the textarea reaches an edge; using
  // those events to change the composer offset makes the whole input box slide.
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;

    const update = () => {
      const keyboardOffset = Math.max(0, window.innerHeight - viewport.height);
      const open = keyboardOffset > 120;
      setIsKeyboardOpen(open);

      // The fixed landing composer is already positioned against the visual
      // viewport on Android. Never apply the visualViewport height delta as a
      // bottom offset; that double-lifts the composer above the keyboard.
      document.documentElement.style.setProperty('--jarvis-keyboard-offset', '0px');
      document.documentElement.style.setProperty('--jarvis-visual-height', `${viewport.height}px`);

      const composerHeight = composerRef.current?.getBoundingClientRect().height ?? 0;
      const available = Math.max(0, viewport.height - 56 - composerHeight - 16);
      const heroScale = open ? Math.max(0.18, Math.min(0.46, (available / 420) * 0.46)) : 1;
      document.documentElement.style.setProperty('--jarvis-keyboard-hero-scale', String(heroScale));
    };

    update();
    viewport.addEventListener('resize', update);
    return () => {
      viewport.removeEventListener('resize', update);
      document.documentElement.style.removeProperty('--jarvis-keyboard-offset');
      document.documentElement.style.removeProperty('--jarvis-visual-height');
      document.documentElement.style.removeProperty('--jarvis-composer-height');
      document.documentElement.style.removeProperty('--jarvis-keyboard-hero-scale');
    };
  }, []);

  // Own the mobile textarea gesture ourselves. This prevents Android from
  // handing an edge-reaching textarea swipe to the page/visual viewport.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;

    let lastY = 0;
    const onStart = (event: TouchEvent) => {
      textareaTouchingRef.current = true;
      lastY = event.touches[0]?.clientY ?? 0;
      event.stopPropagation();
    };
    const onMove = (event: TouchEvent) => {
      const y = event.touches[0]?.clientY;
      if (y == null) return;
      event.preventDefault();
      event.stopPropagation();
      const delta = lastY - y;
      if (delta) {
        const maxScroll = Math.max(0, el.scrollHeight - el.clientHeight);
        el.scrollTop = Math.max(0, Math.min(maxScroll, el.scrollTop + delta));
      }
      lastY = y;
    };
    const onEnd = (event: TouchEvent) => {
      event.stopPropagation();
      textareaTouchingRef.current = false;
    };

    el.addEventListener('touchstart', onStart, { passive: false });
    el.addEventListener('touchmove', onMove, { passive: false });
    el.addEventListener('touchend', onEnd, { passive: false });
    el.addEventListener('touchcancel', onEnd, { passive: false });
    return () => {
      el.removeEventListener('touchstart', onStart);
      el.removeEventListener('touchmove', onMove);
      el.removeEventListener('touchend', onEnd);
      el.removeEventListener('touchcancel', onEnd);
    };
  }, [isExpanded]);

  // Hard-lock the landing document while this screen is mounted so the
  // composer itself is the only element allowed to move during a textarea
  // gesture. The textarea gesture above handles its own scrollTop.
  useEffect(() => {
    const html = document.documentElement;
    const body = document.body;
    const root = document.getElementById('root');
    const previous = {
      htmlOverflow: html.style.overflow,
      bodyOverflow: body.style.overflow,
      bodyOverscroll: body.style.overscrollBehavior,
      rootOverflow: root?.style.overflow || '',
    };
    html.style.overflow = 'hidden';
    body.style.overflow = 'hidden';
    body.style.overscrollBehavior = 'none';
    if (root) root.style.overflow = 'hidden';
    return () => {
      html.style.overflow = previous.htmlOverflow;
      body.style.overflow = previous.bodyOverflow;
      body.style.overscrollBehavior = previous.bodyOverscroll;
      if (root) root.style.overflow = previous.rootOverflow;
    };
  }, []);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el || isExpanded) return;
    const lineHeight = 24;
    const minHeight = lineHeight * 2;
    const maxHeight = lineHeight * 5;
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
        const open = keyboardOffset > 120;
        const available = Math.max(0, viewport.height - 56 - height - 16);
        const heroScale = open ? Math.max(0.18, Math.min(0.46, (available / 420) * 0.46)) : 1;
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
