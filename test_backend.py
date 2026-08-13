import sys
sys.path.insert(0, 'backend')
sys.path.insert(0, 'frontend')

# Test database layer
from backend.database.db import init_db, get_db
init_db()
print('DB initialized OK')

# Test user creation
from backend.services.auth_service import register, login
try:
    user = register('Test HR', 'Test Corp', 'test@example.com', 'testpass')
    print('Registered:', user['name'], '/', user['company_name'])
except ValueError as e:
    print('Register error (ok if dupe):', e)

# Test login
user = login('test@example.com', 'testpass')
print('Login:', user['name'], '@', user['company_name'])

# Test JD creation
from backend.services.jd_service import create_job_description, get_active_jd
jd_id = create_job_description(user['company_id'], user['id'], 'Senior AI Engineer', 'Need a great AI engineer', 'Python, ML, PyTorch')
print('Created JD #' + str(jd_id))
active = get_active_jd(user['company_id'])
print('Active JD:', active['title'])

# Test analytics
from backend.services.analytics_service import get_dashboard_kpis
kpis = get_dashboard_kpis(user['company_id'])
print('KPIs total_resumes:', kpis['_raw']['total_resumes'])

print('All backend tests PASSED')
