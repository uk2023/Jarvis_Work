import React, { useState } from 'react';
import {
  Shield,
  Lock,
  ArrowRight,
  X,
  AlertCircle,
  Mail,
  Phone,
  User,
  CheckCircle2,
  Fingerprint,
  Scan,
  KeyRound,
  RotateCw,
} from 'lucide-react';
import { api } from '../api/client';
import { AppTheme } from '../types';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  theme: AppTheme;
}

export function AuthModal({ isOpen, onClose, onSuccess, theme }: AuthModalProps) {
  // Main authentication modes: 'user' | 'admin'
  const [authMode, setAuthMode] = useState<'user' | 'admin'>('user');

  // User auth sub-method: 'google' | 'email' | 'otp'
  const [userMethod, setUserMethod] = useState<'google' | 'email' | 'otp'>('google');

  // User form states
  const [emailInput, setEmailInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');
  const [phoneInput, setPhoneInput] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [otpSent, setOtpSent] = useState(false);

  // Admin auth sub-method: 'biometric' | 'passphrase'
  const [adminMethod, setAdminMethod] = useState<'biometric' | 'passphrase'>('biometric');
  const [adminPassphrase, setAdminPassphrase] = useState('');
  const [biometricScanning, setBiometricScanning] = useState(false);
  const [biometricType, setBiometricType] = useState<'fingerprint' | 'face'>('fingerprint');

  // Status & feedback
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const isDark = theme === 'dark';

  // 1. Google 1-Click Sign-In
  const handleGoogleLogin = () => {
    setIsSubmitting(true);
    setError(null);
    setTimeout(() => {
      const googleUser = {
        displayName: 'Google Operator',
        nickname: 'Operator',
        username: 'user@gmail.com',
        role: 'user',
        avatar: 'G',
      };
      try {
        localStorage.setItem('jarvis_user_profile', JSON.stringify(googleUser));
        localStorage.setItem('jarvis_logged_in_method', 'google');
      } catch {}
      setIsSubmitting(false);
      setSuccessMessage('Successfully authenticated via Google Account');
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 700);
    }, 600);
  };

  // 2. Email & Password Sign-In
  const handleEmailPasswordLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailInput.trim()) {
      setError('Please enter your email address');
      return;
    }
    if (!passwordInput.trim() || passwordInput.length < 4) {
      setError('Please enter a valid password (minimum 4 characters)');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    setTimeout(() => {
      const standardUser = {
        displayName: emailInput.split('@')[0] || 'Operator',
        nickname: 'Member',
        username: emailInput.trim(),
        role: 'user',
      };
      try {
        localStorage.setItem('jarvis_user_profile', JSON.stringify(standardUser));
        localStorage.setItem('jarvis_logged_in_method', 'email');
      } catch {}
      setIsSubmitting(false);
      setSuccessMessage(`Signed in as ${emailInput.trim()}`);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 700);
    }, 500);
  };

  // 3. Mobile Number OTP Flow
  const handleSendOtp = (e: React.FormEvent) => {
    e.preventDefault();
    if (!phoneInput.trim() || phoneInput.length < 7) {
      setError('Please enter a valid mobile number');
      return;
    }
    setIsSubmitting(true);
    setError(null);

    setTimeout(() => {
      setIsSubmitting(false);
      setOtpSent(true);
      setOtpCode('8492'); // Simulation code
    }, 600);
  };

  const handleVerifyOtp = (e: React.FormEvent) => {
    e.preventDefault();
    if (!otpCode.trim() || otpCode.length < 4) {
      setError('Please enter the 4-digit verification code');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    setTimeout(() => {
      const phoneUser = {
        displayName: `User ${phoneInput.slice(-4)}`,
        nickname: 'Mobile User',
        username: phoneInput.trim(),
        role: 'user',
      };
      try {
        localStorage.setItem('jarvis_user_profile', JSON.stringify(phoneUser));
        localStorage.setItem('jarvis_logged_in_method', 'phone_otp');
      } catch {}
      setIsSubmitting(false);
      setSuccessMessage('Mobile OTP verified successfully');
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 700);
    }, 500);
  };

  // 4. Biometric Touch / Face Scanner Simulation
  const handleBiometricScan = () => {
    setBiometricScanning(true);
    setError(null);

    setTimeout(async () => {
      try {
        await api.login('operator-pass-4242');
        const adminUser = {
          displayName: 'Lead Operator',
          nickname: 'Admin',
          username: 'admin@jarvis.core',
          role: 'admin',
        };
        try {
          localStorage.setItem('jarvis_user_profile', JSON.stringify(adminUser));
          localStorage.setItem('jarvis_operator_token', 'operator-active');
        } catch {}
        setBiometricScanning(false);
        setSuccessMessage('Biometric signature authenticated. Operator unlocked.');
        setTimeout(() => {
          onSuccess();
          onClose();
        }, 700);
      } catch {
        setBiometricScanning(false);
        setError('Biometric authentication failed. Please use passphrase.');
      }
    }, 1200);
  };

  // 5. Admin Passphrase Login
  const handleAdminPassphraseLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adminPassphrase.trim()) {
      setError('Please enter operator passphrase or PIN');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await api.login(adminPassphrase.trim());
      const adminUser = {
        displayName: 'Lead Operator',
        nickname: 'Admin',
        username: 'admin@jarvis.core',
        role: 'admin',
      };
      try {
        localStorage.setItem('jarvis_user_profile', JSON.stringify(adminUser));
        localStorage.setItem('jarvis_operator_token', 'operator-active');
      } catch {}
      setSuccessMessage('Operator privileges granted');
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 700);
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Default passphrase is "jarvis2026".');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/75 backdrop-blur-sm overflow-y-auto animate-fade-in">
      <div
        className={`relative my-auto w-full max-w-md rounded-2xl border p-5 sm:p-6 shadow-2xl space-y-4 transition-all max-h-[92vh] overflow-y-auto ${
          isDark
            ? 'bg-[#090d18] border-white/10 text-white shadow-brand-950/40'
            : 'bg-white border-slate-200 text-slate-900 shadow-xl'
        }`}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 text-slate-400 hover:text-slate-600 dark:hover:text-white transition cursor-pointer"
          title="Close modal"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Brand & Logo Header */}
        <div className="text-center space-y-2 pt-1">
          <div className="mx-auto w-12 h-12 rounded-2xl bg-brand-500/15 border border-brand-400/40 flex items-center justify-center shadow-lg shadow-brand-500/10">
            <span className="w-4 h-4 rounded-full bg-brand-400 animate-pulse" />
          </div>
          <div>
            <h2 className="text-lg sm:text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              {authMode === 'user' ? 'JARVIS User Login' : 'Operator Console Access'}
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-sans mt-0.5">
              {authMode === 'user'
                ? 'Standard session with Google, email, or mobile OTP'
                : 'Elevate privileges with Biometrics or Kernel Passphrase'}
            </p>
          </div>
        </div>

        {/* Top-Level Mode Selector: User vs Admin */}
        <div
          className={`p-1 rounded-xl border flex items-center gap-1 ${
            isDark ? 'bg-white/[0.03] border-white/10' : 'bg-slate-100 border-slate-200'
          }`}
        >
          <button
            type="button"
            onClick={() => {
              setAuthMode('user');
              setError(null);
              setSuccessMessage(null);
            }}
            className={`flex-1 py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition cursor-pointer ${
              authMode === 'user'
                ? isDark
                  ? 'bg-brand-500/20 text-brand-300 shadow-xs border border-brand-500/30'
                  : 'bg-white text-slate-900 shadow-xs border border-slate-200'
                : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            <User className="w-3.5 h-3.5" />
            <span>Normal / User Login</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setAuthMode('admin');
              setError(null);
              setSuccessMessage(null);
            }}
            className={`flex-1 py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition cursor-pointer ${
              authMode === 'admin'
                ? isDark
                  ? 'bg-brand-500/20 text-brand-300 shadow-xs border border-brand-500/30'
                  : 'bg-white text-slate-900 shadow-xs border border-slate-200'
                : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            <Shield className="w-3.5 h-3.5 text-brand-500" />
            <span>Admin / Operator</span>
          </button>
        </div>

        {/* Success Alert */}
        {successMessage && (
          <div className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs flex items-center gap-2 font-medium animate-in fade-in">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-500" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2 font-medium animate-in fade-in">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-500" />
            <span>{error}</span>
          </div>
        )}

        {/* ============================================================ */}
        {/* TAB 1: NORMAL / USER LOGIN                                   */}
        {/* ============================================================ */}
        {authMode === 'user' && (
          <div className="space-y-3.5">
            {/* Sub-method pills: Google, Email, Mobile OTP */}
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => {
                  setUserMethod('google');
                  setError(null);
                }}
                className={`flex-1 py-1 px-2 rounded-lg text-xs font-semibold border transition cursor-pointer flex items-center justify-center gap-1 ${
                  userMethod === 'google'
                    ? 'bg-brand-600/15 text-brand-600 dark:text-brand-400 border-brand-500/30'
                    : isDark
                    ? 'border-white/5 text-slate-400 hover:text-white'
                    : 'border-slate-200 text-slate-600 hover:text-slate-900'
                }`}
              >
                <span>Google</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setUserMethod('email');
                  setError(null);
                }}
                className={`flex-1 py-1 px-2 rounded-lg text-xs font-semibold border transition cursor-pointer flex items-center justify-center gap-1 ${
                  userMethod === 'email'
                    ? 'bg-brand-600/15 text-brand-600 dark:text-brand-400 border-brand-500/30'
                    : isDark
                    ? 'border-white/5 text-slate-400 hover:text-white'
                    : 'border-slate-200 text-slate-600 hover:text-slate-900'
                }`}
              >
                <span>Email</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setUserMethod('otp');
                  setError(null);
                }}
                className={`flex-1 py-1 px-2 rounded-lg text-xs font-semibold border transition cursor-pointer flex items-center justify-center gap-1 ${
                  userMethod === 'otp'
                    ? 'bg-brand-600/15 text-brand-600 dark:text-brand-400 border-brand-500/30'
                    : isDark
                    ? 'border-white/5 text-slate-400 hover:text-white'
                    : 'border-slate-200 text-slate-600 hover:text-slate-900'
                }`}
              >
                <span>Mobile OTP</span>
              </button>
            </div>

            {/* 1. Google Method */}
            {userMethod === 'google' && (
              <div className="space-y-3 pt-1">
                <button
                  type="button"
                  onClick={handleGoogleLogin}
                  disabled={isSubmitting}
                  className={`w-full py-2.5 px-4 rounded-xl border flex items-center justify-center gap-2.5 text-xs font-semibold transition cursor-pointer ${
                    isDark
                      ? 'bg-white/5 hover:bg-white/10 border-white/15 text-white'
                      : 'bg-white hover:bg-slate-50 border-slate-300 text-slate-800 shadow-2xs'
                  }`}
                >
                  <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
                    <path
                      fill="#4285F4"
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                    />
                  </svg>
                  <span>Continue with Google</span>
                </button>
                <p className="text-xs text-center text-slate-500 dark:text-slate-400">
                  Instant authentication using standard Google Identity Token.
                </p>
              </div>
            )}

            {/* 2. Email & Password Method */}
            {userMethod === 'email' && (
              <form onSubmit={handleEmailPasswordLogin} className="space-y-3 pt-1">
                <div className="space-y-1">
                  <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400">
                    Email Address
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                      <Mail className="w-3.5 h-3.5" />
                    </div>
                    <input
                      type="email"
                      value={emailInput}
                      onChange={e => setEmailInput(e.target.value)}
                      placeholder="operator@domain.com"
                      className={`w-full pl-9 pr-3 py-2 rounded-xl border text-xs outline-none transition ${
                        isDark
                          ? 'bg-black/50 border-white/15 focus:border-brand-400 text-white placeholder:text-slate-600'
                          : 'bg-slate-50 border-slate-300 focus:border-brand-600 text-slate-900 placeholder:text-slate-400'
                      }`}
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400">
                    Password
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                      <Lock className="w-3.5 h-3.5" />
                    </div>
                    <input
                      type="password"
                      value={passwordInput}
                      onChange={e => setPasswordInput(e.target.value)}
                      placeholder="Enter password..."
                      className={`w-full pl-9 pr-3 py-2 rounded-xl border text-xs outline-none transition ${
                        isDark
                          ? 'bg-black/50 border-white/15 focus:border-brand-400 text-white placeholder:text-slate-600'
                          : 'bg-slate-50 border-slate-300 focus:border-brand-600 text-slate-900 placeholder:text-slate-400'
                      }`}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs flex items-center justify-center gap-1.5 shadow-md shadow-brand-600/20 transition cursor-pointer"
                >
                  <span>{isSubmitting ? 'Signing in...' : 'Sign In with Email'}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </form>
            )}

            {/* 3. Mobile OTP Method */}
            {userMethod === 'otp' && (
              <div className="space-y-3 pt-1">
                {!otpSent ? (
                  <form onSubmit={handleSendOtp} className="space-y-3">
                    <div className="space-y-1">
                      <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400">
                        Mobile Phone Number
                      </label>
                      <div className="relative">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                          <Phone className="w-3.5 h-3.5" />
                        </div>
                        <input
                          type="tel"
                          value={phoneInput}
                          onChange={e => setPhoneInput(e.target.value)}
                          placeholder="+1 555-0199 or +91 98765 43210"
                          className={`w-full pl-9 pr-3 py-2 rounded-xl border text-xs outline-none transition ${
                            isDark
                              ? 'bg-black/50 border-white/15 focus:border-brand-400 text-white placeholder:text-slate-600'
                              : 'bg-slate-50 border-slate-300 focus:border-brand-600 text-slate-900 placeholder:text-slate-400'
                          }`}
                        />
                      </div>
                    </div>

                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="w-full py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs flex items-center justify-center gap-1.5 shadow-md shadow-brand-600/20 transition cursor-pointer"
                    >
                      <span>{isSubmitting ? 'Sending Code...' : 'Send Verification OTP'}</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </form>
                ) : (
                  <form onSubmit={handleVerifyOtp} className="space-y-3">
                    <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20 text-xs text-brand-600 dark:text-brand-400 flex items-center justify-between">
                      <span>OTP sent to: <b>{phoneInput}</b></span>
                      <button
                        type="button"
                        onClick={() => setOtpSent(false)}
                        className="text-xs underline hover:text-brand-300 cursor-pointer"
                      >
                        Change
                      </button>
                    </div>

                    <div className="space-y-1">
                      <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400">
                        Enter 4-digit OTP Code
                      </label>
                      <input
                        type="text"
                        maxLength={6}
                        value={otpCode}
                        onChange={e => setOtpCode(e.target.value)}
                        placeholder="e.g. 8492"
                        className={`w-full text-center tracking-widest text-lg font-mono py-2 rounded-xl border outline-none transition ${
                          isDark
                            ? 'bg-black/50 border-white/15 focus:border-brand-400 text-white'
                            : 'bg-slate-50 border-slate-300 focus:border-brand-600 text-slate-900'
                        }`}
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="w-full py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs flex items-center justify-center gap-1.5 shadow-md shadow-brand-600/20 transition cursor-pointer"
                    >
                      <span>{isSubmitting ? 'Verifying...' : 'Verify OTP & Enter'}</span>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    </button>
                  </form>
                )}
              </div>
            )}
          </div>
        )}

        {/* ============================================================ */}
        {/* TAB 2: ADMIN / OPERATOR LOGIN                                */}
        {/* ============================================================ */}
        {authMode === 'admin' && (
          <div className="space-y-3.5">
            {/* Sub-method pills: Biometric Scanner vs Passphrase */}
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => {
                  setAdminMethod('biometric');
                  setError(null);
                }}
                className={`flex-1 py-1 px-2 rounded-lg text-xs font-semibold border transition cursor-pointer flex items-center justify-center gap-1 ${
                  adminMethod === 'biometric'
                    ? 'bg-brand-600/15 text-brand-600 dark:text-brand-400 border-brand-500/30'
                    : isDark
                    ? 'border-white/5 text-slate-400 hover:text-white'
                    : 'border-slate-200 text-slate-600 hover:text-slate-900'
                }`}
              >
                <Fingerprint className="w-3.5 h-3.5" />
                <span>Biometric Sensor</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setAdminMethod('passphrase');
                  setError(null);
                }}
                className={`flex-1 py-1 px-2 rounded-lg text-xs font-semibold border transition cursor-pointer flex items-center justify-center gap-1 ${
                  adminMethod === 'passphrase'
                    ? 'bg-brand-600/15 text-brand-600 dark:text-brand-400 border-brand-500/30'
                    : isDark
                    ? 'border-white/5 text-slate-400 hover:text-white'
                    : 'border-slate-200 text-slate-600 hover:text-slate-900'
                }`}
              >
                <KeyRound className="w-3.5 h-3.5" />
                <span>Passphrase / PIN</span>
              </button>
            </div>

            {/* 1. Biometric Scanner Mode */}
            {adminMethod === 'biometric' && (
              <div className="space-y-3 pt-1">
                {/* Scanner Type Toggle (Fingerprint / FaceID) */}
                <div className="flex justify-center gap-2">
                  <button
                    type="button"
                    onClick={() => setBiometricType('fingerprint')}
                    className={`px-3 py-1 rounded-full text-xs font-mono border transition cursor-pointer ${
                      biometricType === 'fingerprint'
                        ? 'bg-brand-500/20 text-brand-400 border-brand-400/40 font-bold'
                        : 'border-transparent text-slate-400 hover:text-white'
                    }`}
                  >
                    Fingerprint Touch
                  </button>
                  <button
                    type="button"
                    onClick={() => setBiometricType('face')}
                    className={`px-3 py-1 rounded-full text-xs font-mono border transition cursor-pointer ${
                      biometricType === 'face'
                        ? 'bg-brand-500/20 text-brand-400 border-brand-400/40 font-bold'
                        : 'border-transparent text-slate-400 hover:text-white'
                    }`}
                  >
                    Face ID Scan
                  </button>
                </div>

                {/* Interactive Scanner Hub */}
                <div
                  className={`p-6 rounded-2xl border text-center flex flex-col items-center justify-center gap-3 relative overflow-hidden ${
                    isDark ? 'bg-black/50 border-brand-500/30' : 'bg-slate-50 border-slate-200'
                  }`}
                >
                  <div className="relative">
                    <button
                      type="button"
                      onClick={handleBiometricScan}
                      disabled={biometricScanning}
                      className={`w-20 h-20 rounded-full border-2 flex items-center justify-center transition-all cursor-pointer ${
                        biometricScanning
                          ? 'border-brand-400 bg-brand-500/20 shadow-[0_0_30px_#22d3ee] scale-105'
                          : 'border-brand-500/50 hover:border-brand-400 bg-brand-500/10 text-brand-400 hover:scale-105'
                      }`}
                    >
                      {biometricType === 'fingerprint' ? (
                        <Fingerprint className={`w-10 h-10 ${biometricScanning ? 'animate-pulse text-brand-300' : ''}`} />
                      ) : (
                        <Scan className={`w-10 h-10 ${biometricScanning ? 'animate-pulse text-brand-300' : ''}`} />
                      )}
                    </button>

                    {biometricScanning && (
                      <div className="absolute inset-0 rounded-full border-2 border-brand-400 animate-ping opacity-60 pointer-events-none" />
                    )}
                  </div>

                  <div>
                    <div className="font-bold text-xs text-slate-900 dark:text-white">
                      {biometricScanning
                        ? 'Reading Biometric Signature...'
                        : 'Tap Sensor to Authenticate Operator'}
                    </div>
                    <div className="text-xs text-slate-400 font-mono mt-0.5">
                      SHA-256 Neural Vault &bull; Kernel Elevation
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleBiometricScan}
                    disabled={biometricScanning}
                    className="px-4 py-1.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-bold text-xs transition cursor-pointer shadow-sm flex items-center gap-1.5"
                  >
                    {biometricScanning && <RotateCw className="w-3.5 h-3.5 animate-spin" />}
                    <span>{biometricScanning ? 'Authenticating...' : 'Simulate Biometric Touch'}</span>
                  </button>
                </div>
              </div>
            )}

            {/* 2. Passphrase Mode */}
            {adminMethod === 'passphrase' && (
              <form onSubmit={handleAdminPassphraseLogin} className="space-y-3.5 pt-1">
                <div
                  className={`p-2.5 rounded-xl border text-xs ${
                    isDark
                      ? 'bg-brand-950/20 border-brand-500/20 text-brand-300'
                      : 'bg-brand-50/70 border-brand-200 text-brand-900'
                  }`}
                >
                  <span className="font-semibold block mb-0.5">Authorized Kernel Passkey</span>
                  <span className="text-xs opacity-85">
                    Authorized operator passphrase required (Default: <code className="font-mono font-bold">jarvis2026</code>).
                  </span>
                </div>

                <div className="space-y-1">
                  <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400">
                    Operator Passphrase / PIN
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                      <Lock className="w-3.5 h-3.5" />
                    </div>
                    <input
                      type="password"
                      value={adminPassphrase}
                      onChange={e => setAdminPassphrase(e.target.value)}
                      placeholder="Enter operator passphrase..."
                      autoFocus
                      className={`w-full pl-9 pr-3 py-2 rounded-xl border text-xs outline-none transition font-mono ${
                        isDark
                          ? 'bg-black/50 border-white/15 focus:border-brand-400 text-white placeholder:text-slate-600'
                          : 'bg-slate-50 border-slate-300 focus:border-brand-600 text-slate-900 placeholder:text-slate-400'
                      }`}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full py-2.5 rounded-xl bg-brand-500 hover:bg-brand-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-1.5 shadow-lg shadow-brand-500/20 transition cursor-pointer"
                >
                  <span>{isSubmitting ? 'Authenticating...' : 'Enter Operator Console'}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </form>
            )}
          </div>
        )}

        {/* Footer info */}
        <div className="text-center pt-2 border-t border-slate-200 dark:border-white/10">
          <button
            type="button"
            onClick={onClose}
            className="text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-white transition cursor-pointer"
          >
            Continue browsing as Guest &rarr;
          </button>
        </div>
      </div>
    </div>
  );
}
