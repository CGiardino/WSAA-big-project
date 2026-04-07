// Main UI container for evaluation, applicants, statistics, and training flows.
import { CommonModule } from '@angular/common';
import { Component, HostListener, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { HTTP_INTERCEPTORS } from '@angular/common/http';

import {
  ApiService,
  Applicant,
  ApplicantCreateResult,
  ApplicantList,
  ApplicantPayload,
  ApplicantUpdatePayload,
  RiskEvaluationRequest,
  RiskEvaluationResponse,
  Sex,
  SmokerStatus,
  StatisticsPlots,
  StatisticsSummary,
  TrainingDatasetItem,
  TrainingDatasetList,
  TrainingStatusResponse,
} from './api.service';
import { TimeoutInterceptor } from './timeout.interceptor';

type UnitSystem = 'metric' | 'imperial';
type AppTab = 'evaluation' | 'applicants' | 'statistics' | 'training';

interface EvaluationInput {
  age: number;
  sex: Sex;
  height: number;
  weight: number;
  unitSystem: UnitSystem;
  children: number;
  smoker: SmokerStatus;
}

interface ApplicantInput {
  age: number;
  sex: Sex;
  height: number;
  weight: number;
  unitSystem: UnitSystem;
  children: number;
  smoker: SmokerStatus;
}

interface ApplicantEditInput {
  age: number;
  sex: Sex;
  bmi: number;
  children: number;
  smoker: SmokerStatus;
}

interface ClassificationReportRow {
  label: string;
  precision: string;
  recall: string;
  f1Score: string;
  support: string;
}

type ApplicantSortKey = 'id' | 'age' | 'sex' | 'bmi' | 'children' | 'smoker' | 'risk';
type SortDirection = 'asc' | 'desc';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
  providers: [
    {
      provide: HTTP_INTERCEPTORS,
      useClass: TimeoutInterceptor,
      multi: true,
    },
  ],
})
export class AppComponent implements OnInit, OnDestroy {
  // Shared UI state for all tabs lives here to keep cross-tab behavior predictable.
  title = 'Health Insurance Risk Classifier';
  // Friendly labels for plot files returned by backend statistics endpoint.
  private readonly statisticsPlotLabels: Record<string, string> = {
    '01_age_distribution.png': 'Age Distribution',
    '02_bmi_distribution.png': 'BMI Distribution',
    '03_charges_distribution.png': 'Charges Distribution',
    '04_smoker_analysis.png': 'Smoker Analysis',
    '05_sex_analysis.png': 'Sex Analysis',
    '07_children_analysis.png': 'Children Analysis',
    '08_risk_category_distribution.png': 'Risk Category Distribution',
    '09_correlation_matrix.png': 'Correlation Matrix',
    '10_confusion_matrix.png': 'Confusion Matrix',
    '11_per_risk_performance.png': 'Performance by Risk Category',
  };

  activeTab: AppTab = 'evaluation';
  tabsExpanded = false;

  // Applicants tab state (table, paging, search, and edit workflow).
  applicants: Applicant[] = [];
  readonly applicantPageSize = 25;
  applicantTotal = 0;
  applicantOffset = 0;
  hasMoreApplicants = true;
  applicantsLoading = false;
  applicantError = '';
  applicantSortKey: ApplicantSortKey = 'id';
  applicantSortDirection: SortDirection = 'desc';
  applicantSearchIdInput: number | null = null;
  applicantSearchId: number | null = null;
  applicantSearchActive = false;
  applicantSearching = false;
  applicantCreating = false;
  latestApplicantCreateResult: ApplicantCreateResult | null = null;
  highlightedApplicantId: number | null = null;
  editingApplicantId: number | null = null;
  savingApplicantId: number | null = null;
  applicantEditInput: ApplicantEditInput | null = null;
  expandedApplicantIds = new Set<number>();
  private applicantHighlightTimeout: ReturnType<typeof setTimeout> | null = null;
  applicantInput: ApplicantInput = {
    age: 42,
    sex: Sex.Male,
    height: 175,
    weight: 85,
    unitSystem: 'metric',
    children: 2,
    smoker: SmokerStatus.No,
  };

