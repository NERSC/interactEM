// This file is auto-generated by @hey-api/openapi-ts

import {
  createClient,
  createConfig,
  type Options,
  urlSearchParamsBodySerializer,
} from "@hey-api/client-axios"
import type {
  LoginAccessTokenData,
  LoginAccessTokenError,
  LoginAccessTokenResponse,
  TestTokenError,
  TestTokenResponse,
  RecoverPasswordData,
  RecoverPasswordError,
  RecoverPasswordResponse,
  ResetPasswordData,
  ResetPasswordError,
  ResetPasswordResponse,
  RecoverPasswordHtmlContentData,
  RecoverPasswordHtmlContentError,
  RecoverPasswordHtmlContentResponse,
  ReadUsersData,
  ReadUsersError,
  ReadUsersResponse,
  CreateUserData,
  CreateUserError,
  CreateUserResponse,
  ReadUserMeError,
  ReadUserMeResponse,
  DeleteUserMeError,
  DeleteUserMeResponse,
  UpdateUserMeData,
  UpdateUserMeError,
  UpdateUserMeResponse,
  UpdatePasswordMeData,
  UpdatePasswordMeError,
  UpdatePasswordMeResponse,
  RegisterUserData,
  RegisterUserError,
  RegisterUserResponse,
  ReadUserByIdData,
  ReadUserByIdError,
  ReadUserByIdResponse,
  UpdateUserData,
  UpdateUserError,
  UpdateUserResponse,
  DeleteUserData,
  DeleteUserError,
  DeleteUserResponse,
  TestEmailData,
  TestEmailError,
  TestEmailResponse,
  ReadPipelinesData,
  ReadPipelinesError,
  ReadPipelinesResponse,
  CreatePipelineData,
  CreatePipelineError,
  CreatePipelineResponse,
  ReadPipelineData,
  ReadPipelineError,
  ReadPipelineResponse,
  DeletePipelineData,
  DeletePipelineError,
  DeletePipelineResponse,
  RunPipelineData,
  RunPipelineError,
  RunPipelineResponse,
} from "./types.gen"

export const client = createClient(createConfig())

/**
 * Login Access Token
 * OAuth2 compatible token login, get an access token for future requests
 */
export const loginAccessToken = <ThrowOnError extends boolean = false>(
  options: Options<LoginAccessTokenData, ThrowOnError>,
) => {
  return (options?.client ?? client).post<
    LoginAccessTokenResponse,
    LoginAccessTokenError,
    ThrowOnError
  >({
    ...options,
    ...urlSearchParamsBodySerializer,
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      ...options?.headers,
    },
    url: "/api/v1/login/access-token",
  })
}

/**
 * Test Token
 * Test access token
 */
export const testToken = <ThrowOnError extends boolean = false>(
  options?: Options<unknown, ThrowOnError>,
) => {
  return (options?.client ?? client).post<
    TestTokenResponse,
    TestTokenError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/login/test-token",
  })
}

/**
 * Recover Password
 * Password Recovery
 */
export const recoverPassword = <ThrowOnError extends boolean = false>(
  options: Options<RecoverPasswordData, ThrowOnError>,
) => {
  return (options?.client ?? client).post<
    RecoverPasswordResponse,
    RecoverPasswordError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/password-recovery/{email}",
  })
}

/**
 * Reset Password
 * Reset password
 */
export const resetPassword = <ThrowOnError extends boolean = false>(
  options: Options<ResetPasswordData, ThrowOnError>,
) => {
  return (options?.client ?? client).post<
    ResetPasswordResponse,
    ResetPasswordError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/reset-password/",
  })
}

/**
 * Recover Password Html Content
 * HTML Content for Password Recovery
 */
export const recoverPasswordHtmlContent = <
  ThrowOnError extends boolean = false,
>(
  options: Options<RecoverPasswordHtmlContentData, ThrowOnError>,
) => {
  return (options?.client ?? client).post<
    RecoverPasswordHtmlContentResponse,
    RecoverPasswordHtmlContentError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/password-recovery-html-content/{email}",
  })
}

/**
 * Read Users
 * Retrieve users.
 */
export const readUsers = <ThrowOnError extends boolean = false>(
  options?: Options<ReadUsersData, ThrowOnError>,
) => {
  return (options?.client ?? client).get<
    ReadUsersResponse,
    ReadUsersError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/users/",
  })
}

/**
 * Create User
 * Create new user.
 */
export const createUser = <ThrowOnError extends boolean = false>(
  options: Options<CreateUserData, ThrowOnError>,
) => {
  return (options?.client ?? client).post<
    CreateUserResponse,
    CreateUserError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/users/",
  })
}

/**
 * Read User Me
 * Get current user.
 */
