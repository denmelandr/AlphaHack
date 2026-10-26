"""Integration regressions against PostgreSQL; every test rolls back its changes."""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.core.db import engine, get_db

@pytest.fixture
def client():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()
    session.close()
    transaction.rollback()
    connection.close()

def auth(client, email="demo@alfa.ru", password="demo123"):
    response = client.post('/auth/login', json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()['access_token']}

def get_apps(client, headers):
    response = client.get('/applications', headers=headers)
    assert response.status_code == 200
    return response.json()

def test_auth_and_company_isolation(client):
    assert client.get('/applications').status_code == 401
    h = auth(client, 'client@demo.ru', 'client123')
    apps = get_apps(client, h)
    assert apps and all(a['company_name'] == 'ООО "Ромашка"' for a in apps)
    other = next(a for a in get_apps(client, auth(client)) if a['company_name'] != 'ООО "Ромашка"')
    assert client.get(f"/applications/{other['id']}", headers=h).status_code == 403
    assert client.get('/policies', headers=h).status_code == 403

def test_registration_cannot_assign_bank_without_invitation(client):
    token = uuid.uuid4().hex
    body = dict(email=f"test-{token}@example.com", password='test-password-2026', full_name='Тест', account_type='bank', invitation='ALFA-DEMO-BANK')
    assert client.post('/auth/register', json=body).status_code == 403
    body.update(account_type='client', company_name='Тестовая компания', inn='9912345678')
    response = client.post('/auth/register', json=body)
    assert response.status_code == 201, response.text
    h = {'Authorization': 'Bearer '+response.json()['access_token']}
    assert client.get('/auth/me', headers=h).json()['role'] == 'owner'
    assert client.get('/applications', headers=h).json() == []
    assert client.post('/policies/1/activate', headers=h).status_code == 403

def test_draft_documents_pipeline_and_resume(client):
    h = auth(client)
    response = client.post('/applications', headers=h, json=dict(product_id=1, amount=500000, term_months=12, purpose='Закупка товара', form_data={'wizard_step': 2}))
    assert response.status_code == 201, response.text
    aid = response.json()['id']
    assert client.get(f'/applications/{aid}', headers=h).json()['form_data']['wizard_step'] == 2
    assert client.get(f'/applications/{aid}/readiness', headers=h).json()['ready'] is False
    for dtype in ['passport','financials','bank_statements']:
        assert client.post(f'/applications/{aid}/documents', headers=h, json={'doc_type':dtype,'filename':dtype+'.pdf'}).status_code == 200
    assert client.get(f'/applications/{aid}/readiness', headers=h).json()['ready'] is True
    response = client.post(f'/applications/{aid}/submit', headers=h)
    assert response.status_code == 200, response.text
    assert response.json()['state'] in ['OFFER','NEEDS_INFO','DECLINED']
    assert response.json()['events']

def test_what_if_validation_and_saved_conditions(client):
    h = auth(client)
    a = next(a for a in get_apps(client,h) if 'Ромашка' in a['company_name'])
    url=f"/applications/{a['id']}"
    assert client.post(url+'/simulate', headers=h, json={'amount':-100,'term_months':-1}).status_code == 422
    terms={'amount':1000000,'term_months':24,'collateral_offered':True,'guarantor_offered':True}
    preview=client.post(url+'/simulate', headers=h, json=terms)
    assert preview.status_code==200, preview.text
    saved=client.post(url+'/conditions', headers=h, json=terms)
    assert saved.status_code==200, saved.text
    assert saved.json()['amount']==terms['amount']
    assert saved.json()['score']['score']==preview.json()['score']
    assert saved.json()['decision']['outcome']==preview.json()['outcome']

def test_manual_approval_creates_new_decision_and_offer(client):
    h=auth(client)
    a=next(a for a in get_apps(client,h) if 'Клён' in a['company_name'])
    url=f"/applications/{a['id']}"
    assert client.post(url+'/review',headers=h,json={'comment':'Контекст клиента'}).status_code==200
    response=client.post(url+'/transition',headers=h,json={'event':'manual_approve','comment':'Демо-проверка документов выполнена'})
    assert response.status_code==200,response.text
    assert response.json()['offer'] and response.json()['decision']['outcome']=='approve'
    assert client.post(url+'/transition',headers=h,json={'event':'accept_offer'}).status_code==403
    assert client.post(url+'/accept',headers=h).json()['state']=='SERVICING'

