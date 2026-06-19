import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { acceptInvite } from '../../services/authService';

const acceptInviteSchema = z.object({
  password: z.string().min(8, 'Password must be at least 8 characters'),
  confirm_password: z.string().min(1, 'Confirm password is required'),
}).refine((data) => data.password === data.confirm_password, {
  message: "Passwords do not match",
  path: ['confirm_password'],
});

type AcceptInviteFormValues = z.infer<typeof acceptInviteSchema>;

const AcceptInvitePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  
  const [apiError, setApiError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AcceptInviteFormValues>({
    resolver: zodResolver(acceptInviteSchema),
    defaultValues: { password: '', confirm_password: '' },
  });

  const onSubmit = async (data: AcceptInviteFormValues) => {
    if (!token) {
      setApiError('Invalid or missing invite link. Please contact your administrator.');
      return;
    }

    setApiError(null);
    setIsLoading(true);
    try {
      await acceptInvite({
        token,
        password: data.password,
      });
      setIsSuccess(true);
    } catch (err: any) {
      if (err.response && err.response.data && err.response.data.detail) {
        setApiError(err.response.data.detail);
      } else {
        setApiError('Failed to activate your account. The invite link may have expired or is invalid.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // If successfully activated
  if (isSuccess) {
    return (
      <div className="w-full max-w-md animate-fade-in text-center">
        <div className="flex justify-center mb-6">
          <CheckCircle2 className="h-16 w-16 text-emerald-500 dark:text-emerald-450" />
        </div>
        <h2 className="font-sora text-3xl font-bold tracking-tight text-slate-800 dark:text-slate-100 mb-4">
          Account Activated!
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-8">
          Your account has been set up successfully. You can now log in to the system.
        </p>
        <Link
          to="/login"
          className="bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400 text-white font-semibold rounded-lg px-6 py-3 w-full block transition-colors duration-200"
        >
          Sign in to your account
        </Link>
      </div>
    );
  }

  // If token is missing from URL query parameter
  if (!token) {
    return (
      <div className="w-full max-w-md animate-fade-in">
        <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/60 rounded-lg p-6 flex flex-col items-center text-center">
          <AlertTriangle className="h-12 w-12 text-red-500 dark:text-red-400 mb-4" />
          <h3 className="font-sora text-xl font-bold text-red-800 dark:text-red-300 mb-2">Invalid Invite Link</h3>
          <p className="text-sm text-red-700 dark:text-red-400/90 mb-6">
            Invalid or missing invite link. Please contact your administrator to receive a valid invitation email.
          </p>
          <Link
            to="/login"
            className="text-sm font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300 flex items-center gap-1.5"
          >
            Go to login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md animate-fade-in">
      <div className="mb-8">
        <h2 className="font-sora text-3xl font-bold tracking-tight text-slate-800 dark:text-slate-100">
          Welcome to RAG Vault
        </h2>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400 font-sans">
          You have been invited to join your organisation. Set a password to activate your account.
        </p>
      </div>

      {/* Error Alert Box */}
      {apiError && (
        <div className="mb-6 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/60 rounded-lg p-4 flex items-start gap-3 text-red-700 dark:text-red-450 text-sm">
          <AlertTriangle className="h-5 w-5 text-red-500 dark:text-red-455 shrink-0 mt-0.5" />
          <div>
            <h4 className="font-bold text-red-800 dark:text-red-300">Activation Failed</h4>
            <p className="mt-1 text-red-700 dark:text-red-400/90">{apiError}</p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Choose a Password */}
        <div>
          <label htmlFor="password" className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
            Choose a Password
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              placeholder="••••••••"
              {...register('password')}
              className={`border rounded-lg px-4 py-3 w-full bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-550 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-400 focus:border-transparent ${
                errors.password ? 'border-red-500 dark:border-red-450 focus:ring-red-500 dark:focus:ring-red-450' : 'border-slate-200 dark:border-slate-700'
              }`}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 dark:text-slate-550 hover:text-slate-600 dark:hover:text-slate-350"
            >
              {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
            </button>
          </div>
          {errors.password && (
            <p className="mt-1.5 text-sm text-red-500 dark:text-red-400">{errors.password.message}</p>
          )}
        </div>

        {/* Confirm Password */}
        <div>
          <label htmlFor="confirm_password" className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
            Confirm Password
          </label>
          <div className="relative">
            <input
              id="confirm_password"
              type={showConfirmPassword ? 'text' : 'password'}
              placeholder="••••••••"
              {...register('confirm_password')}
              className={`border rounded-lg px-4 py-3 w-full bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-550 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-405 focus:border-transparent ${
                errors.confirm_password ? 'border-red-500 dark:border-red-450 focus:ring-red-500 dark:focus:ring-red-450' : 'border-slate-200 dark:border-slate-700'
              }`}
            />
            <button
              type="button"
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 dark:text-slate-550 hover:text-slate-600 dark:hover:text-slate-350"
            >
              {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
            </button>
          </div>
          {errors.confirm_password && (
            <p className="mt-1.5 text-sm text-red-500 dark:text-red-400">{errors.confirm_password.message}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400 text-white font-semibold rounded-lg px-6 py-3 w-full transition-colors duration-200 flex items-center justify-center gap-2"
        >
          {isLoading ? (
            <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            'Activate Account'
          )}
        </button>
      </form>
    </div>
  );
};

export default AcceptInvitePage;
