// Integration boundary. These adapters intentionally perform no bank requests.
export const bankGateway = {
  async refreshStatus(): Promise<{ state: 'not_connected'; estimatedNextStageAt: null }> {
    return { state: 'not_connected', estimatedNextStageAt: null };
  },
  async getProductTerms(): Promise<{ state: 'not_connected'; rate: null; fee: null }> {
    return { state: 'not_connected', rate: null, fee: null };
  },
  async sendSupportRequest(): Promise<{ state: 'not_connected'; requestId: null }> {
    return { state: 'not_connected', requestId: null };
  },
};
export type AnalyticsName = 'CALCULATOR_OPENED' | 'BENEFIT_EVALUATION_COMPLETED' | 'SUBMIT_ATTEMPTED' | 'STATUS_HELP_OPENED' | 'SURVEY_COMPLETED';
export type AnalyticsEvent = { eventId: string; name: AnalyticsName; createdAt: string; applicationId: null };
export function trackEvent(name: AnalyticsName) {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem('alfa-analytics-v1') || '[]');
    const events = Array.isArray(stored) ? stored : [];
    const event: AnalyticsEvent = { eventId: crypto.randomUUID(), name, createdAt: new Date().toISOString(), applicationId: null };
    localStorage.setItem('alfa-analytics-v1', JSON.stringify([...events, event].slice(-200)));
  } catch { /* Analytics must never interrupt the customer journey. */ }
}
export const metricPlaceholders = {
  benefitCompletionRate: null, errorFreeSubmissionRate: null, medianProcessingSeconds: null, statusSupportRequests: null,
};
