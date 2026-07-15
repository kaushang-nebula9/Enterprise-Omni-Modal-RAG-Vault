import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertTriangle, Eye, EyeOff } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { completeGoogleSetup, setPassword } from "../../services/authService";
import { useAuthStore } from "../../store/authStore";
import type { UserResponse } from "../../types/auth";

const step1Schema = z.object({
  org_name: z.string().min(1, "Organisation name is required"),
  org_website: z
    .string()
    .min(1, "Organisation website is required")
    .url("Please enter a valid website URL (e.g. https://acme.com)"),
});

const step2Schema = z
  .object({
    new_password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string().min(1, "Confirm password is required"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type Step1FormValues = z.infer<typeof step1Schema>;
type Step2FormValues = z.infer<typeof step2Schema>;

const GoogleOrgSetupPage: React.FC = () => {
  const navigate = useNavigate();
  const setUser = useAuthStore((state) => state.setUser);
  const [searchParams] = useSearchParams();
  const setupToken = searchParams.get("setup_token");

  const [step, setStep] = useState(1);
  const [createdUser, setCreatedUser] = useState<UserResponse | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Password visibility
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Step 1 Form
  const {
    register: registerStep1,
    handleSubmit: handleSubmitStep1,
    formState: { errors: errorsStep1 },
  } = useForm<Step1FormValues>({
    resolver: zodResolver(step1Schema),
    defaultValues: {
      org_name: "",
      org_website: "",
    },
  });

  // Step 2 Form
  const {
    register: registerStep2,
    handleSubmit: handleSubmitStep2,
    formState: { errors: errorsStep2 },
  } = useForm<Step2FormValues>({
    resolver: zodResolver(step2Schema),
    defaultValues: {
      new_password: "",
      confirm_password: "",
    },
  });

  const onStep1Submit = async (data: Step1FormValues) => {
    if (!setupToken) {
      setApiError(
        "Setup token is missing. Please try signing in with Google again.",
      );
      return;
    }

    setApiError(null);
    setIsLoading(true);
    try {
      const userResponse = await completeGoogleSetup({
        org_name: data.org_name,
        org_website: data.org_website,
        setup_token: setupToken,
      });
      setCreatedUser(userResponse);
      setStep(2);
    } catch (err: any) {
      if (err.response && err.response.data && err.response.data.detail) {
        setApiError(err.response.data.detail);
      } else {
        setApiError(
          "An error occurred during account setup. Please try again.",
        );
      }
    } finally {
      setIsLoading(false);
    }
  };

  const onStep2Submit = async (data: Step2FormValues) => {
    if (!createdUser) {
      setApiError("Account session not found. Please start over.");
      return;
    }

    setApiError(null);
    setIsLoading(true);
    try {
      // Set the password
      await setPassword({
        new_password: data.new_password,
        confirm_password: data.confirm_password,
      });
      // Store user with has_password = true in Zustand
      setUser({
        ...createdUser,
        has_password: true,
      });
      navigate("/dashboard");
    } catch (err: any) {
      if (err.response && err.response.data && err.response.data.detail) {
        setApiError(err.response.data.detail);
      } else {
        setApiError(
          "Failed to set password. You can try again later from your settings.",
        );
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSkipPassword = () => {
    if (createdUser) {
      setUser(createdUser);
      navigate("/dashboard");
    }
  };

  if (!setupToken) {
    return (
      <div className="w-full max-w-md animate-fade-in">
        <div className="mb-6 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/60 rounded-lg p-4 flex items-start gap-3 text-red-700 dark:text-red-400 text-sm">
          <AlertTriangle className="h-5 w-5 text-red-500 dark:text-red-455 shrink-0 mt-0.5" />
          <div>
            <h4 className="font-bold text-red-800 dark:text-red-300">
              Invalid setup link
            </h4>
            <p className="mt-1 text-red-700 dark:text-red-400/90">
              Please try signing in with Google again.
            </p>
          </div>
        </div>
        <Link
          to="/login"
          className="inline-flex justify-center w-full bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400 text-white font-semibold rounded-lg px-6 py-3 transition-colors duration-200"
        >
          Back to Login
        </Link>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md animate-fade-in">
      {step === 1 ? (
        <>
          {/* Headings */}
          <div className="mb-8">
            <h2 className="font-sora text-3xl font-bold tracking-tight text-slate-800 dark:text-slate-100">
              Almost there!
            </h2>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              Tell us about your organisation to complete your account setup.
            </p>
          </div>

          {/* API error alert box */}
          {apiError && (
            <div className="mb-6 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/60 rounded-lg p-4 flex items-start gap-3 text-red-700 dark:text-red-450 text-sm animate-fade-in">
              <AlertTriangle className="h-5 w-5 text-red-500 dark:text-red-455 shrink-0 mt-0.5" />
              <div>
                <h4 className="font-bold text-red-800 dark:text-red-300">
                  Setup Failed
                </h4>
                <p className="mt-1 text-red-700 dark:text-red-400/90">
                  {apiError}
                </p>
              </div>
            </div>
          )}

          {/* Setup Form */}
          <form
            onSubmit={handleSubmitStep1(onStep1Submit)}
            className="space-y-6"
          >
            {/* Organisation Name Field */}
            <div>
              <label
                htmlFor="org_name"
                className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2"
              >
                Organisation Name
              </label>
              <input
                id="org_name"
                type="text"
                placeholder="Acme Corporation"
                {...registerStep1("org_name")}
                className={`border rounded-lg px-4 py-3 w-full bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-550 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-400 focus:border-transparent ${
                  errorsStep1.org_name
                    ? "border-red-500 dark:border-red-450 focus:ring-red-500 dark:focus:ring-red-455"
                    : "border-slate-200 dark:border-slate-700"
                }`}
              />
              {errorsStep1.org_name && (
                <p className="mt-1.5 text-sm text-red-500 dark:text-red-400">
                  {errorsStep1.org_name.message}
                </p>
              )}
            </div>

            {/* Organisation Website Field */}
            <div>
              <label
                htmlFor="org_website"
                className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2"
              >
                Organisation Website
              </label>
              <input
                id="org_website"
                type="text"
                placeholder="https://acme.com"
                {...registerStep1("org_website")}
                className={`border rounded-lg px-4 py-3 w-full bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-550 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-400 focus:border-transparent ${
                  errorsStep1.org_website
                    ? "border-red-500 dark:border-red-450 focus:ring-red-500 dark:focus:ring-red-455"
                    : "border-slate-200 dark:border-slate-700"
                }`}
              />
              {errorsStep1.org_website && (
                <p className="mt-1.5 text-sm text-red-500 dark:text-red-400">
                  {errorsStep1.org_website.message}
                </p>
              )}
            </div>

            {/* Submit Button */}
            <div>
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
                  "Complete Setup"
                )}
              </button>
            </div>
          </form>
        </>
      ) : (
        <>
          {/* Step 2: Set Optional Password */}
          <div className="mb-8 animate-fade-in">
            <h2 className="font-sora text-3xl font-bold tracking-tight text-slate-800 dark:text-slate-100">
              Set a password
            </h2>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              Optional: Set a password to log in without Google in the future.
              You can skip this step if you prefer.
            </p>
          </div>

          {/* API error alert box */}
          {apiError && (
            <div className="mb-6 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/60 rounded-lg p-4 flex items-start gap-3 text-red-700 dark:text-red-450 text-sm animate-fade-in">
              <AlertTriangle className="h-5 w-5 text-red-500 dark:text-red-455 shrink-0 mt-0.5" />
              <div>
                <h4 className="font-bold text-red-800 dark:text-red-300">
                  Error setting password
                </h4>
                <p className="mt-1 text-red-700 dark:text-red-400/90">
                  {apiError}
                </p>
              </div>
            </div>
          )}

          {/* Password Form */}
          <form
            onSubmit={handleSubmitStep2(onStep2Submit)}
            className="space-y-6 animate-fade-in"
          >
            {/* New Password Field */}
            <div>
              <label
                htmlFor="new_password"
                className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2"
              >
                New Password
              </label>
              <div className="relative">
                <input
                  id="new_password"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  {...registerStep2("new_password")}
                  className={`border rounded-lg px-4 py-3 w-full bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-550 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-400 focus:border-transparent ${
                    errorsStep2.new_password
                      ? "border-red-500 dark:border-red-450 focus:ring-red-500 dark:focus:ring-red-455"
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
              {errorsStep2.new_password && (
                <p className="mt-1.5 text-sm text-red-500 dark:text-red-400">
                  {errorsStep2.new_password.message}
                </p>
              )}
            </div>

            {/* Confirm Password Field */}
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
                  {...registerStep2("confirm_password")}
                  className={`border rounded-lg px-4 py-3 w-full bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-550 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-405 focus:border-transparent ${
                    errorsStep2.confirm_password
                      ? "border-red-500 dark:border-red-450 focus:ring-red-500 dark:focus:ring-red-455"
                      : "border-slate-200 dark:border-slate-700"
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 dark:text-slate-550 hover:text-slate-600 dark:hover:text-slate-350"
                >
                  {showConfirmPassword ? (
                    <EyeOff className="h-5 w-5" />
                  ) : (
                    <Eye className="h-5 w-5" />
                  )}
                </button>
              </div>
              {errorsStep2.confirm_password && (
                <p className="mt-1.5 text-sm text-red-500 dark:text-red-400">
                  {errorsStep2.confirm_password.message}
                </p>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex gap-4">
              <button
                type="button"
                onClick={handleSkipPassword}
                className="border border-slate-200 dark:border-slate-700 rounded-lg px-6 py-3 w-1/3 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 font-semibold hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors duration-200 text-center"
              >
                Skip
              </button>
              <button
                type="submit"
                disabled={isLoading}
                className="bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400 text-white font-semibold rounded-lg px-6 py-3 w-2/3 transition-colors duration-200 flex items-center justify-center gap-2"
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
                  "Save and Continue"
                )}
              </button>
            </div>
          </form>
        </>
      )}
    </div>
  );
};

export default GoogleOrgSetupPage;
