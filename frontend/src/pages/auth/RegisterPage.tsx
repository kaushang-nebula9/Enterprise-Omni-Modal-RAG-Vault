import React, { useState, useRef, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, AlertTriangle, ArrowLeft } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { registerSignup, verifyRegistrationOTP } from '../../services/authService';
import { useAuthStore } from '../../store/authStore';

const registerSchema = z.object({
  org_name: z.string().min(1, 'Organisation name is required'),
  org_website: z.string().min(1, 'Organisation website is required').url('Please enter a valid website URL (e.g. https://acme.com)'),
  full_name: z.string().min(1, 'Full name is required'),
  email: z.string().min(1, 'Work email is required').email('Please enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  confirm_password: z.string().min(1, 'Confirm password is required'),
}).refine((data) => data.password === data.confirm_password, {
  message: "Passwords do not match",
  path: ['confirm_password'],
});

type RegisterFormValues = z.infer<typeof registerSchema>;

const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const setUser = useAuthStore((state) => state.setUser);

  const [step, setStep] = useState(1);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // OTP State
  const [otp, setOtp] = useState<string[]>(Array(6).fill(''));
  const [cooldown, setCooldown] = useState(0);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  const {
    register,
    handleSubmit,
    trigger,
    getValues,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      org_name: '',
      org_website: '',
      full_name: '',
      email: '',
      password: '',
      confirm_password: '',
    },
    mode: 'onTouched',
  });

  // Handle Cooldown Timer
  useEffect(() => {
    if (cooldown > 0) {
      const timer = setTimeout(() => setCooldown(cooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [cooldown]);

  const handleNextStep = async () => {
    // Validate Step 1 fields
    const isStep1Valid = await trigger(['org_name', 'org_website']);
    if (isStep1Valid) {
      setApiError(null);
      setStep(2);
    }
  };

  const handleBackStep = () => {
    setApiError(null);
    setStep(1);
  };

  // Step 2 Submission (calls registerSignup)
  const onSignupSubmit = async (data: RegisterFormValues) => {
    setApiError(null);
    setIsLoading(true);
    try {
      await registerSignup({
        org_name: data.org_name,
        org_website: data.org_website,
        full_name: data.full_name,
        email: data.email,
        password: data.password,
        confirm_password: data.confirm_password,
      });
      setStep(3);
      setCooldown(60); // Start 60-second cooldown
    } catch (err: any) {
      if (err.response && err.response.data && err.response.data.detail) {
        setApiError(err.response.data.detail);
      } else {
        setApiError('An error occurred during registration. Please check your details and try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // OTP input handlers
  const handleOtpChange = (value: string, index: number) => {
    const cleanValue = value.replace(/[^a-zA-Z0-9]/g, '');
    const newOtp = [...otp];
    const char = cleanValue.slice(-1); // Take last char
    newOtp[index] = char;
    setOtp(newOtp);

    // Auto-focus next input
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

  // Step 3 Submission (calls verifyRegistrationOTP)
  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    const otpCode = otp.join('');
    if (otpCode.length < 6) {
      setApiError('Please enter all 6 digits of the verification code.');
      return;
    }

    setApiError(null);
    setIsLoading(true);
    try {
      const userResponse = await verifyRegistrationOTP({
        email: getValues('email'),
        otp: otpCode,
      });
      setUser(userResponse);
      navigate('/dashboard');
    } catch (err: any) {
      if (err.response && err.response.data && err.response.data.detail) {
        setApiError(err.response.data.detail);
      } else {
        setApiError('Invalid or expired verification code. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (cooldown > 0) return;
    setApiError(null);
    try {
      const data = getValues();
      await registerSignup({
        org_name: data.org_name,
        org_website: data.org_website,
        full_name: data.full_name,
        email: data.email,
        password: data.password,
        confirm_password: data.confirm_password,
      });
      setCooldown(60);
      setOtp(Array(6).fill(''));
      inputRefs.current[0]?.focus();
    } catch (err: any) {
      if (err.response && err.response.data && err.response.data.detail) {
        setApiError(err.response.data.detail);
      } else {
        setApiError('Failed to resend verification code. Please try again.');
      }
    }
  };

  return (
    <div className="w-full max-w-md">
      {/* Progress Indicator */}
      <div className="mb-10 w-full select-none">
        <div className="flex items-center justify-between relative">
          {/* Step 1 */}
          <div className="flex flex-col items-center flex-1 z-10">
            <div
              className={`flex h-10 w-10 items-center justify-center rounded-full border-2 text-sm font-bold transition-all duration-200 ${
                step > 1
                  ? 'border-indigo-700 bg-white text-indigo-700'
                  : step === 1
                  ? 'border-indigo-700 bg-indigo-700 text-white ring-4 ring-indigo-100'
                  : 'border-slate-200 bg-white text-slate-400'
              }`}
            >
              {step > 1 ? '✓' : '1'}
            </div>
            <span className={`mt-2 text-xs font-semibold ${step >= 1 ? 'text-indigo-700' : 'text-slate-400'}`}>
              Organisation
            </span>
          </div>

          {/* Line 1 */}
          <div className="absolute left-[16.6%] right-[50%] top-5 h-0.5 -translate-y-1/2 bg-slate-200 z-0">
            <div
              className="h-full bg-indigo-700 transition-all duration-300"
              style={{ width: step > 1 ? '100%' : '0%' }}
            ></div>
          </div>

          {/* Step 2 */}
          <div className="flex flex-col items-center flex-1 z-10">
            <div
              className={`flex h-10 w-10 items-center justify-center rounded-full border-2 text-sm font-bold transition-all duration-200 ${
                step > 2
                  ? 'border-indigo-700 bg-white text-indigo-700'
                  : step === 2
                  ? 'border-indigo-700 bg-indigo-700 text-white ring-4 ring-indigo-100'
                  : 'border-slate-200 bg-white text-slate-400'
              }`}
            >
              {step > 2 ? '✓' : '2'}
            </div>
            <span className={`mt-2 text-xs font-semibold ${step >= 2 ? 'text-indigo-700' : 'text-slate-400'}`}>
              Your Details
            </span>
          </div>

          {/* Line 2 */}
          <div className="absolute left-[50%] right-[16.6%] top-5 h-0.5 -translate-y-1/2 bg-slate-200 z-0">
            <div
              className="h-full bg-indigo-700 transition-all duration-300"
              style={{ width: step > 2 ? '100%' : '0%' }}
            ></div>
          </div>

          {/* Step 3 */}
          <div className="flex flex-col items-center flex-1 z-10">
            <div
              className={`flex h-10 w-10 items-center justify-center rounded-full border-2 text-sm font-bold transition-all duration-200 ${
                step === 3
                  ? 'border-indigo-700 bg-indigo-700 text-white ring-4 ring-indigo-100'
                  : 'border-slate-200 bg-white text-slate-400'
              }`}
            >
              3
            </div>
            <span className={`mt-2 text-xs font-semibold ${step === 3 ? 'text-indigo-700' : 'text-slate-400'}`}>
              Verify Email
            </span>
          </div>
        </div>
      </div>

      {/* General error alert box */}
      {apiError && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3 text-red-700 text-sm animate-fade-in">
          <AlertTriangle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
          <div>
            <h4 className="font-bold text-red-800">Registration Error</h4>
            <p className="mt-1 text-red-700">{apiError}</p>
          </div>
        </div>
      )}

      {/* STEP 1: Organisation Details */}
      {step === 1 && (
        <div className="animate-fade-in">
          <div className="mb-8">
            <h2 className="font-sora text-3xl font-bold tracking-tight text-slate-800">
              Tell us about your organisation
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              Set up the workspace identity for your secure documents.
            </p>
          </div>

          <div className="space-y-6">
            <div>
              <label htmlFor="org_name" className="block text-sm font-semibold text-slate-700 mb-2">
                Organisation Name
              </label>
              <input
                id="org_name"
                type="text"
                placeholder="Acme Corporation"
                {...register('org_name')}
                className={`border rounded-lg px-4 py-3 w-full text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                  errors.org_name ? 'border-red-500 focus:ring-red-500' : 'border-slate-200'
                }`}
              />
              {errors.org_name && (
                <p className="mt-1.5 text-sm text-red-500">{errors.org_name.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="org_website" className="block text-sm font-semibold text-slate-700 mb-2">
                Organisation Website
              </label>
              <input
                id="org_website"
                type="text"
                placeholder="https://acme.com"
                {...register('org_website')}
                className={`border rounded-lg px-4 py-3 w-full text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                  errors.org_website ? 'border-red-500 focus:ring-red-500' : 'border-slate-200'
                }`}
              />
              {errors.org_website && (
                <p className="mt-1.5 text-sm text-red-500">{errors.org_website.message}</p>
              )}
            </div>

            <button
              type="button"
              onClick={handleNextStep}
              className="bg-indigo-700 hover:bg-indigo-600 text-white font-semibold rounded-lg px-6 py-3 w-full transition-colors duration-200"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* STEP 2: Admin details */}
      {step === 2 && (
        <form onSubmit={handleSubmit(onSignupSubmit)} className="space-y-6 animate-fade-in">
          <div className="mb-6">
            <h2 className="font-sora text-3xl font-bold tracking-tight text-slate-800">
              Create your admin account
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              You will be configured as the tenant administrator.
            </p>
          </div>

          <div>
            <label htmlFor="full_name" className="block text-sm font-semibold text-slate-700 mb-2">
              Full Name
            </label>
            <input
              id="full_name"
              type="text"
              placeholder="John Doe"
              {...register('full_name')}
              className={`border rounded-lg px-4 py-3 w-full text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                errors.full_name ? 'border-red-500 focus:ring-red-500' : 'border-slate-200'
              }`}
            />
            {errors.full_name && (
              <p className="mt-1.5 text-sm text-red-500">{errors.full_name.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-semibold text-slate-700 mb-2">
              Work Email
            </label>
            <input
              id="email"
              type="email"
              placeholder="john@acme.com"
              {...register('email')}
              className={`border rounded-lg px-4 py-3 w-full text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                errors.email ? 'border-red-500 focus:ring-red-500' : 'border-slate-200'
              }`}
            />
            {errors.email && (
              <p className="mt-1.5 text-sm text-red-500">{errors.email.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-semibold text-slate-700 mb-2">
              Password
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                {...register('password')}
                className={`border rounded-lg px-4 py-3 w-full text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                  errors.password ? 'border-red-500 focus:ring-red-500' : 'border-slate-200'
                }`}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 hover:text-slate-600"
              >
                {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
              </button>
            </div>
            {errors.password && (
              <p className="mt-1.5 text-sm text-red-500">{errors.password.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="confirm_password" className="block text-sm font-semibold text-slate-700 mb-2">
              Confirm Password
            </label>
            <div className="relative">
              <input
                id="confirm_password"
                type={showConfirmPassword ? 'text' : 'password'}
                placeholder="••••••••"
                {...register('confirm_password')}
                className={`border rounded-lg px-4 py-3 w-full text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                  errors.confirm_password ? 'border-red-500 focus:ring-red-500' : 'border-slate-200'
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
            {errors.confirm_password && (
              <p className="mt-1.5 text-sm text-red-500">{errors.confirm_password.message}</p>
            )}
          </div>

          <div className="flex gap-4">
            <button
              type="button"
              onClick={handleBackStep}
              className="border border-slate-200 rounded-lg px-6 py-3 w-1/3 text-slate-700 font-semibold hover:bg-slate-50 transition-colors duration-200 flex items-center justify-center gap-1.5"
            >
              <ArrowLeft className="h-4 w-4" /> Back
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="bg-indigo-700 hover:bg-indigo-600 text-white font-semibold rounded-lg px-6 py-3 w-2/3 transition-colors duration-200 flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                'Send Verification Code'
              )}
            </button>
          </div>
        </form>
      )}

      {/* STEP 3: OTP Verification */}
      {step === 3 && (
        <form onSubmit={handleVerifyOtp} className="space-y-6 animate-fade-in">
          <div className="mb-6">
            <h2 className="font-sora text-3xl font-bold tracking-tight text-slate-800">
              Check your email
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              We sent a 6-digit code to <span className="font-semibold text-slate-800">{getValues('email')}</span>. Enter it below to verify your account.
            </p>
          </div>

          {/* OTP boxes */}
          <div className="flex justify-between gap-2 py-4">
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
              'Verify Email'
            )}
          </button>

          {/* Resend Link with Cooldown */}
          <div className="text-center">
            {cooldown > 0 ? (
              <p className="text-sm text-slate-500">
                Resend code in <span className="font-semibold text-slate-700">{cooldown}s</span>
              </p>
            ) : (
              <button
                type="button"
                onClick={handleResendOtp}
                className="text-sm font-semibold text-indigo-600 hover:text-indigo-500"
              >
                Resend code
              </button>
            )}
          </div>
        </form>
      )}

      {/* Redirect back to Login */}
      <div className="mt-8 text-center text-sm text-slate-500">
        Already have an account?{' '}
        <Link to="/login" className="font-semibold text-indigo-600 hover:text-indigo-500">
          Sign in
        </Link>
      </div>
    </div>
  );
};

export default RegisterPage;
