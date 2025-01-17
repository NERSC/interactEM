import { useMutation } from "@tanstack/react-query";
import { loginLoginWithExternalToken } from "../client/generated/sdk.gen";
import type { LoginLoginWithExternalTokenResponse, Token } from "../client/generated/types.gen";
import { client } from "../client";


export const useExternalTokenLogin = () => {
  const loginExternally = useMutation<LoginLoginWithExternalTokenResponse, Error, Token>(
    {
    ...loginLoginWithExternalToken(),
      onMutate: (data) => {
        // Set the client instance to have authorization with the external token
        console.log("Logging in with external token:", data);
        client.setConfig({
            auth: () => data.access_token
        })
        console.log("set the access token:", client.getConfig().auth)
      },
      onSuccess: (data) => {
        // Set the token for InteractEM
        console.log("Logged in with external token:", data);
        client.setConfig({
            auth: () => data.access_token
        })
        console.log("set the access token:", client.getConfig().auth)
      },
      onError: (error) => {
        console.error("Failed to login with external token:", error);
      },
    }
  );

  return loginExternally;
};