  evaluationError = '';
  evaluationResult: RiskEvaluationResponse | null = null;
  evaluationHighlighted = false;
  evaluationCreating = false;
  private evaluationHighlightTimeout: ReturnType<typeof setTimeout> | null = null;
  evaluationInput: EvaluationInput = {
    age: 42,
    sex: Sex.Male,
    height: 175,
    weight: 85,
    unitSystem: 'metric',
    children: 2,
    smoker: SmokerStatus.No,
  };

  trainingError = '';
  isTraining = false;
  trainingStatus: TrainingStatusResponse | null = null;
  classificationReportRows: ClassificationReportRow[] = [];
  trainingDataset: TrainingDatasetItem[] = [];
  trainingDatasetError = '';
  trainingDatasetLoading = false;
  trainingDatasetHasMore = true;
  trainingDatasetTotal = 0;
  trainingDatasetOffset = 0;
  readonly trainingDatasetPageSize = 25;

  statisticsError = '';
  statisticsLoading = false;
  statisticsSummary: StatisticsSummary | null = null;
  statisticsPlots: StatisticsPlots['items'] = [];
  statisticsPlotObjectUrls: Record<string, string> = {};
  statisticsPlotLoadErrors: Record<string, string> = {};
  statisticsPlotLoading: Record<string, boolean> = {};
  selectedPlotFileName: string | null = null;
  selectedPlotName: string | null = null;
  selectedPlotUrl: string | null = null;
  selectedPlotError = '';

  get trainingInProgress(): boolean {
    // Combine optimistic local flag with latest server status.
    return this.isTraining || this.trainingStatus?.status === 'running';
  }

  constructor(private readonly api: ApiService) {}

  ngOnInit(): void {
    // Prime initial datasets and keep selected tab aligned with URL hash.
    this.loadApplicants();
    this.refreshTrainingStatus();
    this.syncTabWithHash();
  }

  ngOnDestroy(): void {
    this.revokeAllPlotObjectUrls();
  }

  setActiveTab(tab: AppTab, syncHash = true): void {
    this.activeTab = tab;
    this.tabsExpanded = false;
    if (syncHash) {
      this.updateHashForTab(tab);
    }
    if (tab === 'statistics' && this.statisticsSummary === null && !this.statisticsLoading) {
      // Lazy-load statistics only when the tab is first opened.
      this.loadStatistics();
    }
    if (tab === 'training' && this.trainingDataset.length === 0) {
      // Lazy-load training dataset to avoid extra startup API calls.
      this.loadTrainingDataset();
    }
  }

  toggleTabs(): void {
    this.tabsExpanded = !this.tabsExpanded;
  }

  @HostListener('window:hashchange')
  onHashChange(): void {
    this.syncTabWithHash();
  }

  private syncTabWithHash(): void {
    const tabFromHash = this.getTabFromHash(window.location.hash);
    if (tabFromHash !== null) {
      if (tabFromHash !== this.activeTab) {
        this.setActiveTab(tabFromHash, false);
      }
      return;
    }
    this.updateHashForTab(this.activeTab);
  }

