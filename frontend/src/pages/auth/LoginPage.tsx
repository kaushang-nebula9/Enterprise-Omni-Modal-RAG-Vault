import React, { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, Mail, AlertTriangle } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { login, initiateGoogleLogin } from "../../services/authService";
import { useAuthStore } from "../../store/authStore";

const loginSchema = z.object({
  email: z
    .string()
    .min(1, "Email is required")
    .email("Please enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const setUser = useAuthStore((state) => state.setUser);
  const [searchParams] = useSearchParams();
  const errorParam = searchParams.get("error");

  const [showPassword, setShowPassword] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (errorParam === "inactive") {
      setApiError(
        "Your account is inactive. Please contact your administrator.",
      );
    }
  }, [errorParam]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const onSubmit = async (data: LoginFormValues) => {
    setApiError(null);
    setIsLoading(true);
    try {
      const userResponse = await login({
        email: data.email,
        password: data.password,
      });
      setUser(userResponse);
      navigate("/dashboard");
    } catch (err: any) {
      if (err.response && err.response.data && err.response.data.detail) {
        setApiError(err.response.data.detail);
      } else {
        setApiError("Incorrect email or password. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = () => {
    initiateGoogleLogin();
  };

  return (
    <div className="w-full max-w-md">
      {/* Headings */}
      <div className="mb-8">
        <h2 className="font-sora text-3xl font-bold tracking-tight text-slate-800 dark:text-slate-100">
          Sign in to your account
        </h2>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          Enter your credentials to access the secure repository.
        </p>
      </div>

      {/* Google OAuth Button */}
      <div className="relative mb-6">
        <button
          type="button"
          onClick={handleGoogleLogin}
          className="border border-slate-200 dark:border-slate-700 rounded-lg px-6 py-3 w-full flex items-center justify-center gap-3 text-slate-700 dark:text-slate-300 font-medium bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors duration-200"
        >
          <svg
            className="h-5 w-5"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              fill="#4285F4"
            />
            <path
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              fill="#34A853"
            />
            <path
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              fill="#FBBC05"
            />
            <path
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              fill="#EA4335"
            />
          </svg>
          Sign in with Google
        </button>
      </div>

      {/* Divider */}
      <div className="relative flex py-5 items-center">
        <div className="flex-grow border-t border-slate-200 dark:border-slate-800"></div>
        <span className="flex-shrink mx-4 text-xs font-semibold tracking-wider text-slate-400 dark:text-slate-500 uppercase">
          OR CONTINUE WITH
        </span>
        <div className="flex-grow border-t border-slate-200 dark:border-slate-800"></div>
      </div>

      {/* General error alert box */}
      {apiError && (
        <div className="mb-6 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/60 rounded-lg p-4 flex items-start gap-3 text-red-700 dark:text-red-400 text-sm animate-fade-in">
          <AlertTriangle className="h-5 w-5 text-red-500 dark:text-red-450 shrink-0 mt-0.5" />
          <div>
            <h4 className="font-bold text-red-800 dark:text-red-300">
              Authentication Failed
            </h4>
            <p className="mt-1 text-red-755 dark:text-red-400/90">{apiError}</p>
          </div>
        </div>
      )}

      {/* Login Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Email Field */}
        <div>
          <label
            htmlFor="email"
            className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2"
          >
            Email address
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <Mail className="h-5 w-5 text-slate-400 dark:text-slate-500" />
            </div>
            <input
              id="email"
              type="email"
              placeholder="name@company.com"
              {...register("email")}
              className={`border rounded-lg pl-11 pr-4 py-3 w-full bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-550 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-400 focus:border-transparent ${
                errors.email
                  ? "border-red-500 dark:border-red-450 focus:ring-red-500 dark:focus:ring-red-450"
                  : "border-slate-200 dark:border-slate-700"
              }`}
            />
          </div>
          {errors.email && (
            <p className="mt-1.5 text-sm text-red-500 dark:text-red-400">
              {errors.email.message}
            </p>
          )}
        </div>

        {/* Password Field */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label
              htmlFor="password"
              className="block text-sm font-semibold text-slate-700 dark:text-slate-300"
            >
              Password
            </label>
            <Link
              to="/forgot-password"
              className="text-sm font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300"
            >
              Forgot password?
            </Link>
          </div>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              placeholder="••••••••"
              {...register("password")}
              className={`border rounded-lg px-4 py-3 w-full bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-550 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-400 focus:border-transparent ${
                errors.password
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
          {errors.password && (
            <p className="mt-1.5 text-sm text-red-500 dark:text-red-400">
              {errors.password.message}
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
              "Sign in →"
            )}
          </button>
        </div>
      </form>

      {/* Support Link */}
      <div className="mt-6 text-center text-sm text-slate-500 dark:text-slate-400">
        Need help accessing your account?{" "}
        <a
          href="#"
          className="font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300"
        >
          Contact IT Support
        </a>
      </div>

            {/* Divider */}
      <div className="relative flex mt-2 items-center">
        <div className="flex-grow border-t border-slate-200 dark:border-slate-800"></div>
        <span className="flex-shrink mx-4 text-xs font-semibold tracking-wider text-slate-400 dark:text-slate-500 uppercase">
          OR
        </span>
        <div className="flex-grow border-t border-slate-200 dark:border-slate-800"></div>
      </div>

      {/* Redirect to Register */}
      <div className="mt-2 text-center text-sm text-slate-500 dark:text-slate-400">
        Want to register your organization?{" "}
        <Link
          to="/register"
          className="font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300"
        >
          Register
        </Link>
      </div>

    </div>
  );
};

export default LoginPage;
