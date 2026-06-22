# API Keys Setup Guide

Step-by-step instructions for obtaining every API key this project needs.
Refer back to this guide whenever you need to rotate keys or set up a new environment.

---

## 1. OpenAI API Key

**Used for:** LLM classification, response generation, summarization, embeddings.

### Steps

1. Go to [platform.openai.com](https://platform.openai.com) and sign in or create an account.
2. Click your profile icon (top right) → **API Keys**.
3. Click **Create new secret key**.
4. Give it a name (e.g. `ai-support-agent-dev`).
5. Copy the key — it starts with `sk-proj-...`
   > It is shown **only once**. Copy it immediately.
6. Paste it into your `.env` file:
   ```
   OPENAI_API_KEY=sk-proj-...
   ```

### Add Billing Credits

The API key will not work without credits on your account.

1. Go to [platform.openai.com/settings/billing](https://platform.openai.com/settings/billing).
2. Click **Add payment method** and enter your card details.
3. Click **Add to credit balance** → add **$5–10** to start.
   > `gpt-4o-mini` costs ~$0.15 per 1M input tokens — $5 lasts weeks of development.

### Models Used in This Project

| Purpose | Model | Cost |
|---------|-------|------|
| Development | `gpt-4o-mini` | Cheap + fast |
| Production / Evaluation | `gpt-4o` | Best accuracy |
| Embeddings | `text-embedding-3-small` | Very cheap |

---

## 2. Anthropic API Key

**Used for:** Optional LLM fallback (Claude 3.5 Sonnet). Not required if OpenAI is working.

### Steps

1. Go to [console.anthropic.com](https://console.anthropic.com) and sign in or create an account.
2. Click **API Keys** in the left sidebar.
3. Click **Create Key**.
4. Give it a name (e.g. `ai-support-agent-dev`).
5. Copy the key — it starts with `sk-ant-...`
   > It is shown **only once**. Copy it immediately.
6. Paste it into your `.env` file:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

### Add Billing Credits

1. Go to [console.anthropic.com/settings/billing](https://console.anthropic.com/settings/billing).
2. Click **Add credits** → minimum top-up is **$5**.

### Switch Provider

To use Anthropic instead of OpenAI, change one line in `.env`:
```
LLM_PROVIDER=anthropic
```
Switch back to OpenAI:
```
LLM_PROVIDER=openai
```

### Models Used in This Project

| Purpose | Model |
|---------|-------|
| Development + Production | `claude-3-5-sonnet-20241022` |

---

## 3. Langfuse Keys (Public + Secret)

**Used for:** LLM tracing, prompt tracking, token monitoring, cost tracking, evaluation.

### Steps

1. Go to [cloud.langfuse.com](https://cloud.langfuse.com) and sign in or create an account.
2. When prompted for a **data region**, choose:
   - **US** → `https://us.cloud.langfuse.com` ← used in this project
   - **EU** → `https://eu.cloud.langfuse.com` (only if GDPR compliance is required)
3. **Create a new Project** (e.g. `ai-customer-support-agent`).
4. Inside the project, go to **Project Settings** → **API Keys**.
5. Click **Create API Key**.
6. Both keys are shown together:
   - `pk-lf-...` → Public Key
   - `sk-lf-...` → Secret Key
   > Copy both immediately — the secret key is shown **only once**.
7. Paste them into your `.env` file:
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=https://us.cloud.langfuse.com
   ```

### Langfuse is Free

No billing required. The Langfuse cloud hobby tier is free and sufficient for this project.

### Verify Connection

```bash
.venv/bin/python -c "
from config.settings import settings
from langfuse import Langfuse
lf = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host
)
lf.auth_check()
print('Langfuse: OK')
"
```

---

## Security Rules

| Rule | Reason |
|------|--------|
| Never commit `.env` to git | `.gitignore` already excludes it |
| Never paste keys in chat or email | They get stored in logs |
| Never hardcode keys in source files | Use `config/settings.py` which reads from `.env` |
| Rotate keys if accidentally exposed | Go to the provider dashboard and delete + recreate |
| Use separate keys per environment | One key for dev, a different key for production |

---

## Quick Reference

| Variable | Provider | Where to Get It |
|----------|----------|-----------------|
| `OPENAI_API_KEY` | OpenAI | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `ANTHROPIC_API_KEY` | Anthropic | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| `LANGFUSE_PUBLIC_KEY` | Langfuse | Project Settings → API Keys |
| `LANGFUSE_SECRET_KEY` | Langfuse | Project Settings → API Keys |
