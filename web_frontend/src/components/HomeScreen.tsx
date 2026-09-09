import React, { useEffect, useRef, useState } from 'react';
import {
  Activity,
  Shield,
  Sparkles,
  ArrowUp,
  Mic,
  MicOff,
  Cpu,
  Brain,
  Zap,
  Orbit,
  Command,
} from 'lucide-react';
import { AppTheme } from '../types';
import '../styles/dashboard-tables.css';

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

export function HomeScreen({
  theme,
  onNavigateToView,
  onStartChatWithPrompt,
  isAdmin,
  onOpenAuth,
}: HomeScreenProps) {
  const isDark = theme === 'dark';
  const [prompt, setPrompt] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isKeyboardOpen, setIsKeyboardOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resizePrompt = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const lineHeight = 24;
    const maxHeight = lineHeight * 5;
    el.style.height = `${Math.min(Math.max(el.scrollHeight, lineHeight * 2), maxHeight)}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? 'auto' : 'hidden';
  };

  useEffect(() => {
    resizePrompt();
  }, [prompt]);

  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const update = () => setIsKeyboardOpen(window.innerHeight - viewport.height > 120);
    update();
    viewport.addEventListener('resize', update);
    viewport.addEventListener('scroll', update);
    return () => {
      viewport.removeEventListener('resize', update);
      viewport.removeEventListener('scroll', update);
    };
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    onStartChatWithPrompt(prompt.trim());
    setPrompt('');
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
      setTimeout(() => {
        setPrompt('JARVIS, check system status');
        setIsListening(false);
      }, 1800);
    } else {
      setIsListening(false);
    }
  };

  return (
    <div className={`jarvis-home ${isKeyboardOpen ? 'keyboard-open' : ''} ${isDark ? 'jarvis-home-dark' : 'jarvis-home-light'}`}>
      <div className="jarvis-space-field" aria-hidden="true">
        <span className="jarvis-star s1" /><span className="jarvis-star s2" /><span className="jarvis-star s3" />
        <span className="jarvis-nebula n1" /><span className="jarvis-nebula n2" />
      </div>

      <main className="jarvis-home-main">
        <div className="jarvis-home-content">
          <div className="jarvis-black-hole" aria-label="JARVIS core">
            <div className="jarvis-orbit orbit-a" />
            <div className="jarvis-orbit orbit-b" />
            <div className="jarvis-orbit orbit-c" />
            <div className="jarvis-core-glow" />
            <div className="jarvis-core-void"><span /><span /><span /></div>
          </div>

          <div className="jarvis-identity">
            <div className="jarvis-eyebrow"><Orbit size={12} /> JARVIS COGNITIVE OS <span>•</span> ONLINE</div>
            <h1>Hi, I'm JARVIS</h1>
            <p>Intelligent, local-first cognition — ready when you are.</p>
          </div>

          <form
            onSubmit={handleSubmit}
            className="jarvis-composer"
            style={{ backgroundColor: 'var(--jarvis-surface)', borderColor: 'var(--jarvis-border)' }}
          >
            <textarea
              ref={textareaRef}
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              onFocus={() => setIsKeyboardOpen(window.innerHeight - (window.visualViewport?.height || window.innerHeight) > 120)}
              onKeyDown={handleKeyDown}
              rows={2}
              maxLength={4000}
              placeholder="Message JARVIS..."
              aria-label="Message JARVIS"
              className="jarvis-prompt-input"
              style={{ color: 'var(--jarvis-text)' }}
            />
            <div className="jarvis-composer-footer" style={{ borderColor: 'var(--jarvis-border)' }}>
              <span className="jarvis-native-badge"><Sparkles size={12} /> Native-first</span>
              <div className="flex items-center gap-1.5">
                <button type="button" onClick={toggleMic} aria-label={isListening ? 'Stop listening' : 'Voice input'} className="jarvis-composer-icon" style={isListening ? { backgroundColor: 'var(--jarvis-danger)', color: 'white' } : { color: 'var(--jarvis-text-muted)' }}>
                  {isListening ? <MicOff size={16} /> : <Mic size={16} />}
                </button>
                <button type="submit" disabled={!prompt.trim()} aria-label="Send" className="jarvis-send-button" style={{ backgroundColor: prompt.trim() ? 'var(--jarvis-accent)' : 'var(--jarvis-border)', color: prompt.trim() ? 'white' : 'var(--jarvis-text-muted)' }}>
                  <ArrowUp size={17} />
                </button>
              </div>
            </div>
          </form>

          <div className="jarvis-quick-rail" aria-label="JARVIS quick actions">
            {QUICK_PROMPTS.map(item => {
              const Icon = item.icon;
              return (
                <button key={item.label} type="button" onClick={() => onStartChatWithPrompt(item.query)} className="jarvis-quick-card">
                  <span className="jarvis-quick-icon"><Icon size={14} /></span>
                  <span className="jarvis-quick-copy"><small>{item.meta}</small><strong>{item.label}</strong></span>
                </button>
              );
            })}
          </div>

          <div className="jarvis-home-actions">
            {isAdmin ? (
              <button onClick={() => onNavigateToView('dashboard')}><Activity size={13} /> Open systems dashboard</button>
            ) : (
              <button onClick={onOpenAuth}><Shield size={13} /> Operator sign in</button>
            )}
            <span><Command size={11} /> ENTER TO SEND</span>
          </div>
        </div>
      </main>
    </div>
  );
}
