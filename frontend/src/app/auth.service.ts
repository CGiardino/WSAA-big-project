import {
  AccountInfo,
  InteractionRequiredAuthError,
  PublicClientApplication,
  type AuthenticationResult,
} from '@azure/msal-browser';

interface AuthRuntimeConfig {
  enabled: boolean;
  tenantId: string;
  clientId: string;
  apiScope: string;
}

function readAuthConfig(): AuthRuntimeConfig {
  const auth = window.__WSAA_ENV__?.auth;
  return {
    enabled: auth?.enabled === true,
    tenantId: auth?.tenantId ?? '',
    clientId: auth?.clientId ?? '',
    apiScope: auth?.apiScope ?? '',
  };
}

const authConfig = readAuthConfig();
let msalInstance: PublicClientApplication | null = null;

function getMsalInstance(): PublicClientApplication {
  if (msalInstance !== null) {
    return msalInstance;
  }

  msalInstance = new PublicClientApplication({
    auth: {
      clientId: authConfig.clientId,
      authority: `https://login.microsoftonline.com/${authConfig.tenantId}`,
      redirectUri: window.location.origin,
    },
    cache: {
      cacheLocation: 'sessionStorage',
    },
  });

  return msalInstance;
}

function getAccount(): AccountInfo | null {
  const client = getMsalInstance();
  const active = client.getActiveAccount();
  if (active !== null) {
    return active;
  }

  const all = client.getAllAccounts();
  if (all.length === 0) {
    return null;
  }

  client.setActiveAccount(all[0]);
  return all[0];
}

export function isAuthEnabled(): boolean {
  return authConfig.enabled;
}

export async function initializeAuth(): Promise<void> {
  if (!authConfig.enabled) {
    return;
  }

  if (!authConfig.tenantId || !authConfig.clientId || !authConfig.apiScope) {
    throw new Error('Missing frontend Entra auth runtime settings in assets/env.js');
  }

  const client = getMsalInstance();
  await client.initialize();
  const redirectResult: AuthenticationResult | null = await client.handleRedirectPromise();
  if (redirectResult?.account) {
    client.setActiveAccount(redirectResult.account);
  }

  if (getAccount() === null) {
    await client.loginRedirect({ scopes: [authConfig.apiScope] });
  }
}

export async function getAccessToken(): Promise<string | undefined> {
  if (!authConfig.enabled) {
    return undefined;
  }

  const account = getAccount();
  if (account === null) {
    await getMsalInstance().loginRedirect({ scopes: [authConfig.apiScope] });
    return undefined;
  }

  try {
    const result = await getMsalInstance().acquireTokenSilent({
      account,
      scopes: [authConfig.apiScope],
    });
    return result.accessToken;
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) {
      await getMsalInstance().acquireTokenRedirect({ scopes: [authConfig.apiScope] });
      return undefined;
    }
    throw error;
  }
}



