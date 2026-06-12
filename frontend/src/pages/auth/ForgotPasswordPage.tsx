import React, { useState, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, AlertTriangle, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { forgotPassword, resetPassword } from '../../services/authService';

// Schema for Phase 1: Request OTP
const requestOtpSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Please enter a valid email address'),
});

// Schema for Phase 2: Reset Password
const resetPasswordSchema = z.object({
  new_password: z.string().min(8, 'Password must be at least 8 characters'),
  confirm_password: z.string().min(1, 'Confirm password is required'),
}).refine((data) => data.new_password === data.confirm_password, {
  message: "Passwords do not match",
  path: ['confirm_password'],
});

type RequestOtpFormValues = z.infer<typeof requestOtpSchema>;
type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;

const ForgotPasswordPage: React.FC = () => {
  const [isOtpSent, setIsOtpSent] = useState(false);
  const [isResetSuccess, setIsResetSuccess] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  
  const [apiError, setApiError] = useState<string | null>(null);
  const [apiSuccess, setApiSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // OTP inputs
  const [otp, setOtp] = useState<string[]>(Array(6).fill(''));
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Form 1: Email Request
  const {
    register: registerEmail,
    handleSubmit: handleSubmitEmail,
    formState: { errors: emailErrors },
  } = useForm<RequestOtpFormValues>({
    resolver: zodResolver(requestOtpSchema),
    defaultValues: { email: '' },
  });

  // Form 2: Password Reset
  const {
    register: registerReset,
    handleSubmit: handleSubmitReset,
    formState: { errors: resetErrors },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: '', confirm_password: '' },
  });

  const onRequestOtpSubmit = async (data: RequestOtpFormValues) => {
    setApiError(null);
    setIsLoading(true);
    try {
      await forgotPassword({ email: data.email });
      setUserEmail(data.email);
      setApiSuccess('If an account with this email exists, a code has been sent.');
      setIsOtpSent(true);
    } catch (err: any) {
      if (err.response && err.response.data && err.response.data.detail) {
        setApiError(err.response.data.detail);
      } else {
        setApiError('Failed to send verification code. Please check your email address and try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const onResetPasswordSubmit = async (data: ResetPasswordFormValues) => {
    const otpCode = otp.join('');
    if (otpCode.length < 6) {
      setApiError('Please enter the 6-digit verification code.');
      return;
    }

    setApiError(null);
    setIsLoading(true);
    try {
      await resetPassword({
        email: userEmail,
        otp: otpCode,
        new_password: data.new_password,
        confirm_password: data.confirm_password,
      });
      setIsResetSuccess(true);
      setApiSuccess('Password reset successfully.');
    } catch (err: any) {
      if (err.response && err.response.data && err.response.data.detail) {
        setApiError(err.response.data.detail);
      } else {
        setApiError('Invalid verification code or failed to reset password. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // OTP input handlers
  const handleOtpChange = (value: string, index: number) => {
    const cleanValue = value.replace(/[^a-zA-Z0-9]/g, '');
    const newOtp = [...otp];
    const char = cleanValue.slice(-1);
    newOtp[index] = char;
    setOtp(newOtp);

    if (char && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleOtpKeyDown = (e: React.KeyboardEvent<HTMLInputElement>, index: number) => {
    if (e.key === 'Backspace') {
      if (!otp[index] && index > 0) {
        const newOtp = [...otp];
        newOtp[index - 1] = '';
        setOtp(newOtp);
        inputRefs.current[index - 1]?.focus();
      }
    }
  };

  const handleOtpPaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').trim().slice(0, 6);
    if (pastedData.length > 0) {
      const newOtp = [...otp];
      for (let i = 0; i < Math.min(pastedData.length, 6); i++) {
        newOtp[i] = pastedData[i];
      }
      setOtp(newOtp);
      const nextFocusIndex = Math.min(pastedData.length, 5);
      inputRefs.current[nextFocusIndex]?.focus();
    }
  };

  // State 1: Reset Success State
  if (isResetSuccess) {
    return (
      <div className="w-full max-w-md animate-fade-in text-center">
        <div className="flex justify-center mb-6">
          <CheckCircle2 className="h-16 w-16 text-emerald-500" />
        </div>
        <h2 className="font-sora text-3xl font-bold tracking-tight text-slate-800 mb-4">
          Password Reset Complete
        </h2>
        <p className="text-sm text-slate-500 mb-8">
          {apiSuccess}
        </p>
        <Link
          to="/login"
          className="bg-indigo-700 hover:bg-indigo-600 text-white font-semibold rounded-lg px-6 py-3 w-full block transition-colors duration-200"
        >
          Back to login
        </Link>
      </div>
    );
  }

  // State 2: OTP + New Password Form (after request success)
  if (isOtpSent) {
    return (
      <div className="w-full max-w-md animate-fade-in">
        {/* Back to Request Email */}
        <button
          onClick={() => {
            setIsOtpSent(false);
            setApiError(null);
            setApiSuccess(null);
          }}
          className="inline-flex items-center text-sm font-semibold text-indigo-600 hover:text-indigo-500 mb-8"
        >
          <ArrowLeft className="mr-1.5 h-4 w-4" /> Use different email
        </button>

        <div className="mb-6">
          <h2 className="font-sora text-3xl font-bold tracking-tight text-slate-800">
            Reset your password
          </h2>
          <p className="mt-2 text-sm text-slate-500">
            Enter the 6-digit code sent to <span className="font-semibold text-slate-800">{userEmail}</span> and your new password.
          </p>
        </div>

        {/* Success Alert Banner */}
        {apiSuccess && (
          <div className="mb-6 bg-emerald-50 border border-emerald-200 rounded-lg p-4 flex items-start gap-3 text-emerald-800 text-sm">
            <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0" />
            <p>{apiSuccess}</p>
          </div>
        )}

        {/* Error Alert Box */}
        {apiError && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3 text-red-700 text-sm">
            <AlertTriangle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-bold text-red-800">Reset Failed</h4>
              <p className="mt-1 text-red-700">{apiError}</p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmitReset(onResetPasswordSubmit)} className="space-y-6">
          {/* OTP boxes */}
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">
              Verification Code
            </label>
            <div className="flex justify-between gap-2 py-2">
              {otp.map((digit, index) => (
                <input
                  key={index}
                  type="text"
                  maxLength={1}
                  value={digit}
                  ref={(el) => {
                    inputRefs.current[index] = el;
                  }}
                  onChange={(e) => handleOtpChange(e.target.value, index)}
                  onKeyDown={(e) => handleOtpKeyDown(e, index)}
                  onPaste={handleOtpPaste}
                  className="w-12 h-12 text-center text-xl font-bold border-2 border-slate-200 rounded-lg focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              ))}
            </div>
          </div>

          {/* New Password */}
          <div>
            <label htmlFor="new_password" className="block text-sm font-semibold text-slate-700 mb-2">
              New Password
            </label>
            <div className="relative">
              <input
                id="new_password"
                type={showNewPassword ? 'text' : 'password'}
                placeholder="••••••••"
                {...registerReset('new_password')}
                className={`border rounded-lg px-4 py-3 w-full text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                  resetErrors.new_password ? 'border-red-500 focus:ring-red-500' : 'border-slate-200'
                }`}
              />
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 hover:text-slate-600"
              >
                {showNewPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
              </button>
            </div>
            {resetErrors.new_password && (
              <p className="mt-1.5 text-sm text-red-500">{resetErrors.new_password.message}</p>
            )}
          </div>

          {/* Confirm Password */}
          <div>
            <label htmlFor="confirm_password" className="block text-sm font-semibold text-slate-700 mb-2">
              Confirm Password
            </label>
            <div className="relative">
              <input
                id="confirm_password"
                type={showConfirmPassword ? 'text' : 'password'}
                placeholder="••••••••"
                {...registerReset('confirm_password')}
                className={`border rounded-lg px-4 py-3 w-full text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                  resetErrors.confirm_password ? 'border-red-500 focus:ring-red-500' : 'border-slate-200'
                }`}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 hover:text-slate-600"
              >
                {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
              </button>
            </div>
            {resetErrors.confirm_password && (
              <p className="mt-1.5 text-sm text-red-500">{resetErrors.confirm_password.message}</p>
            )}
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={isLoading}
            className="bg-indigo-700 hover:bg-indigo-600 text-white font-semibold rounded-lg px-6 py-3 w-full transition-colors duration-200 flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              'Reset Password'
            )}
          </button>
        </form>
      </div>
    );
  }

  // Default State 3: Enter email address
  return (
    <div className="w-full max-w-md animate-fade-in">
      {/* Back to Login Link */}
      <Link
        to="/login"
        className="inline-flex items-center text-sm font-semibold text-indigo-600 hover:text-indigo-500 mb-8"
      >
        <ArrowLeft className="mr-1.5 h-4 w-4" /> Back to login
      </Link>

      <div className="mb-8">
        <h2 className="font-sora text-3xl font-bold tracking-tight text-slate-800">
          Forgot your password?
        </h2>
        <p className="mt-2 text-sm text-slate-500">
          Enter your work email and we'll send you a verification code.
        </p>
      </div>

      {/* Error Alert Box */}
      {apiError && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3 text-red-700 text-sm">
          <AlertTriangle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
          <div>
            <h4 className="font-bold text-red-800">Reset Request Failed</h4>
            <p className="mt-1 text-red-700">{apiError}</p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmitEmail(onRequestOtpSubmit)} className="space-y-6">
        <div>
          <label htmlFor="email" className="block text-sm font-semibold text-slate-700 mb-2">
            Work Email
          </label>
          <input
            id="email"
            type="email"
            placeholder="john@company.com"
            {...registerEmail('email')}
            className={`border rounded-lg px-4 py-3 w-full text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
              emailErrors.email ? 'border-red-500 focus:ring-red-500' : 'border-slate-200'
            }`}
          />
          {emailErrors.email && (
            <p className="mt-1.5 text-sm text-red-500">{emailErrors.email.message}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="bg-indigo-700 hover:bg-indigo-600 text-white font-semibold rounded-lg px-6 py-3 w-full transition-colors duration-200 flex items-center justify-center gap-2"
        >
          {isLoading ? (
            <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            'Send Reset Code'
          )}
        </button>
      </form>
    </div>
  );
};

export default ForgotPasswordPage;
