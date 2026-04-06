import { provideHttpClient } from '@angular/common/http';
import { bootstrapApplication } from '@angular/platform-browser';

import { AppComponent } from './app/app.component';
import { BASE_PATH } from './app/generated-api';

declare global {
  interface Window {
    __WSAA_ENV__?: {
      apiBaseUrl?: string;
    };
  }
}

const apiBaseUrl = window.__WSAA_ENV__?.apiBaseUrl ?? '/api';

bootstrapApplication(AppComponent, {
  // Keep local dev proxy by default and allow release-time override via assets/env.js.
  providers: [provideHttpClient(), { provide: BASE_PATH, useValue: apiBaseUrl }],
}).catch((err) => console.error(err));
