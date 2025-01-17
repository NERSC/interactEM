import { Auth, Client } from "@hey-api/client-axios"

export const getTokenFromClient = async (
  client: Client,
): Promise<string | undefined> => {
  const auth = client.getConfig().auth

  if (!auth) {
    return undefined
  }

  if (typeof auth === "string") {
    return auth
  }

  const defaultAuth: Auth = {
    type: "http",
    scheme: "bearer",
  }

  return await auth(defaultAuth)
}
