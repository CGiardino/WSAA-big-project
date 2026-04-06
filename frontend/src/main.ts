import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { bootstrapApplication } from '@angular/platform-browser';

import { AppComponent } from './app/app.component';
import { BASE_PATH } from './app/generated-api';
import { authInterceptor } from './app/auth.interceptor';
import { initializeAuth } from './app/auth.service';

declare global {
  interface Window {
    __WSAA_ENV__?: {
      apiBaseUrl?: string;
      auth?: {
        enabled?: boolean;
        tenantId?: string;
        clientId?: string;
        apiScope?: string;
      };
    };
  }
}

const apiBaseUrl = window.__WSAA_ENV__?.apiBaseUrl ?? '/api';

async function bootstrap(): Promise<void> {
  await initializeAuth();

  await bootstrapApplication(AppComponent, {
    // Keep local dev proxy by default and allow release-time override via assets/env.js.
    providers: [
      provideHttpClient(withInterceptors([authInterceptor])),
      { provide: BASE_PATH, useValue: apiBaseUrl },
    ],
  });
}

bootstrap().catch((err) => console.error(err));
