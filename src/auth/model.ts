import { api, clearToken, getToken, setToken } from '../api/client.ts';
export type Session = { id: string; name: string; email: string; role: 'client' | 'bank' | 'demo'; serverRole: string; companyId: number | null };
export const clientPages = ['overview','calculator','application','tracker','documents','products','repayment','approval','cashflow','care','collaboration'];
export const bankPages = ['bank-queue','bank-policy','bank-copilot','bank-portfolio','approval','tracker','care','documents'];
export function canAccess(role: Session['role'], page: string) { return role === 'demo' ? [...clientPages,...bankPages].includes(page) : (role === 'bank' ? bankPages : clientPages).includes(page); }
export const homePage = (role: Session['role']) => role === 'bank' ? 'bank-queue' : 'overview';
function toSession(user: any): Session { return { id: String(user.id), name: user.full_name, email: user.email, role: user.role === 'demo' ? 'demo' : ['underwriter','risk_admin'].includes(user.role) ? 'bank' : 'client', serverRole: user.role, companyId: user.company_id }; }
export async function readSession(): Promise<Session | null> { if (!getToken()) return null; return toSession(await api.me()); }
export function signOut() { clearToken(); }
async function authenticate(result: { access_token: string }) { setToken(result.access_token); try { return toSession(await api.me()); } catch (error) { clearToken(); throw error; } }
export async function register(input: { name: string; email: string; password: string; role: 'client'|'bank'; invitation: string; company?: string; inn?: string }): Promise<Session> {
  return authenticate(await api.register({ full_name: input.name, email: input.email.trim().toLowerCase(), password: input.password, account_type: input.role, invitation: input.invitation, company_name: input.company, inn: input.inn }));
}
export async function signIn(email: string, password: string): Promise<Session> { return authenticate(await api.login(email.trim().toLowerCase(), password)); }
