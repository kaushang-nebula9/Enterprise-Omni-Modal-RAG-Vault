import api from './api';
import type {
  UserResponse,
  MessageResponse,
  RegisterSignupPayload,
  VerifyOTPPayload,
  LoginPayload,
  ForgotPasswordPayload,
  ResetPasswordPayload,
  AcceptInvitePayload,
  GoogleOrgSetupPayload,
  SetPasswordPayload
} from '../types/auth';

export const registerSignup = async (data: RegisterSignupPayload): Promise<MessageResponse> => {
  const response = await api.post<MessageResponse>('/api/v1/auth/register/signup', data);
  return response.data;
};

export const verifyRegistrationOTP = async (data: VerifyOTPPayload): Promise<UserResponse> => {
  const response = await api.post<UserResponse>('/api/v1/auth/register/verify-otp', data);
  return response.data;
};

export const login = async (data: LoginPayload): Promise<UserResponse> => {
  const response = await api.post<UserResponse>('/api/v1/auth/login', data);
  return response.data;
};

export const logout = async (): Promise<void> => {
  await api.post('/api/v1/auth/logout');
};

export const getMe = async (): Promise<UserResponse> => {
  const response = await api.get<UserResponse>('/api/v1/auth/me');
  return response.data;
};

export const forgotPassword = async (data: ForgotPasswordPayload): Promise<MessageResponse> => {
  const response = await api.post<MessageResponse>('/api/v1/auth/forgot-password', data);
  return response.data;
};

export const resetPassword = async (data: ResetPasswordPayload): Promise<MessageResponse> => {
  const response = await api.post<MessageResponse>('/api/v1/auth/reset-password', data);
  return response.data;
};

export const acceptInvite = async (data: AcceptInvitePayload): Promise<MessageResponse> => {
  const response = await api.post<MessageResponse>('/api/v1/auth/accept-invite', data);
  return response.data;
};

export const initiateGoogleLogin = (): void => {
  window.location.href = `${import.meta.env.VITE_API_BASE_URL || 'https://enterprise-omni-modal-rag-vault.onrender.com'}/api/v1/auth/google`;
};

export const completeGoogleSetup = async (data: GoogleOrgSetupPayload): Promise<UserResponse> => {
  const response = await api.post<UserResponse>('/api/v1/auth/google/complete-setup', data);
  return response.data;
};

export const setPassword = async (data: SetPasswordPayload): Promise<MessageResponse> => {
  const response = await api.post<MessageResponse>('/api/v1/auth/set-password', data);
  return response.data;
};

export const updateProfile = async (data: { full_name?: string }): Promise<UserResponse> => {
  const response = await api.patch<UserResponse>('/api/v1/auth/profile', data);
  return response.data;
};

