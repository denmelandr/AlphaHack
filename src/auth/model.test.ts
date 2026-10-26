import test from 'node:test';
import assert from 'node:assert/strict';
import { canAccess, homePage, signIn, signOut, readSession } from './model.ts';
const storage=new Map<string,string>();
Object.defineProperty(globalThis,'sessionStorage',{value:{getItem:(key:string)=>storage.get(key)??null,setItem:(key:string,value:string)=>storage.set(key,value),removeItem:(key:string)=>storage.delete(key)}});
test('server role gates workspaces; demo has both; bank can inspect but not use customer navigation',()=>{
  for(const page of ['bank-queue','bank-policy','bank-copilot','bank-portfolio']){assert.equal(canAccess('client',page),false);assert.ok(canAccess('bank',page));assert.ok(canAccess('demo',page));}
  for(const page of ['overview','calculator','application','products','collaboration']){assert.equal(canAccess('bank',page),false);assert.ok(canAccess('client',page));assert.ok(canAccess('demo',page));}
  for(const page of ['approval','care','tracker','documents'])assert.ok(canAccess('bank',page));
  assert.equal(canAccess('demo','unknown'),false);assert.equal(homePage('bank'),'bank-queue');
});
test('login and restored session use auth/me rather than an editable local role',async()=>{
  const calls:string[]=[];
  globalThis.fetch=async(input:any)=>{const url=String(input);calls.push(url);return new Response(JSON.stringify(url.endsWith('/auth/login')?{access_token:'test-token'}:{id:7,email:'demo@example.test',full_name:'Demo',role:'risk_admin',company_id:null}),{status:200});};
  const user=await signIn('demo@example.test','test-password');assert.equal(user.role,'bank');assert.equal(user.serverRole,'risk_admin');assert.equal((await readSession())?.id,'7');assert.ok(calls.includes('/api/auth/me'));signOut();assert.equal(await readSession(),null);
});
