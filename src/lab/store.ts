import { useEffect, useState } from 'react';
import { baselinePolicy, cases, initialConditions, type Conditions, type Policy } from './engine';
export type Review = { id: string; caseId: string; comment: string; createdAt: string; status: 'pending' | 'reviewed'; response: string };
export type Audit = { id: string; actor: string; action: string; at: string };
export type Version = { id: string; policy: Policy; createdAt: string };
export type CareRequest = { id: string; caseId: string; action: string; parameters?: Record<string, number>; at: string };
export type LabState = { selectedId: string; conditions: Conditions; champion: Policy; versions: Version[]; reviews: Review[]; audit: Audit[]; sources: ('bank' | 'ofd' | 'accounting' | 'marketplace')[]; careRequests: CareRequest[]; tasks: Record<string, boolean>; companyApprovals: string[] };
const initial: LabState = { selectedId: cases[0].id, conditions: initialConditions(cases[0]), champion: baselinePolicy, versions: [{ id: 'v1', policy: baselinePolicy, createdAt: '2026-10-23T09:00:00Z' }], reviews: [], audit: [], sources: ['bank', 'accounting'], careRequests: [], tasks: {}, companyApprovals: [] };
export function useLabState() {
  const [state, setState] = useState<LabState>(() => { try { const stored = JSON.parse(localStorage.getItem('alfa-lab-v1') || 'null'); return stored ? { ...initial, ...stored } : initial; } catch { return initial; } });
  const [saved, setSaved] = useState(true);
  useEffect(() => { try { localStorage.setItem('alfa-lab-v1', JSON.stringify(state)); setSaved(true); } catch { setSaved(false); } }, [state]);
  const patch = (value: Partial<LabState>) => setState(previous => ({ ...previous, ...value }));
  const record = (action: string, actor: string) => ({ id: crypto.randomUUID(), action, actor, at: new Date().toISOString() });
  return { state, setState, patch, record, saved };
}
export type LabController = ReturnType<typeof useLabState>;
