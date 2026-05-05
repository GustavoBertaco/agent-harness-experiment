# Security Vulnerability Taxonomy — Shared SOP

This file is referenced by the `security-checker` agent. It defines the full vulnerability scan taxonomy (Sections A–G) and exception rules applied during every security review.

---

## Section A — Sensitive File Scan (run BEFORE diff scan)

Run: `git diff --name-only main...<branch>`

Flag any file in the output that matches these patterns as CRITICAL — regardless of content:

| Pattern | Examples |
|---------|---------|
| `.env*` | `.env`, `.env.local`, `.env.production` |
| `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.cer` | `server.key`, `cert.pem` |
| `*secret*`, `*credential*`, `*password*` | `secrets.json`, `db_credentials.yml` |
| `id_rsa`, `id_ed25519`, `id_ecdsa` | SSH private keys |
| `*.keystore`, `*.jks` | Java keystores |
| `config/secrets.*`, `config/master.key` | Rails-style secrets |

Exception: if the file is clearly a template (e.g., `.env.example`, `.env.template`), downgrade to LOW.

---

## Section B — CRITICAL findings (blocks merge)

Only examine lines **added or modified** (prefixed `+` in diff). Do not flag removed code.

### Hardcoded secrets
Passwords, API keys, tokens, or connection strings as string literals in non-test code.
- Variable names containing: `password`, `passwd`, `secret`, `api_key`, `token`, `auth`, `credential`, `private_key`, `access_key`, `client_secret`
- Examples: `password = "abc123"`, `api_key = "sk-..."`, `DATABASE_URL = "postgresql://user:pass@host/db"`

### Command injection
Shell execution with variable or user-controlled input.
- Python: `subprocess.call(..., shell=True)` where argument is not a literal string
- Any: `os.system(var)`, `eval(user_input)`, `exec(user_input)`

### SQL injection
SQL strings built with f-strings or `+` concatenation using variables.
- Examples: `f"SELECT * FROM {table}"`, `"WHERE id = " + user_id`
- Exception: parameterized queries (`cursor.execute("SELECT * FROM t WHERE id = ?", (user_id,))`) are safe.

### SSRF — Server-Side Request Forgery (OWASP A10 2025)
HTTP requests made to URLs derived from user input or external variables.
- `requests.get(user_input)`, `requests.get(f"http://...{var}...")`
- `urllib.request.urlopen(user_input)`
- `httpx.get(url)` or `httpx.post(url)` where `url` is a variable, not a literal
- `aiohttp.ClientSession().get(user_input)`
- Safe: `requests.get("https://api.example.com/fixed/path")` — literal URL only

### Insecure deserialization
Loading untrusted serialized data.
- Python: `pickle.loads(data)`, `yaml.load(data)` without `Loader=yaml.SafeLoader`

### Path traversal
Opening files at user-controlled paths without sanitization.
- `open(user_path)`, `os.path.join(base_dir, user_input)` without checking result stays inside `base_dir`

### Insecure TLS/SSL defaults
Disabling certificate verification "to make it work."
- `requests.get(..., verify=False)` or `requests.post(..., verify=False)` → CRITICAL
- `ssl_context.check_hostname = False`
- `ssl_context.verify_mode = ssl.CERT_NONE`

### Template injection
Rendering user-controlled input as a template.
- `jinja2.Template(user_input).render()`
- `jinja2.Environment(...).from_string(user_input)`
- `mako.template.Template(user_input)`

### JWT misuse
Bypassing signature verification.
- `jwt.decode(..., options={"verify_signature": False})`
- `algorithm="none"` or `algorithms=["none"]` in JWT decode
- `jwt.decode(token, None, algorithms=["none"])`

---

## Section C — HIGH findings (must be documented or fixed)

### Insecure cryptography
- `hashlib.md5()` or `hashlib.sha1()` used to hash passwords or auth tokens (fine for checksums — flag only when variable names suggest auth context)
- `random` module (not `secrets`) used to generate tokens, session IDs, or passwords

### Sensitive data in logs
- `logger.info(password)`, `print(api_key)`, `logging.debug(f"Token: {token}")`

### Overly permissive file permissions
- `chmod(path, 0o777)` or equivalent

### JWT algorithm confusion
- `jwt.decode(..., algorithms=["HS256", "RS256"])` — accepting multiple algorithm families enables algorithm confusion attacks

### CORS misconfiguration
- `Access-Control-Allow-Origin: *` combined with `Access-Control-Allow-Credentials: true`
- In Flask: `CORS(app, origins="*", supports_credentials=True)`
- In FastAPI: `allow_origins=["*"]` with `allow_credentials=True`

### SSL warning suppression
- `urllib3.disable_warnings()` — silences important security alerts

### Known CVEs in dependencies
Reported by the dependency audit tool (see Section G).

---

## Section D — MEDIUM findings (flag for awareness)

- **Bare exception suppression**: `except: pass` or `except Exception: pass` that silently swallows errors
- **Insecure XML parsing**: `xml.etree.ElementTree.parse()` or `lxml.etree.parse()` on untrusted input without disabling external entities
- **Debug flags in production paths**: `DEBUG = True`, hardcoded `localhost` URLs, or dev credentials outside test files
- **Unpinned dependencies with range operators**: `requests>=2.0` or `requests~=2.31` — range still allows pulling vulnerable future versions

---

## Section E — LOW findings (informational)

- TODO/FIXME security comments: `# TODO: validate input`, `# FIXME: sanitize this`
- Commented-out credentials: old passwords or keys left as comments

---

## Section F — Dependency pinning check

After the diff scan, check every modified dependency file:

**`requirements.txt`**: Flag any entry without an exact version pin (`==`) as HIGH.
- Bad: `requests`, `requests>=2.0`, `requests~=2.31`
- Good: `requests==2.31.0`

**`setup.py` / `pyproject.toml` `install_requires`**: Flag ranges or unpinned entries as MEDIUM (install_requires is intentionally flexible, but flag it for awareness).

**Recommendation**: Always include hash verification note — `pip install --require-hashes -r requirements.txt`

---

## Section G — Dependency audit tools

| If this file was modified | Run this command |
|---------------------------|------------------|
| `requirements.txt`, `setup.py`, `pyproject.toml` | `pip-audit` (if installed) or `pip install pip-audit && pip-audit` |
| `package.json` | `npm audit` |
| `Gemfile` | `bundle audit` |
| `go.mod` | `govulncheck ./...` |

If the tool is not installed and cannot be installed, note it as a recommendation in the report rather than a failure.

---

## Test file exceptions

If a suspicious pattern appears inside a test file (path contains `test`, `tests`, `spec`, or `__tests__`):
- Downgrade CRITICAL → LOW (e.g., `password = "test_password"` in a test fixture is not a real secret)
- Still report it at LOW so a human can confirm it's intentional

Exception: `verify=False` in tests is still MEDIUM — it can propagate to production code via copy-paste.