  private getTabFromHash(hashValue: string): AppTab | null {
    const normalized = hashValue.replace(/^#/, '').trim().toLowerCase();
    if (normalized === 'evaluation' || normalized === 'applicants' || normalized === 'statistics' || normalized === 'training') {
      return normalized;
    }
    return null;
  }

  private updateHashForTab(tab: AppTab): void {
    const nextHash = `#${tab}`;
    if (window.location.hash !== nextHash) {
      // Keep browser URL in sync without introducing router dependency.
      window.location.hash = nextHash;
    }
  }

  loadStatistics(): void {
    this.statisticsLoading = true;
    this.statisticsError = '';

    forkJoin({
      summary: this.api.getStatisticsSummary(),
      plots: this.api.listStatisticsPlots(),
    }).subscribe({
      next: (result) => {
        this.statisticsSummary = result.summary;
        this.statisticsPlots = result.plots.items;
        this.reconcileStatisticsPlotCache();
        this.preloadStatisticsPlots();
        this.statisticsLoading = false;
      },
      error: (err) => {
        this.statisticsError = err?.error?.detail ?? 'Failed to load statistics';
        this.statisticsLoading = false;
      },
    });
  }

  getPlotImageUrl(plotName: string): string | null {
    return this.statisticsPlotObjectUrls[plotName] ?? null;
  }

  hasPlotLoadError(plotName: string): boolean {
    return this.statisticsPlotLoadErrors[plotName] !== undefined;
  }

  getPlotLabel(plotName: string): string {
    const directLabel = this.statisticsPlotLabels[plotName];
    if (directLabel !== undefined) {
      return directLabel;
    }

    // Fallback: derive a readable label from the file name.
    const withoutExtension = plotName.replace(/\.[^/.]+$/, '');
    const withoutPrefix = withoutExtension.replace(/^\d+_/, '');
    return withoutPrefix
      .split(/[_-]+/)
      .filter((part) => part.length > 0)
      .map((part) => part[0].toUpperCase() + part.slice(1))
      .join(' ');
  }

  openPlotModal(plot: StatisticsPlots['items'][number]): void {
    this.selectedPlotFileName = plot.name;
    this.selectedPlotName = this.getPlotLabel(plot.name);
    this.selectedPlotError = '';
    this.selectedPlotUrl = this.getPlotImageUrl(plot.name);
    if (this.selectedPlotUrl === null) {
      this.fetchPlotImage(plot.name, true);
    }
  }

  closePlotModal(): void {
    this.selectedPlotFileName = null;
    this.selectedPlotName = null;
    this.selectedPlotUrl = null;
    this.selectedPlotError = '';
  }

  onPlotBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.closePlotModal();
    }
  }

  @HostListener('document:keydown.escape')
  onEscapeKey(): void {
    if (this.selectedPlotName !== null) {
      this.closePlotModal();
    }
  }

  private preloadStatisticsPlots(): void {
    for (const plot of this.statisticsPlots) {
      if (this.statisticsPlotObjectUrls[plot.name] !== undefined) {
        continue;
      }
      this.fetchPlotImage(plot.name);
    }
  }

  private fetchPlotImage(plotName: string, updateModal = false): void {
    if (this.statisticsPlotLoading[plotName] === true) {
      return;
    }

    this.statisticsPlotLoading[plotName] = true;
    delete this.statisticsPlotLoadErrors[plotName];

    this.api.getStatisticsPlot(plotName).subscribe({
      next: (blob) => {
        const currentUrl = this.statisticsPlotObjectUrls[plotName];
        if (currentUrl !== undefined) {
          URL.revokeObjectURL(currentUrl);
        }
        const objectUrl = URL.createObjectURL(blob);
        this.statisticsPlotObjectUrls[plotName] = objectUrl;
        delete this.statisticsPlotLoading[plotName];

        if (updateModal && this.selectedPlotFileName === plotName) {
          this.selectedPlotUrl = objectUrl;
          this.selectedPlotError = '';
        }
      },
      error: (err) => {
        this.statisticsPlotLoadErrors[plotName] = err?.error?.detail ?? 'Failed to load plot image';
        delete this.statisticsPlotLoading[plotName];
        if (updateModal && this.selectedPlotFileName === plotName) {
          this.selectedPlotError = this.statisticsPlotLoadErrors[plotName];
        }
      },
    });
  }

  private reconcileStatisticsPlotCache(): void {
    const activePlotNames = new Set(this.statisticsPlots.map((plot) => plot.name));
    for (const plotName of Object.keys(this.statisticsPlotObjectUrls)) {
      if (!activePlotNames.has(plotName)) {
        URL.revokeObjectURL(this.statisticsPlotObjectUrls[plotName]);
        delete this.statisticsPlotObjectUrls[plotName];
      }
    }
    for (const plotName of Object.keys(this.statisticsPlotLoadErrors)) {
      if (!activePlotNames.has(plotName)) {
        delete this.statisticsPlotLoadErrors[plotName];
      }
    }
    for (const plotName of Object.keys(this.statisticsPlotLoading)) {
      if (!activePlotNames.has(plotName)) {
        delete this.statisticsPlotLoading[plotName];
      }
    }
  }

  private revokeAllPlotObjectUrls(): void {
    for (const objectUrl of Object.values(this.statisticsPlotObjectUrls)) {
      URL.revokeObjectURL(objectUrl);
    }
    this.statisticsPlotObjectUrls = {};
  }

  loadApplicants(): void {
    this.applicantSearchActive = false;
    this.applicantSearchId = null;
    this.applicantSearchIdInput = null;
    this.applicantSearching = false;
    this.applicants = [];
    this.applicantTotal = 0;
    this.applicantOffset = 0;
    this.hasMoreApplicants = true;
    this.expandedApplicantIds.clear();
    this.applicantError = '';
    this.loadNextApplicantsPage();
  }

  searchApplicantById(): void {
    if (this.applicantSearchIdInput === null || this.applicantSearchIdInput === undefined) {
      this.clearApplicantSearch();
      return;
    }
    const normalizedId = Number(this.applicantSearchIdInput);
    if (!Number.isInteger(normalizedId) || normalizedId <= 0) {
      this.applicantError = 'Enter a valid applicant ID';
      return;
    }
    this.applicantSearchActive = true;
    this.applicantSearchId = normalizedId;
    this.applicantSearching = true;
    this.applicantError = '';

    this.api.getApplicantById(normalizedId).subscribe({
      next: (applicant) => {
        this.applicants = [applicant];
        this.syncExpandedApplicantIds();
        this.applicantTotal = 1;
        this.applicantOffset = 1;
        this.hasMoreApplicants = false;
        this.applicantSearching = false;
      },
      error: (err) => {
        this.applicants = [];
        this.syncExpandedApplicantIds();
        this.applicantTotal = 0;
        this.applicantOffset = 0;
        this.hasMoreApplicants = false;
        this.applicantError = err?.status === 404 ? 'Applicant not found' : err?.error?.detail ?? 'Failed to search applicant';
        this.applicantSearching = false;
      },
    });
  }

  clearApplicantSearch(): void {
    this.loadApplicants();
  }

  loadNextApplicantsPage(): void {
    if (!this.hasMoreApplicants || this.applicantsLoading) {
      return;
    }

    this.applicantsLoading = true;
    this.api.listApplicants(this.applicantPageSize, this.applicantOffset).subscribe({
      next: (page: ApplicantList) => {
        this.applicants = [...this.applicants, ...page.items];
        this.syncExpandedApplicantIds();
        this.applicantTotal = page.total;
        this.applicantOffset = page.offset + page.items.length;
        this.hasMoreApplicants = page.has_more;
        this.applicantError = '';
        this.applicantsLoading = false;
      },
      error: (err) => {
        this.applicantError = err?.error?.detail ?? 'Failed to load applicants';
        this.applicantsLoading = false;
      },
    });
  }

  onApplicantsScroll(event: Event): void {
    if (!this.hasMoreApplicants || this.applicantsLoading) {
      return;
    }

    const container = event.target as HTMLElement;
    const distanceToBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    if (distanceToBottom <= 120) {
      this.loadNextApplicantsPage();
    }
  }

  setApplicantSort(key: ApplicantSortKey): void {
    if (this.applicantSortKey === key) {
      this.applicantSortDirection = this.applicantSortDirection === 'asc' ? 'desc' : 'asc';
      return;
    }
    this.applicantSortKey = key;
    this.applicantSortDirection = 'asc';
  }

  getApplicantSortIndicator(key: ApplicantSortKey): string {
    if (this.applicantSortKey !== key) {
      return '';
    }
    return this.applicantSortDirection === 'asc' ? '\u2191' : '\u2193';
  }

  getApplicantSortAriaSort(key: ApplicantSortKey): 'ascending' | 'descending' | 'none' {
    if (this.applicantSortKey !== key) {
      return 'none';
    }
    return this.applicantSortDirection === 'asc' ? 'ascending' : 'descending';
  }

  get sortedApplicants(): Applicant[] {
    const direction = this.applicantSortDirection === 'asc' ? 1 : -1;
    const sorted = [...this.applicants];
    sorted.sort((left, right) => {
      const result = this.compareApplicantsByKey(left, right, this.applicantSortKey);
      if (result !== 0) {
        return result * direction;
      }
      return (left.id - right.id) * direction;
    });
    return sorted;
  }

  private compareApplicantsByKey(left: Applicant, right: Applicant, key: ApplicantSortKey): number {
    switch (key) {
      case 'id':
        return left.id - right.id;
      case 'age':
        return left.age - right.age;
      case 'bmi':
        return left.bmi - right.bmi;
      case 'children':
        return left.children - right.children;
      case 'sex':
        return left.sex.localeCompare(right.sex);
      case 'smoker':
        return left.smoker.localeCompare(right.smoker);
      case 'risk':
        return this.getRiskSortValue(left.evaluation?.risk_category) - this.getRiskSortValue(right.evaluation?.risk_category);
      default:
        return 0;
    }
  }

  private getRiskSortValue(riskCategory: string | null | undefined): number {
    if (riskCategory === null || riskCategory === undefined) {
      return Number.MAX_SAFE_INTEGER;
    }
    const normalized = riskCategory.trim().toLowerCase();
    if (normalized === 'low') {
      return 0;
    }
    if (normalized === 'medium') {
      return 1;
    }
    if (normalized === 'high') {
      return 2;
    }
    return 3;
  }

  submitApplicant(): void {
    this.applicantError = '';
    this.applicantCreating = true;
    const payload = this.buildApplicantPayload();
    if (payload === null) {
      this.applicantCreating = false;
      return;
    }

    this.api.createApplicant(payload).subscribe({
      next: (result) => {
        this.latestApplicantCreateResult = result;
        this.applicants = [
          result.applicant,
          ...this.applicants.filter((applicant) => applicant.id !== result.applicant.id),
        ];
        this.applicantTotal = Math.max(this.applicantTotal + 1, this.applicants.length);
        this.highlightNewApplicant(result.applicant.id);
        this.applicantCreating = false;
      },
      error: (err) => {
        this.applicantError = err?.error?.detail ?? 'Failed to create applicant';
        this.latestApplicantCreateResult = null;
        this.applicantCreating = false;
      },
    });
  }

  private highlightNewApplicant(applicantId: number): void {
    this.highlightedApplicantId = applicantId;
    if (this.applicantHighlightTimeout !== null) {
      clearTimeout(this.applicantHighlightTimeout);
    }
    this.applicantHighlightTimeout = setTimeout(() => {
      this.highlightedApplicantId = null;
      this.applicantHighlightTimeout = null;
    }, 3000);
  }

  // Modal state for delete confirmation
  showDeleteModal = false;
  deleteApplicantId: number | null = null;

  removeApplicant(applicantId: number): void {
    this.deleteApplicantId = applicantId;
    this.showDeleteModal = true;
  }

  confirmDeleteApplicant(): void {
    if (this.deleteApplicantId == null) return;
    this.api.deleteApplicant(this.deleteApplicantId).subscribe({
      next: () => this.loadApplicants(),
      error: (err) => {
        this.applicantError = err?.error?.detail ?? 'Failed to delete applicant';
      },
      complete: () => {
        this.showDeleteModal = false;
        this.deleteApplicantId = null;
      }
    });
  }

  cancelDeleteApplicant(): void {
    this.showDeleteModal = false;
    this.deleteApplicantId = null;
  }

  startEditApplicant(applicant: Applicant): void {
    this.applicantError = '';
    this.editingApplicantId = applicant.id;
    this.expandedApplicantIds.add(applicant.id);
    this.applicantEditInput = {
      age: applicant.age,
      sex: applicant.sex,
      bmi: applicant.bmi,
      children: applicant.children,
      smoker: applicant.smoker,
    };
  }

  isApplicantExpanded(applicantId: number): boolean {
    return this.expandedApplicantIds.has(applicantId);
  }

  toggleApplicantExpanded(applicantId: number): void {
    if (this.expandedApplicantIds.has(applicantId)) {
      this.expandedApplicantIds.delete(applicantId);
      return;
    }
    this.expandedApplicantIds.add(applicantId);
  }

  private syncExpandedApplicantIds(): void {
    const visibleIds = new Set(this.applicants.map((applicant) => applicant.id));
    this.expandedApplicantIds.forEach((applicantId) => {
      if (!visibleIds.has(applicantId)) {
        this.expandedApplicantIds.delete(applicantId);
      }
    });
  }

  cancelEditApplicant(): void {
    this.editingApplicantId = null;
    this.savingApplicantId = null;
    this.applicantEditInput = null;
  }

  saveApplicantUpdate(applicantId: number): void {
    if (this.applicantEditInput === null) {
      return;
    }

    const payload: ApplicantUpdatePayload = {
      age: Number(this.applicantEditInput.age),
      sex: this.applicantEditInput.sex,
      bmi: Number(this.applicantEditInput.bmi),
      children: Number(this.applicantEditInput.children),
      smoker: this.applicantEditInput.smoker,
    };

    this.applicantError = '';
    this.savingApplicantId = applicantId;
    this.api.updateApplicant(applicantId, payload).subscribe({
      next: (updated) => {
        this.applicants = this.applicants.map((applicant) =>
          applicant.id === updated.id ? updated : applicant
        );
        this.savingApplicantId = null;
        this.cancelEditApplicant();
      },
      error: (err) => {
        this.applicantError = err?.error?.detail ?? 'Failed to update applicant';
        this.savingApplicantId = null;
      },
    });
  }

  submitEvaluation(): void {
    this.evaluationError = '';
    this.evaluationResult = null;
    this.evaluationCreating = true;
    const payload = this.buildEvaluationPayload();
    if (payload === null) {
      this.evaluationCreating = false;
      return;
    }

    this.api.evaluateRisk(payload).subscribe({
      next: (result) => {
        this.evaluationResult = result;
        this.evaluationError = '';
        this.highlightEvaluationResult();
        this.evaluationCreating = false;
      },
      error: (err) => {
        this.evaluationError = err?.error?.detail ?? 'Failed to evaluate risk';
        this.evaluationCreating = false;
      },
    });
  }

  private highlightEvaluationResult(): void {
    this.evaluationHighlighted = true;
    if (this.evaluationHighlightTimeout !== null) {
      clearTimeout(this.evaluationHighlightTimeout);
    }
    this.evaluationHighlightTimeout = setTimeout(() => {
      this.evaluationHighlighted = false;
      this.evaluationHighlightTimeout = null;
    }, 3000);
  }

  private buildEvaluationPayload(): RiskEvaluationRequest | null {
    const bmi = this.calculateBmi(
      this.evaluationInput.height,
      this.evaluationInput.weight,
      this.evaluationInput.unitSystem
    );
    if (bmi === null) {
      this.evaluationError = 'Enter a valid height and weight';
      return null;
    }

    return {
      age: this.evaluationInput.age,
      sex: this.evaluationInput.sex,
      bmi,
      children: this.evaluationInput.children,
      smoker: this.evaluationInput.smoker,
    };
  }

  private buildApplicantPayload(): ApplicantPayload | null {
    const bmi = this.calculateBmi(
      this.applicantInput.height,
      this.applicantInput.weight,
      this.applicantInput.unitSystem
    );
    if (bmi === null) {
      this.applicantError = 'Enter a valid height and weight';
      return null;
    }

    return {
      age: this.applicantInput.age,
      sex: this.applicantInput.sex,
      bmi,
      children: this.applicantInput.children,
      smoker: this.applicantInput.smoker,
    };
  }

  private calculateBmi(height: number, weight: number, unitSystem: UnitSystem): number | null {
    const normalizedHeight = Number(height);
    const normalizedWeight = Number(weight);

    if (!Number.isFinite(normalizedHeight) || !Number.isFinite(normalizedWeight)) {
      return null;
    }
    if (normalizedHeight <= 0 || normalizedWeight <= 0) {
      return null;
    }

    let bmi = 0;
    if (unitSystem === 'metric') {
      const heightMeters = normalizedHeight / 100;
      if (heightMeters <= 0) {
        return null;
      }
      bmi = normalizedWeight / (heightMeters * heightMeters);
    } else {
      bmi = (703 * normalizedWeight) / (normalizedHeight * normalizedHeight);
    }

    if (!Number.isFinite(bmi)) {
      return null;
    }
    return Math.round(bmi * 10) / 10;
  }

  runTraining(): void {
    if (this.trainingInProgress) {
      return;
    }

    this.isTraining = true;
    this.trainingError = '';

    this.api.runTraining({ epochs: 200 }).subscribe({
      next: (result) => {
        this.trainingStatus = {
          run_id: result.run_id,
          status: result.status,
          epochs: result.epochs,
          model_version: result.model_version,
          started_at: result.started_at,
          finished_at: result.finished_at,
          last_error: null,
          classification_report: result.classification_report,
        };
        this.classificationReportRows = this.parseClassificationReportRows(result.classification_report);
        this.trainingError = '';
        this.isTraining = false;
        this.loadTrainingDataset();
      },
      error: (err) => {
        this.trainingError = err?.error?.detail ?? 'Training failed';
        this.isTraining = false;
      },
    });
  }

  refreshTrainingStatus(): void {
    this.api.getTrainingStatus().subscribe({
      next: (status) => {
        this.trainingStatus = status;
        this.classificationReportRows = this.parseClassificationReportRows(status.classification_report);
        this.isTraining = status.status === 'running';
        this.trainingError = '';
      },
      error: (err) => {
        this.trainingError = err?.error?.detail ?? 'Failed to get training status';
      },
    });
  }

  refreshTrainingPanel(): void {
    this.refreshTrainingStatus();
    this.loadTrainingDataset();
  }

  private parseClassificationReportRows(report: string | null | undefined): ClassificationReportRow[] {
    if (report === null || report === undefined || report.trim().length === 0) {
      return [];
    }

    const rows: ClassificationReportRow[] = [];
    const lines = report
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.length > 0);

    for (const line of lines) {
      if (line.startsWith('precision') || line.toLowerCase().startsWith('overall accuracy')) {
        continue;
      }

      const fullMetricsMatch = line.match(/^(.+?)\s+([0-9]*\.?[0-9]+)\s+([0-9]*\.?[0-9]+)\s+([0-9]*\.?[0-9]+)\s+([0-9]+)$/);
      if (fullMetricsMatch !== null) {
        rows.push({
          label: fullMetricsMatch[1].trim(),
          precision: fullMetricsMatch[2],
          recall: fullMetricsMatch[3],
          f1Score: fullMetricsMatch[4],
          support: fullMetricsMatch[5],
        });
        continue;
      }

      const accuracyMatch = line.match(/^(accuracy)\s+([0-9]*\.?[0-9]+)\s+([0-9]+)$/i);
      if (accuracyMatch !== null) {
        rows.push({
          label: accuracyMatch[1],
          precision: '-',
          recall: '-',
          f1Score: accuracyMatch[2],
          support: accuracyMatch[3],
        });
      }
    }

    return rows;
  }


  loadTrainingDataset(): void {
    this.trainingDataset = [];
    this.trainingDatasetError = '';
    this.trainingDatasetLoading = false;
    this.trainingDatasetHasMore = true;
    this.trainingDatasetTotal = 0;
    this.trainingDatasetOffset = 0;
    this.loadNextTrainingDatasetPage();
  }

  loadNextTrainingDatasetPage(): void {
    if (!this.trainingDatasetHasMore || this.trainingDatasetLoading) {
      return;
    }

    this.trainingDatasetLoading = true;
    this.api
      .listTrainingDataset(this.trainingDatasetPageSize, this.trainingDatasetOffset)
      .subscribe({
        next: (page: TrainingDatasetList) => {
          this.trainingDataset = [...this.trainingDataset, ...page.items];
          this.trainingDatasetTotal = page.total;
          this.trainingDatasetOffset = page.offset + page.items.length;
          this.trainingDatasetHasMore = page.has_more;
          this.trainingDatasetError = '';
          this.trainingDatasetLoading = false;
        },
        error: (err) => {
          this.trainingDatasetError = err?.error?.detail ?? 'Failed to load training dataset';
          this.trainingDatasetLoading = false;
        },
      });
  }

  onTrainingDatasetScroll(event: Event): void {
    if (!this.trainingDatasetHasMore || this.trainingDatasetLoading) {
      return;
    }

    const container = event.target as HTMLElement;
    const distanceToBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    if (distanceToBottom <= 120) {
      this.loadNextTrainingDatasetPage();
    }
  }

  selectAllOnFocus(event: FocusEvent): void {
    const target = event.target;
    if (target instanceof HTMLInputElement) {
      target.select();
    }
  }

  // Prevent non-integer input in number fields (e, +, -, .)
  blockNonIntegerInput(event: KeyboardEvent): void {
    const invalidKeys = ['e', 'E', '+', '-', '.'];
    if (invalidKeys.includes(event.key)) {
      event.preventDefault();
    }
  }
}
