import { Injectable } from '@angular/core';
import {
  HttpEvent,
  HttpHandler,
  HttpInterceptor,
  HttpRequest
} from '@angular/common/http';
import { Observable } from 'rxjs';
import { timeout } from 'rxjs/operators';

@Injectable()
export class TimeoutInterceptor implements HttpInterceptor {
  // Avoid hung UI requests when backend hangs during long operations.
  private readonly DEFAULT_TIMEOUT = 60000; // 60 seconds

  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    // Apply the timeout consistently to every outgoing HTTP call.
    return next.handle(req).pipe(timeout(this.DEFAULT_TIMEOUT));
  }
}
