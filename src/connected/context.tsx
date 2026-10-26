import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { api } from '../api/client';
import type { Session } from '../auth/model';
export type Terms = { amount: number; rate: number; months: number; profit: number; delay: number; purpose: string; productId?: number };
export type Product = { id: number; code: string; name: string; description: string; kind: string; min_amount: number; max_amount: number; min_term: number; max_term: number; base_rate: number };
export type Application = { id: number; company_id: number; amount: number; term_months: number; purpose: string; state: string; product_id: number; form_data: Record<string, any>; created_at: string; updated_at: string; events?: any[]; available_events?: string[]; enrichment?: any; score?: any; decision?: any; offer?: any };
export const stateNames: Record<string,string> = { DRAFT:'Черновик',SUBMITTED:'Заявка отправлена',VALIDATION:'Проверка данных',ENRICHMENT:'Обогащение',SCORING:'Скоринг',DECISIONING:'Принятие решения',OFFER:'Предложены условия',NEEDS_INFO:'Нужны сведения',MANUAL_REVIEW:'Пересмотр человеком',DECLINED:'Отказ',OFFER_ACCEPTED:'Условия приняты',SIGNING:'Подписание',DISBURSED:'Выдача',SERVICING:'Сопровождение' };
export const outcomeNames: Record<string,string> = {approve:'Одобрено',counter:'Контрпредложение',need_info:'Нужны данные',decline:'Отказ'};
export const rub = (value: number) => new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Number(value) || 0)+' ₽';
export const date = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(value+'T12:00:00').toLocaleDateString('ru-RU',{day:'numeric',month:'short'}) : new Date(value).toLocaleString('ru-RU',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
function useConveyorState(session: Session) {
  const [applications,setApplications]=useState<Application[]>([]),[products,setProducts]=useState<Product[]>([]),[company,setCompany]=useState<any>(null);
  const [selectedId,setSelectedId]=useState<number|null>(()=>Number(sessionStorage.getItem(`alfa-selected:${session.id}`))||null);
  const [detail,setDetail]=useState<Application|null>(null),[documents,setDocuments]=useState<any[]>([]),[readiness,setReadiness]=useState<any>(null),[servicing,setServicing]=useState<any>(null),[offers,setOffers]=useState<any>(null);
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[revision,setRevision]=useState(0);
  const [terms,setTerms]=useState<Terms>({amount:1000000,rate:22,months:24,profit:95000,delay:0,purpose:'Развитие бизнеса'});
  const lastSelected=useRef<number|null>(null);
  const sequence=useRef(0),mounted=useRef(true),actionLock=useRef(false);
  const isBank=session.role!=='client',isClient=session.role!=='bank',isRisk=session.serverRole==='risk_admin'||session.role==='demo';
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;sequence.current++;};},[]);
  async function refreshList() { const [list,items,comp]=await Promise.all([api.applications(),api.products(),api.company()]);if(!mounted.current)return;setApplications(list);setProducts(items);setCompany(comp);setSelectedId(current=>list.some((a:Application)=>a.id===current)?current:list[0]?.id??null); }
  useEffect(()=>{refreshList().catch(e=>setError(e.message)).finally(()=>setLoading(false));},[]);
  useEffect(()=>{
    const request=++sequence.current;if(lastSelected.current!==selectedId){setDetail(null);setServicing(null);setOffers(null);setDocuments([]);setReadiness(null);lastSelected.current=selectedId;}
    if(!selectedId)return;
    let live=true;
    const load=async()=>{try{const item=await api.application(selectedId);const [docs,ready,offer,serv]=await Promise.all([api.documents(selectedId),api.readiness(selectedId),api.offers(selectedId),item.state==='SERVICING'?api.servicing(selectedId):Promise.resolve(null)]);if(live&&request===sequence.current){setDetail(item);setDocuments(docs);setReadiness(ready);setOffers(offer);setServicing(serv);setError('');}}catch(e){if(live)setError((e as Error).message);}};
    sessionStorage.setItem(`alfa-selected:${session.id}`,String(selectedId));void load();return()=>{live=false;};
  },[selectedId,revision]);
  async function act<T>(operation:()=>Promise<T>,message='Изменения сохранены на сервере'):Promise<T|undefined>{if(actionLock.current)return;actionLock.current=true;setBusy(true);setError('');setNotice('');try{const result=await operation();await refreshList();setRevision(v=>v+1);setNotice(message);return result;}catch(e){setError((e as Error).message);return undefined;}finally{actionLock.current=false;setBusy(false);}}
  const select=(id:number)=>{setError('');setNotice('');setSelectedId(id);};
  return {session,applications,products,company,selectedId,select,detail,documents,readiness,servicing,offers,loading,busy,error,setError,notice,setNotice,revision,poll:()=>{if(!actionLock.current)void refreshList().then(()=>setRevision(v=>v+1)).catch(e=>setError(e.message));},refresh:()=>act(async()=>{},'Данные обновлены'),act,terms,setTerms,isBank,isClient,isRisk};
}
type Conveyor = ReturnType<typeof useConveyorState>;
const Context=createContext<Conveyor|null>(null);
export function ConveyorProvider({session,children}:{session:Session;children:ReactNode}){const value=useConveyorState(session);return <Context.Provider value={value}>{children}</Context.Provider>;}
export function useConveyor(){const value=useContext(Context);if(!value)throw new Error('Нет контекста кабинета');return value;}