def test_servicing_changes_are_persisted_and_reflected_in_portfolio(client):
    h=auth(client)
    a=next(a for a in get_apps(client,h) if 'Весна' in a['company_name'])
    url=f"/applications/{a['id']}/servicing"
    before=client.get(url,headers=h).json()
    assert client.post(url+'/forecast',headers=h,json={'revenue_drop_pct':200,'extra_expense':-1}).status_code==422
    assert client.post(url+'/autopilot',headers=h,json={'enabled':True,'max_bridge':-100}).status_code==422
    result=client.post(url+'/apply',headers=h,json={'action':'collect_receivables'})
    assert result.status_code==200,result.text
    after=client.get(url,headers=h).json()
    assert after['account']['servicing_log']
    assert after['radar']['receivables']['collectable_overdue'] < before['radar']['receivables']['collectable_overdue']
    assert (after['radar']['gap'] or {}).get('amount',0) < before['radar']['gap']['amount']
    assert client.post(url+'/apply',headers=h,json={'action':'collect_receivables'}).status_code==409
    assert client.get('/portfolio/metrics',headers=h).json()['with_preventive_action']>=1
    assert client.post(url+'/apply',headers=auth(client,'underwriter@bank.ru','bank123'),json={'action':'shift_date'}).status_code==403

def test_autopilot_records_a_single_execution(client):
    h=auth(client)
    a=next(a for a in get_apps(client,h) if 'Весна' in a['company_name'])
    url=f"/applications/{a['id']}/servicing"
    assert client.post(url+'/autopilot',headers=h,json={'enabled':True,'max_bridge':0}).status_code==200
    response=client.post(url+'/autopilot/run',headers=h)
    assert response.status_code==200,response.text
    count=len(response.json()['account']['servicing_log'])
    assert response.json()['account']['autopilot']['last_result']['applied']=='collect_receivables'
    second=client.post(url+'/autopilot/run',headers=h).json()
    assert len(second['account']['servicing_log'])==count
    assert second['account']['autopilot']['max_bridge']==0

def test_policy_validation_rbac_and_simulation(client):
    h=auth(client)
    for bad in ['score_bands: []','score_bands: {approve_min: 20, counter_min: 90}', 'score_bands: {approve_min: 70, counter_min: 45}\nrequire_sources: [{}]', 'score_bands: {approve_min: 70, counter_min: 45}\nhard_declines: [{op: {}, reason: test}]']:
        assert client.post('/policies/simulate',headers=h,json={'yaml_text':bad}).status_code==422
        assert client.post('/policies',headers=h,json={'name':'bad','yaml_text':bad}).status_code==422
    active=client.get('/policies/active',headers=h).json()
    text=active['yaml_text'].replace('counter_min: 45','counter_min: 35')
    result=client.post('/policies/simulate',headers=h,json={'yaml_text':text,'limit':500})
    assert result.status_code==200,result.text
    assert result.json()['n']>=5
    version=client.post('/policies',headers=h,json={'name':'Тестовая политика','yaml_text':text})
    assert version.status_code==201,version.text
    underwriter=auth(client,'underwriter@bank.ru','bank123')
    assert client.post(f"/policies/{version.json()['version']}/activate",headers=underwriter).status_code==403
    assert client.post(f"/policies/{version.json()['version']}/activate",headers=h).status_code==200
    assert client.get('/policies/audit',headers=h).json()

def test_collaboration_is_server_persisted_and_role_checked(client):
    h=auth(client)
    a=get_apps(client,h)[0];url=f"/applications/{a['id']}/collaboration"
    assert client.post(url,headers=h,json={'actor':'employee','task':'finance','complete':True}).status_code==403
    for actor,task in [('accountant','finance'),('employee','documents'),('director','terms')]:
        result=client.post(url,headers=h,json={'actor':actor,'task':task,'complete':True})
        assert result.status_code==200,result.text
    assert client.post(url,headers=h,json={'actor':'director','sign':True}).json()['signed'] is True
    assert len(client.get(url,headers=h).json()['history'])==4

def test_actual_document_upload_download_and_access(client):
    h=auth(client)
    created=client.post('/applications',headers=h,json={'product_id':1,'amount':500000,'term_months':12,'purpose':'Тест файлов'}).json()
    url=f"/applications/{created['id']}/documents"
    content=b'%PDF-1.4\nsynthetic test file\n%%EOF'
    response=client.post(url+'/file',headers=h,data={'doc_type':'passport'},files={'file':('synthetic.pdf',content,'application/pdf')})
    assert response.status_code==200,response.text
    assert next(d for d in response.json() if d['type']=='passport')['has_file'] is True
    downloaded=client.get(url+'/passport/file',headers=h)
    assert downloaded.status_code==200 and downloaded.content==content
    outsider=auth(client,'client@demo.ru','client123')
    assert client.get(url+'/passport/file',headers=outsider).status_code==403
    assert client.delete(url+'/passport',headers=h).status_code==200
    assert client.get(url+'/passport/file',headers=h).status_code==404
