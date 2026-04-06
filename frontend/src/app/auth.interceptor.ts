import { HttpInterceptorFn } from '@angular/common/http';
import { from } from 'rxjs';
import { catchError, switchMap } from 'rxjs/operators';

import { getAccessToken, isAuthEnabled } from './auth.service';

function isApiRequest(url: string): boolean {
  return url.startsWith('/api/') || url.includes('/v1/');
}

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  if (!isAuthEnabled() || !isApiRequest(request.url)) {
    return next(request);
  }

  return from(getAccessToken()).pipe(
    switchMap((token) => {
      if (!token) {
        return next(request);
      }
      return next(
        request.clone({
          setHeaders: {
            Authorization: `Bearer ${token}`,
          },
        })
      );
    }),
    catchError(() => next(request))
  );
};

