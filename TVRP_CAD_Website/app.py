import os, sqlite3, secrets, functools
from datetime import datetime, timezone
from flask import Flask, request, redirect, url_for, session, render_template, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash

ROOT=os.path.dirname(__file__)
DB=os.environ.get('TVRP_DB_PATH',os.path.join(ROOT,'cad.sqlite3'))
app=Flask(__name__)
app.secret_key=os.environ.get('TVRP_SECRET_KEY',secrets.token_hex(32))
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.environ.get('TVRP_HTTPS')=='1',MAX_CONTENT_LENGTH=1024*1024)

def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c

def init():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'member',created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS departments(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,kind TEXT NOT NULL,abbreviation TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS memberships(user_id INTEGER NOT NULL,department_id INTEGER NOT NULL,PRIMARY KEY(user_id,department_id),FOREIGN KEY(user_id) REFERENCES users(id),FOREIGN KEY(department_id) REFERENCES departments(id));
 CREATE TABLE IF NOT EXISTS units(id INTEGER PRIMARY KEY,callsign TEXT UNIQUE NOT NULL,department_id INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'Available',FOREIGN KEY(department_id) REFERENCES departments(id));
 CREATE TABLE IF NOT EXISTS incidents(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,nature TEXT NOT NULL,location TEXT NOT NULL,priority INTEGER NOT NULL DEFAULT 3,status TEXT NOT NULL DEFAULT 'Pending',notes TEXT NOT NULL DEFAULT '',created TEXT NOT NULL,created_by INTEGER NOT NULL,FOREIGN KEY(created_by) REFERENCES users(id));
 CREATE TABLE IF NOT EXISTS assignments(incident_id INTEGER NOT NULL,unit_id INTEGER NOT NULL,PRIMARY KEY(incident_id,unit_id),FOREIGN KEY(incident_id) REFERENCES incidents(id),FOREIGN KEY(unit_id) REFERENCES units(id));
 CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,created TEXT NOT NULL,created_by INTEGER NOT NULL,FOREIGN KEY(created_by) REFERENCES users(id));
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor INTEGER,action TEXT NOT NULL,created TEXT NOT NULL);''')
init()

def now():return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
def setting(k,default=''):
 with db() as c:
  r=c.execute('SELECT value FROM settings WHERE key=?',(k,)).fetchone();return r['value'] if r else default

def logged():
 if not session.get('uid'):return None
 with db() as c:return c.execute('SELECT id,username,role FROM users WHERE id=?',(session['uid'],)).fetchone()

def csrf():
 if 'csrf' not in session:session['csrf']=secrets.token_urlsafe(24)
 return session['csrf']
@app.context_processor
def ctx():return dict(user=logged(),community=setting('community','The Vibe RP'),csrf=csrf())
@app.before_request
def protect():
 if request.method in ('POST','PUT','PATCH','DELETE') and request.endpoint!='api_status':
  if not secrets.compare_digest(request.form.get('csrf',''),session.get('csrf','')):abort(400,'Invalid security token. Refresh and retry.')

def auth(f):
 @functools.wraps(f)
 def w(*a,**k):return f(*a,**k) if logged() else redirect(url_for('login'))
 return w

def roles(*allowed):
 def dec(f):
  @functools.wraps(f)
  @auth
  def w(*a,**k):
   if logged()['role'] not in allowed:abort(403)
   return f(*a,**k)
  return w
 return dec

def log(c,action):c.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)',(session.get('uid'),action,now()))

def page(name,**kwargs):return render_template(name,**kwargs)

@app.route('/setup',methods=['GET','POST'])
def setup():
 with db() as c:
  if c.execute('SELECT COUNT(*) FROM users').fetchone()[0]:return redirect(url_for('login'))
  if request.method=='POST':
   username=request.form.get('username','').strip();pw=request.form.get('password','');community=request.form.get('community','').strip()
   if len(username)<3 or len(pw)<12 or len(community)<3:return page('setup.html',error='Use a username of 3+ characters, a password of 12+ characters, and a community name.')
   c.execute('INSERT INTO users(username,password,role,created) VALUES(?,?,?,?)',(username,generate_password_hash(pw),'owner',now()))
   c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',('community',community))
   for n,k,a in [('Los Santos Police Department','Police','LSPD'),('Los Santos Fire Department','Fire','LSFD'),('San Andreas EMS','EMS','SAEMS'),('Emergency Communications','Dispatch','911'),('Department of Transportation','DOT','DOT'),('Civilian Operations','Civilian','CIV')]:c.execute('INSERT INTO departments(name,kind,abbreviation) VALUES(?,?,?)',(n,k,a))
   c.commit();session.clear();session['uid']=c.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone()['id'];return redirect(url_for('dashboard'))
 return page('setup.html')

@app.route('/login',methods=['GET','POST'])
def login():
 with db() as c:
  if not c.execute('SELECT COUNT(*) FROM users').fetchone()[0]:return redirect(url_for('setup'))
  if request.method=='POST':
   u=c.execute('SELECT * FROM users WHERE username=?',(request.form.get('username',''),)).fetchone()
   if u and check_password_hash(u['password'],request.form.get('password','')):session.clear();session['uid']=u['id'];return redirect(url_for('dashboard'))
   return page('login.html',error='Incorrect username or password.')
 return page('login.html')
@app.post('/logout')
@auth
def logout():session.clear();return redirect(url_for('login'))
@app.route('/')
@auth
def dashboard():
 with db() as c:
  stats={t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('users','departments','units','incidents','reports')}
  incidents=c.execute('SELECT * FROM incidents ORDER BY id DESC LIMIT 8').fetchall()
 return page('dashboard.html',stats=stats,incidents=incidents)

@app.route('/incidents',methods=['GET','POST'])
@auth
def incidents():
 with db() as c:
  if request.method=='POST':
   if logged()['role'] not in ('owner','admin','dispatcher'):abort(403)
   kind=request.form.get('kind','');nature=request.form.get('nature','').strip()[:120];location=request.form.get('location','').strip()[:160]
   if kind not in ('Police','Fire','EMS','DOT') or not nature or not location:abort(400)
   p=int(request.form.get('priority','3'))
   if p not in (1,2,3,4,5):abort(400)
   c.execute('INSERT INTO incidents(kind,nature,location,priority,created,created_by) VALUES(?,?,?,?,?,?)',(kind,nature,location,p,now(),logged()['id']));log(c,'Created incident');c.commit();return redirect(url_for('incidents'))
  data=c.execute('SELECT * FROM incidents ORDER BY id DESC').fetchall();units=c.execute('SELECT units.*,departments.kind FROM units JOIN departments ON departments.id=units.department_id ORDER BY callsign').fetchall();assignments=c.execute('SELECT * FROM assignments').fetchall()
 return page('incidents.html',items=data,units=units,assignments=assignments)
@app.post('/incidents/<int:id>/update')
@roles('owner','admin','dispatcher')
def incident_update(id):
 status=request.form.get('status','')
 if status not in ('Pending','Dispatched','En Route','On Scene','Working','Completed','Cancelled'):abort(400)
 with db() as c:
  c.execute('UPDATE incidents SET status=? WHERE id=?',(status,id));log(c,f'Updated incident {id} to {status}');c.commit()
 return redirect(url_for('incidents'))
@app.post('/incidents/<int:id>/assign')
@roles('owner','admin','dispatcher')
def incident_assign(id):
 unit=int(request.form.get('unit_id','0'))
 with db() as c:
  if not c.execute('SELECT id FROM incidents WHERE id=?',(id,)).fetchone() or not c.execute('SELECT id FROM units WHERE id=?',(unit,)).fetchone():abort(404)
  c.execute('INSERT OR IGNORE INTO assignments(incident_id,unit_id) VALUES(?,?)',(id,unit));log(c,f'Assigned unit {unit} to incident {id}');c.commit()
 return redirect(url_for('incidents'))

@app.route('/units',methods=['GET','POST'])
@auth
def units():
 with db() as c:
  if request.method=='POST':
   if logged()['role'] not in ('owner','admin','dispatcher'):abort(403)
   callsign=request.form.get('callsign','').strip()[:30];department=int(request.form.get('department_id','0'))
   if not callsign or not c.execute('SELECT id FROM departments WHERE id=?',(department,)).fetchone():abort(400)
   try:c.execute('INSERT INTO units(callsign,department_id) VALUES(?,?)',(callsign,department));log(c,'Created unit '+callsign);c.commit()
   except sqlite3.IntegrityError:return page('error.html',message='That callsign already exists.')
   return redirect(url_for('units'))
  items=c.execute('SELECT units.*,departments.name,departments.kind FROM units JOIN departments ON units.department_id=departments.id ORDER BY callsign').fetchall();deps=c.execute('SELECT * FROM departments').fetchall()
 return page('units.html',items=items,deps=deps)
@app.post('/units/<int:id>/status')
@roles('owner','admin','dispatcher')
def unit_status(id):
 s=request.form.get('status','')
 if s not in ('Available','Dispatched','En Route','On Scene','Working','Transporting','Out of Service','Off Duty'):abort(400)
 with db() as c:c.execute('UPDATE units SET status=? WHERE id=?',(s,id));log(c,f'Updated unit {id} to {s}');c.commit()
 return redirect(url_for('units'))

@app.route('/reports',methods=['GET','POST'])
@auth
def reports():
 with db() as c:
  if request.method=='POST':
   kind=request.form.get('kind','');title=request.form.get('title','').strip()[:150];body=request.form.get('body','').strip()[:10000]
   if kind not in ('Police','Fire','EMS','DOT') or not title or not body:abort(400)
   if logged()['role']=='member':abort(403)
   c.execute('INSERT INTO reports(kind,title,body,created,created_by) VALUES(?,?,?,?,?)',(kind,title,body,now(),logged()['id']));log(c,'Created '+kind+' report');c.commit();return redirect(url_for('reports'))
  if logged()['role']=='member':items=[]
  else:items=c.execute('SELECT reports.*,users.username FROM reports JOIN users ON users.id=reports.created_by ORDER BY reports.id DESC').fetchall()
 return page('reports.html',items=items)

@app.route('/admin',methods=['GET','POST'])
@roles('owner','admin')
def admin():
 with db() as c:
  if request.method=='POST':
   action=request.form.get('action')
   if action=='community' and logged()['role']=='owner':
    name=request.form.get('community','').strip()[:100]
    if not name:abort(400)
    c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',('community',name))
   elif action=='department':
    name=request.form.get('name','').strip()[:100];abbr=request.form.get('abbreviation','').strip()[:16];kind=request.form.get('kind','')
    if not name or not abbr or kind not in ('Police','Fire','EMS','Dispatch','DOT','Civilian'):abort(400)
    try:c.execute('INSERT INTO departments(name,abbreviation,kind) VALUES(?,?,?)',(name,abbr,kind))
    except sqlite3.IntegrityError:return page('error.html',message='Department name already exists.')
   elif action=='user' and logged()['role']=='owner':
    username=request.form.get('username','').strip();pw=request.form.get('password','');role=request.form.get('role','')
    if len(username)<3 or len(pw)<12 or role not in ('admin','dispatcher','officer','fire','ems','dot','member'):abort(400)
    try:c.execute('INSERT INTO users(username,password,role,created) VALUES(?,?,?,?)',(username,generate_password_hash(pw),role,now()))
    except sqlite3.IntegrityError:return page('error.html',message='Username already exists.')
   else:abort(403)
   log(c,'Admin action: '+action);c.commit();return redirect(url_for('admin'))
  users=c.execute('SELECT id,username,role,created FROM users ORDER BY id').fetchall();deps=c.execute('SELECT * FROM departments ORDER BY kind,name').fetchall();audit=c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 15').fetchall()
 return page('admin.html',users=users,deps=deps,audit=audit)
@app.get('/api/health')
def api_status():return jsonify(status='ok',community=setting('community','The Vibe RP'),version='0.1.0')
@app.errorhandler(403)
def forbidden(e):return page('error.html',message='You do not have permission to access this page.'),403
@app.errorhandler(400)
def bad(e):return page('error.html',message='Invalid request. Please check the form and try again.'),400
if __name__=='__main__':app.run(host='127.0.0.1',port=int(os.environ.get('PORT','5000')),debug=False)
