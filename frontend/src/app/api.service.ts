// Thin facade around generated OpenAPI Angular services.
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import {
  ApplicantCreate,
  ApplicantCreateResponse,
  ApplicantListResponse,
  ApplicantResponse,
  ApplicantUpdate,
  ApplicantsService,
  EvaluationsService,
  RiskEvaluationRequest,
  RiskEvaluationResponse,
  Sex,
  SmokerStatus,
  StatisticsPlotsResponse,
  StatisticsService,
  StatisticsSummaryResponse,
  TrainingRunRequest,
  TrainingRunResponse,
  TrainingDatasetListResponse,
  TrainingDatasetRow,
  TrainingService,
  TrainingStatusResponse,
} from './generated-api';

export type ApplicantPayload = ApplicantCreate;
export type ApplicantUpdatePayload = ApplicantUpdate;
export type Applicant = ApplicantResponse;
export type ApplicantCreateResult = ApplicantCreateResponse;
export type ApplicantList = ApplicantListResponse;
export type TrainingDatasetList = TrainingDatasetListResponse;
export type TrainingDatasetItem = TrainingDatasetRow;
export type StatisticsSummary = StatisticsSummaryResponse;
export type StatisticsPlots = StatisticsPlotsResponse;
export { Sex, SmokerStatus };
export type { RiskEvaluationRequest, RiskEvaluationResponse, TrainingRunRequest, TrainingRunResponse, TrainingStatusResponse };

@Injectable({ providedIn: 'root' })
export class ApiService {
  // Keep the component layer independent from generated client naming.
  constructor(
    // Wrap generated SDK services so UI code imports one stable facade.
    private readonly applicantsApi: ApplicantsService,
    private readonly evaluationsApi: EvaluationsService,
    private readonly statisticsApi: StatisticsService,
    private readonly trainingApi: TrainingService
  ) {}

  listApplicants(limit: number, offset: number): Observable<ApplicantList> {
    return this.applicantsApi.listApplicants(limit, offset);
  }

  getApplicantById(applicantId: number): Observable<Applicant> {
    return this.applicantsApi.getApplicant(applicantId);
  }

  createApplicant(payload: ApplicantPayload): Observable<ApplicantCreateResult> {
    return this.applicantsApi.createApplicant(payload);
  }

  updateApplicant(applicantId: number, payload: ApplicantUpdatePayload): Observable<Applicant> {
    return this.applicantsApi.updateApplicant(applicantId, payload);
  }

  deleteApplicant(applicantId: number): Observable<void> {
    return this.applicantsApi.deleteApplicant(applicantId);
  }

  evaluateRisk(payload: RiskEvaluationRequest): Observable<RiskEvaluationResponse> {
    return this.evaluationsApi.createRiskEvaluation(payload);
  }

  runTraining(payload: TrainingRunRequest): Observable<TrainingRunResponse> {
    return this.trainingApi.runTraining(payload);
  }

  getTrainingStatus(): Observable<TrainingStatusResponse> {
    return this.trainingApi.getTrainingStatus();
  }

  listTrainingDataset(limit: number, offset: number): Observable<TrainingDatasetList> {
    return this.trainingApi.listTrainingDataset(limit, offset);
  }

  getStatisticsSummary(): Observable<StatisticsSummary> {
    return this.statisticsApi.getStatisticsSummary();
  }

  listStatisticsPlots(): Observable<StatisticsPlots> {
    return this.statisticsApi.listStatisticsPlots();
  }
}
