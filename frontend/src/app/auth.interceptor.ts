import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { from, throwError } from 'rxjs';
import { catchError, switchMap } from 'rxjs/operators';

import { getAccessToken, isAuthEnabled } from './auth.service';

function isApiRequest(url: string): boolean {
  return url.startsWith('/api/') || url.includes('/v1/');
}

function authFailure(url: string, detail: string): HttpErrorResponse {
  return new HttpErrorResponse({
    status: 401,
    statusText: 'Unauthorized',
    url,
    error: { detail },
  });
}

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  if (!isAuthEnabled() || !isApiRequest(request.url)) {
    return next(request);
  }

  return from(getAccessToken()).pipe(
    catchError(() => throwError(() => authFailure(request.url, 'Failed to acquire access token'))),
    switchMap((token) => {
      if (!token) {
        return throwError(() => authFailure(request.url, 'Missing access token'));
      }
      return next(
        request.clone({
          setHeaders: {
            Authorization: `Bearer ${token}`,
          },
        })
      );
    })
  );
};

