import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Eye,
  EyeOff,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
} from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { resetPassword } from "../../services/authService";

const resetSchema = z
  .object({
    email: z
      .string()
      .min(1, "Email is required")
      .email("Please enter a valid email address"),
    otp: z
      .string()
      .min(6, "Verification code must be 6 characters")
      .max(6, "Verification code must be 6 characters"),
    new_password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string().min(1, "Confirm password is required"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type ResetFormValues = z.infer<typeof resetSchema>;

const ResetPasswordPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const initialEmail = searchParams.get("email") || "";

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [apiError, setApiError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetFormValues>({
    resolver: zodResolver(resetSchema),
    defaultValues: {
      email: initialEmail,
      otp: "",
      new_password: "",
      confirm_password: "",
    },
  });

  const onSubmit = async (data: ResetFormValues) => {
    setApiError(null);
    setIsLoading(true);
    try {
      await resetPassword({
        email: data.email,
        otp: data.otp,
        new_password: data.new_password,
        confirm_password: data.confirm_password,
      });
      setIsSuccess(true);
    } catch (err: any) {
      if (err.response && err.response.data && err.response.data.detail) {
        setApiError(err.response.data.detail);
      } else {
        setApiError(
          "Failed to reset password. Please check the code and try again.",
        );
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (isSuccess) {
    return (
      <div className="w-full max-w-md animate-fade-in text-center">
        <div className="flex justify-center mb-6">
          <CheckCircle2 className="h-16 w-16 text-emerald-500 dark:text-emerald-450" />
        </div>
        <h2 className="font-sora text-3xl font-bold tracking-tight text-slate-800 dark:text-slate-100 mb-4">
          Password Reset Complete
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-8 font-sans">
          Your password has been reset successfully. You can now log in using
          your new credentials.
        </p>
        <Link
          to="/login"
          className="bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400 text-white font-semibold rounded-lg px-6 py-3 w-full block transition-colors duration-200"
        >
          Back to login
        </Link>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md animate-fade-in">
      <Link
        to="/login"
        className="inline-flex items-center text-sm font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300 mb-8"
      >
        <ArrowLeft className="mr-1.5 h-4 w-4" /> Back to login
      </Link>

      <div className="mb-8">
        <h2 className="font-sora text-3xl font-bold tracking-tight text-slate-800 dark:text-slate-100">
          Reset password
        </h2>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400 font-sans">
          Enter your verification code and choose a new password.
        </p>
      </div>

      {apiError && (
        <div className="mb-6 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/60 rounded-lg p-4 flex items-start gap-3 text-red-700 dark:text-red-450 text-sm">
          <AlertTriangle className="h-5 w-5 text-red-500 dark:text-red-450 shrink-0 mt-0.5" />
          <div>
            <h4 className="font-bold text-red-800 dark:text-red-300">
              Reset Failed
            </h4>
            <p className="mt-1 text-red-700 dark:text-red-400/90">{apiError}</p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Email */}
        <div>
          <label
            htmlFor="email"
            className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2"
          >
            Work Email
          </label>
          <input
            id="email"
            type="email"
            placeholder="john@acme.com"
            {...register("email")}
            className={`border rounded-lg px-4 py-3 w-full bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-550 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-400 focus:border-transparent ${
              errors.email
                ? "border-red-500 dark:border-red-450 focus:ring-red-500 dark:focus:ring-red-450"
                : "border-slate-200 dark:border-slate-700"
            }`}
          />
          {errors.email && (
            <p className="mt-1.5 text-sm text-red-500 dark:text-red-400">
              {errors.email.message}
            </p>
          )}
        </div>

        {/* OTP Code */}
        <div>
          <label
            htmlFor="otp"
            className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2"
          >
            6-digit Code
          </label>
          <input
            id="otp"
            type="text"
            placeholder="123456"
            maxLength={6}
            {...register("otp")}
            className={`border rounded-lg px-4 py-3 w-full bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-550 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-400 focus:border-transparent tracking-widest font-mono text-center text-lg ${
              errors.otp
                ? "border-red-500 dark:border-red-450 focus:ring-red-500 dark:focus:ring-red-450"
                : "border-slate-200 dark:border-slate-700"
            }`}
          />
          {errors.otp && (
            <p className="mt-1.5 text-sm text-red-500 dark:text-red-400">
              {errors.otp.message}
            </p>
          )}
        </div>

        {/* New Password */}
        <div>
          <label
            htmlFor="new_password"
            className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2"
          >
            Choose a Password
          </label>
          <div className="relative">
            <input
              id="new_password"
              type={showPassword ? "text" : "password"}
              placeholder="••••••••"
              {...register("new_password")}
              className={`border rounded-lg px-4 py-3 w-full bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-550 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-400 focus:border-transparent ${
                errors.new_password
                  ? "border-red-500 dark:border-red-450 focus:ring-red-500 dark:focus:ring-red-450"
                  : "border-slate-200 dark:border-slate-700"
              }`}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-350"
            >
              {showPassword ? (
                <EyeOff className="h-5 w-5" />
              ) : (
                <Eye className="h-5 w-5" />
              )}
            </button>
          </div>
          {errors.new_password && (
            <p className="mt-1.5 text-sm text-red-500 dark:text-red-400">
              {errors.new_password.message}
            </p>
          )}
        </div>

        {/* Confirm Password */}
        <div>
          <label
            htmlFor="confirm_password"
            className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2"
          >
            Confirm Password
          </label>
          <div className="relative">
            <input
              id="confirm_password"
              type={showConfirmPassword ? "text" : "password"}
              placeholder="••••••••"
              {...register("confirm_password")}
              className={`border rounded-lg px-4 py-3 w-full bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-550 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-405 focus:border-transparent ${
                errors.confirm_password
                  ? "border-red-500 dark:border-red-450 focus:ring-red-500 dark:focus:ring-red-450"
                  : "border-slate-200 dark:border-slate-700"
              }`}
            />
            <button
              type="button"
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-350"
            >
              {showConfirmPassword ? (
                <EyeOff className="h-5 w-5" />
              ) : (
                <Eye className="h-5 w-5" />
              )}
            </button>
          </div>
          {errors.confirm_password && (
            <p className="mt-1.5 text-sm text-red-500 dark:text-red-400">
              {errors.confirm_password.message}
            </p>
          )}
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400 text-white font-semibold rounded-lg px-6 py-3 w-full transition-colors duration-200 flex items-center justify-center gap-2"
        >
          {isLoading ? (
            <svg
              className="animate-spin h-5 w-5 text-white"
              fill="none"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
          ) : (
            "Reset Password"
          )}
        </button>
      </form>
    </div>
  );
};

export default ResetPasswordPage;
