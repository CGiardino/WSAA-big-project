import { provideHttpClient } from '@angular/common/http';
import { bootstrapApplication } from '@angular/platform-browser';

import { AppComponent } from './app/app.component';
import { BASE_PATH } from './app/generated-api';

bootstrapApplication(AppComponent, {
  // Route generated API client calls through Angular dev proxy (/api -> backend).
  providers: [provideHttpClient(), { provide: BASE_PATH, useValue: '/api' }],
}).catch((err) => console.error(err));