export const readUserMe = <ThrowOnError extends boolean = false>(
  options?: Options<unknown, ThrowOnError>,
) => {
  return (options?.client ?? client).get<
    ReadUserMeResponse,
    ReadUserMeError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/users/me",
  })
}

/**
 * Delete User Me
 * Delete own user.
 */
export const deleteUserMe = <ThrowOnError extends boolean = false>(
  options?: Options<unknown, ThrowOnError>,
) => {
  return (options?.client ?? client).delete<
    DeleteUserMeResponse,
    DeleteUserMeError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/users/me",
  })
}

/**
 * Update User Me
 * Update own user.
 */
export const updateUserMe = <ThrowOnError extends boolean = false>(
  options: Options<UpdateUserMeData, ThrowOnError>,
) => {
  return (options?.client ?? client).patch<
    UpdateUserMeResponse,
    UpdateUserMeError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/users/me",
  })
}

/**
 * Update Password Me
 * Update own password.
 */
export const updatePasswordMe = <ThrowOnError extends boolean = false>(
  options: Options<UpdatePasswordMeData, ThrowOnError>,
) => {
  return (options?.client ?? client).patch<
    UpdatePasswordMeResponse,
    UpdatePasswordMeError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/users/me/password",
  })
}

/**
 * Register User
 * Create new user without the need to be logged in.
 */
export const registerUser = <ThrowOnError extends boolean = false>(
  options: Options<RegisterUserData, ThrowOnError>,
) => {
  return (options?.client ?? client).post<
    RegisterUserResponse,
    RegisterUserError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/users/signup",
  })
}

/**
 * Read User By Id
 * Get a specific user by id.
 */
export const readUserById = <ThrowOnError extends boolean = false>(
  options: Options<ReadUserByIdData, ThrowOnError>,
) => {
  return (options?.client ?? client).get<
    ReadUserByIdResponse,
    ReadUserByIdError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/users/{user_id}",
  })
}

/**
 * Update User
 * Update a user.
 */
export const updateUser = <ThrowOnError extends boolean = false>(
  options: Options<UpdateUserData, ThrowOnError>,
) => {
  return (options?.client ?? client).patch<
    UpdateUserResponse,
    UpdateUserError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/users/{user_id}",
  })
}

/**
 * Delete User
 * Delete a user.
 */
export const deleteUser = <ThrowOnError extends boolean = false>(
  options: Options<DeleteUserData, ThrowOnError>,
) => {
  return (options?.client ?? client).delete<
    DeleteUserResponse,
    DeleteUserError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/users/{user_id}",
  })
}

/**
 * Test Email
 * Test emails.
 */
export const testEmail = <ThrowOnError extends boolean = false>(
  options: Options<TestEmailData, ThrowOnError>,
) => {
  return (options?.client ?? client).post<
    TestEmailResponse,
    TestEmailError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/utils/test-email/",
  })
}

/**
 * Read Pipelines
 * Retrieve pipelines.
 */
export const readPipelines = <ThrowOnError extends boolean = false>(
  options?: Options<ReadPipelinesData, ThrowOnError>,
) => {
  return (options?.client ?? client).get<
    ReadPipelinesResponse,
    ReadPipelinesError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/pipelines/",
  })
}

/**
 * Create Pipeline
 * Create new pipeline.
 */
export const createPipeline = <ThrowOnError extends boolean = false>(
  options: Options<CreatePipelineData, ThrowOnError>,
) => {
  return (options?.client ?? client).post<
    CreatePipelineResponse,
    CreatePipelineError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/pipelines/",
  })
}

/**
 * Read Pipeline
 * Get pipeline by ID.
 */
export const readPipeline = <ThrowOnError extends boolean = false>(
  options: Options<ReadPipelineData, ThrowOnError>,
) => {
  return (options?.client ?? client).get<
    ReadPipelineResponse,
    ReadPipelineError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/pipelines/{id}",
  })
}

/**
 * Delete Pipeline
 * Delete an pipeline.
 */
export const deletePipeline = <ThrowOnError extends boolean = false>(
  options: Options<DeletePipelineData, ThrowOnError>,
) => {
  return (options?.client ?? client).delete<
    DeletePipelineResponse,
    DeletePipelineError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/pipelines/{id}",
  })
}

/**
 * Run Pipeline
 * Run a pipeline.
 */
export const runPipeline = <ThrowOnError extends boolean = false>(
  options: Options<RunPipelineData, ThrowOnError>,
) => {
  return (options?.client ?? client).post<
    RunPipelineResponse,
    RunPipelineError,
    ThrowOnError
  >({
    ...options,
    url: "/api/v1/pipelines/{id}/run",
  })
}