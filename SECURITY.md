# Security Rules — Diligence Project

These rules apply to every Claude Code session, every git push, every deployment in this repo. Read at start of any session that touches credentials, deployment, or commits.

---

## 1. Never read or expose these files

Claude **must refuse** to read, print, paste, or otherwise output the contents of these files into chat, logs, agent outputs, or commits:

| Path | Why |
|------|-----|
| `.env` | Live API keys (Speechmatics / Featherless / FMP) |
| `.env.local`, `.env.*.local` | Local overrides — same risk |
| `~/.config/gcloud/application_default_credentials.json` | RobotBoy production ADC — do not touch ever |
| `~/adc-robotboy-backup.json` | Backup of RobotBoy ADC |
| `~/.ssh/`, `~/.ssh/id_*`, `~/.ssh/config` | SSH private keys |
| `~/.gnupg/`, `*.gpg`, `*.pem`, `*.key`, `*.p12`, `*.pfx` | Crypto material |
| `~/.aws/credentials`, `~/.aws/config` | AWS credentials |
| `~/.gcloud/*`, `~/.config/gcloud/*` | GCP credentials |
| `~/.docker/config.json` | Registry tokens |
| `~/.netrc` | HTTP basic-auth creds |
| Anything matching `*token*`, `*secret*`, `*credentials*`, `*.key` outside this repo unless explicitly approved |

If Claude needs to verify a key works, run a probe script that uses the key — do NOT print the key itself. Echo only "set" / "not set" / "format looks correct."

---

## 2. Git hygiene — no secrets pushed, ever

### Hard rules
- `.env` is gitignored (line 4 of `.gitignore`). Never modify `.gitignore` to remove `.env`.
- Before any `git add`, run `git status` and visually confirm no `.env`, `*.key`, `*.pem`, or `data/{ticker}/raw/*` files are staged.
- Never use `git add -A` or `git add .` blindly. Add specific files by name.
- Never use `--force` push to `main`. If divergence, investigate before overwriting.
- Never use `--no-verify` to skip hooks (pre-commit secret scanners catch leaks).

### If a secret is accidentally committed
1. **Immediately** rotate the key at the provider (Speechmatics / Featherless / FMP / etc.). Treat the leaked key as compromised even if the commit was never pushed.
2. Only after rotation, rewrite history (`git filter-repo` or BFG) and force-push.
3. Order matters: rotate first, history-rewrite second. A leaked key in even a deleted commit may already have been scraped.

### Public repo checklist (before `gh repo create --public` or making private repo public)
- [ ] `.env` not tracked: `git ls-files | grep -E '^\.env$'` returns nothing
- [ ] No keys in commit history: `git log -p | grep -E '(api_key|API_KEY|secret|password)' -i`
- [ ] No real emails leaked beyond what's intentional (`SEC_USER_AGENT` is intentional, login passwords are not)
- [ ] No internal hostnames or IPs in code (production-server IPs for other projects belong in their own repos, never here)

---

## 3. Credential handling in code

- Always load keys via `os.getenv("KEY_NAME")` after `dotenv.load_dotenv()`. Never hard-code.
- Never log a key — not in print statements, not in error tracebacks, not in agent outputs. Sanitize errors before re-raising.
- Never pass a key as a CLI argument (`script.py --key=xyz`) — it lands in shell history. Use env vars.
- Featherless / Speechmatics responses sometimes echo the request — strip auth headers before printing response bodies during debugging.
- Tenacity retry logging: if retrying an HTTP call, log the URL and status code, NOT request headers (which contain auth).

---

## 4. Vertex / gcloud — RobotBoy ADC is sacred

Repeat from `CONTEXT.md` because it's the most expensive mistake possible here:

- **Never** run `gcloud auth application-default login` — overwrites RobotBoy's ADC, re-routes its billing.
- **Never** run `gcloud auth application-default set-quota-project` — same effect.
- The cosmetic warning "active project does not match the quota project in your local ADC" is **expected**. Ignore it. `vertex_client.py` does not read the ADC file.
- Always confirm `gcloud config configurations list` shows `hackathon` as `ACTIVE` before any gcloud command.
- Backup at `~/adc-robotboy-backup.json` exists if a rescue is ever needed.

---

## 5. Data ingestion safety

- SEC EDGAR User-Agent must be a real contact email (their ToS — they block fake UAs). Already set in `.env`.
- Do not redistribute SEC filings or earnings call audio in commits — they're large and the originals are public anyway. `data/*/raw/` and `*.mp3` are gitignored.
- Earnings call MP3s are publicly available recordings of public companies. No personal data concern, but do not upload to public buckets / share links unnecessarily.

---

## 6. Deployment (Vultr) — when we get there

Day 3 only, not now. When deploying:

- SSH to Vultr VM via key auth only — never password auth. Disable PasswordAuthentication in `/etc/ssh/sshd_config`.
- API keys live in a `.env` on the VM, mode `600`, owned by the app user — never in the repo, never in a Docker image layer, never in environment exposed by FastAPI's `/debug` or `/env` endpoints (don't add such endpoints).
- FastAPI must not expose `.env`, `/etc/`, `/root/`, or any path outside the app's static dir. Use explicit route allowlists.
- Bind FastAPI to `127.0.0.1`, put nginx in front with TLS via Let's Encrypt. Don't expose Uvicorn on `0.0.0.0:8000` directly.
- Rate-limit the public demo URL (nginx `limit_req_zone`) — judges + curious public will hit it. Cap at 5 req/min per IP for the inference endpoint.
- CORS allowlist: only the frontend origin, never `*` once deployed.
- No `/admin`, `/debug`, `/metrics` endpoints exposed publicly. If observability needed, restrict to specific IP.

---

## 7. GDPR / personal data (founder in Romania, EU)

- Users of the demo (if any beyond judges) submit a ticker — no PII collected. Good.
- Do NOT add user login, email collection, or analytics that store IP without consent banner. If demo gains real users, add a consent banner before any tracking.
- If logging requests on Vultr, anonymise IP (mask last octet) or set log retention to 7 days max.

---

## 8. Claude session conduct

When in doubt, Claude should:

1. **Refuse to print** anything matching secret-shaped strings (long random alphanumeric, JWT-shaped tokens, anything labelled `api_key` / `secret` / `password`).
2. **Warn before** running destructive commands: `rm -rf`, `git reset --hard`, `git push --force`, `DROP TABLE`, anything that overwrites a file owned by another project (RobotBoy ADC).
3. **Ask before** committing or pushing. Never `git commit` or `git push` autonomously.
4. **Flag immediately** if it spots a secret in code being written, in command output, or in a file the user pastes. Stop, tell the user, suggest rotation.
5. **Never run** `gcloud auth application-default login` or `gcloud auth application-default set-quota-project` — full stop, in any context, in this repo.

---

## 9. Audit checklist (run weekly during active development)

```bash
# Secrets not tracked
git ls-files | grep -E '\.(env|key|pem|p12)$'

# No keys in last 10 commits
git log -p -10 | grep -iE '(api[_-]?key|secret|password|token).*=.*[A-Za-z0-9]{20,}'

# .gitignore hasn't been quietly weakened
grep -E '^\.env$' .gitignore

# RobotBoy ADC untouched (sha changes only when login is run)
shasum ~/.config/gcloud/application_default_credentials.json
shasum ~/adc-robotboy-backup.json
# Compare — primary should not have drifted unexpectedly
```

If any check fails, stop work and triage before continuing.

---

End of rules.
