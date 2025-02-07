import { Visibility, VisibilityOff } from "@mui/icons-material"
import {
  Button,
  CircularProgress,
  FormControl,
  IconButton,
  InputAdornment,
  TextField,
} from "@mui/material"
import { useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { client, loginLoginAccessTokenMutation } from "../client"
import { AuthContext, type AuthProviderProps, type AuthState } from "./base"

export default function InternalAuthProvider({
  children,
  apiBaseUrl,
}: AuthProviderProps) {
  const [showPassword, setShowPassword] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    defaultValues: {
      username: "",
      password: "",
    },
  })

  const loginMutation = useMutation({
    ...loginLoginAccessTokenMutation(),
    onMutate: () => {
      client.setConfig({
        baseURL: apiBaseUrl,
      })
    },
    onSuccess: (data) => {
      client.setConfig({
        auth: data.access_token,
      })
      console.log("nats jwt:", data.nats_jwt)
    },
    onError: (err) => {
      console.log(err)
    },
  })

  const onSubmit: SubmitHandler<{
    username: string
    password: string
  }> = async (data) => {
    await loginMutation.mutateAsync({
      body: { username: data.username, password: data.password },
    })
  }

  const value: AuthState = {
    token: loginMutation.data?.access_token ?? null,
    natsJwt: loginMutation.data?.nats_jwt ?? null,
    isAuthenticated: loginMutation.isSuccess,
    isLoading: loginMutation.isPending,
    error: loginMutation.error ?? null,
  }

  if (value.isAuthenticated) {
    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  }

  return (
    <AuthContext.Provider value={value}>
      <div className="login-container">
        <div className="login-form">
          <h1>Login</h1>
          <form onSubmit={handleSubmit(onSubmit)}>
            <FormControl fullWidth sx={{ marginBottom: 2 }}>
              <TextField
                label="Username"
                variant="outlined"
                {...register("username", { required: "Username is required" })}
                error={!!errors.username}
                helperText={errors.username?.message}
              />
            </FormControl>

            <FormControl fullWidth sx={{ marginBottom: 2 }}>
              <TextField
                label="Password"
                variant="outlined"
                type={showPassword ? "text" : "password"}
                slotProps={{
                  input: {
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={() => setShowPassword(!showPassword)}
                          edge="end"
                        >
                          {showPassword ? <VisibilityOff /> : <Visibility />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  },
                }}
                {...register("password", { required: "Password is required" })}
                error={!!errors.password}
                helperText={errors.password?.message}
              />
            </FormControl>

            {value.error && (
              <FormControl fullWidth sx={{ marginBottom: 2 }}>
                <TextField
                  fullWidth
                  variant="outlined"
                  value={value.error.message}
                  error
                  helperText={value.error.message}
                />
              </FormControl>
            )}

            <Button
              fullWidth
              variant="contained"
              type="submit"
              disabled={loginMutation.isPending}
              sx={{ marginTop: 2 }}
            >
              {loginMutation.isPending ? (
                <CircularProgress size={20} />
              ) : (
                "Login"
              )}
            </Button>
          </form>
        </div>
      </div>
    </AuthContext.Provider>
  )
}