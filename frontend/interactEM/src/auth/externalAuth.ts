// interactEM/src/auth/externalAuth.ts
import { client, loginLoginWithExternalToken } from "../client"
import { zLoginLoginWithExternalTokenResponse } from "../client/generated/zod.gen"

export const loginWithExternalToken = async (token: string): Promise<void> => {
  try {
    // First set client token to external token
    client.setConfig({
      auth: () => `${token}`,
    })
    const response = await loginLoginWithExternalToken()

    // validate w zod
    const validatedData = zLoginLoginWithExternalTokenResponse.parse(
      response.data,
    )

    // Set the new token for future requests
    client.setConfig({
      auth: () => `${validatedData.access_token}`,
    })
  } catch (error) {
    console.error("Failed to login with external token:", error)
    throw error
  }
}
