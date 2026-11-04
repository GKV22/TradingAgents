import { useEffect, useState } from 'react'
import type { Settings, AgentLLMs, RoleLLM, ModelList } from '../types'
import { PROVIDERS, DEFAULT_MODELS, EFFORT_PROVIDERS, ROLE_LABELS, ROLE_DESC, ANALYST_OPTIONS } from '../types'
import './Settings.css'

const EFFORT_OPTS = ['none', 'low', 'medium', 'high']
const DEPTH_OPTS = [
  { value: 1, label: '1 exchange — fast, low cost' },
  { value: 2, label: '2 exchanges — mid effort, mid cost' },
  { value: 3, label: '3 exchanges — thorough, higher cost' },
]
const LANG_OPTS = ['en', 'zh', 'ja', 'ko', 'de', 'fr', 'es']
const CUSTOM = '__custom__'

function RoleRow({
  roleKey,
  value,
  list,
  modelLists,
  onChange,
  onRefresh,
}: {
  roleKey: keyof AgentLLMs
  value: RoleLLM
  list: ModelList | undefined
  modelLists: Record<string, ModelList>
  onChange: (v: RoleLLM) => void
  onRefresh: (provider: string) => Promise<string | null>
}) {
  const models = list?.models ?? []
  const [custom, setCustom] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshErr, setRefreshErr] = useState<string | null>(null)

  const handleProvider = (p: string) => {
    const offered = modelLists[p]?.models ?? []
    const preferred = DEFAULT_MODELS[p]
    const model = offered.includes(preferred) ? preferred : offered[0] ?? ''
    setCustom(offered.length === 0)
    setRefreshErr(null)
    onChange({ provider: p, model, base_url: null, reasoning_effort: null })
  }

  const handleModel = (m: string) => {
    if (m === CUSTOM) {
      setCustom(true)
      return
    }
    setCustom(false)
    onChange({ ...value, model: m })
  }

  const refresh = async () => {
    setRefreshing(true)
    setRefreshErr(await onRefresh(value.provider))
    setRefreshing(false)
  }

  // A saved model the list does not contain is kept selectable (flagged), never silently replaced.
  const unlisted = value.model !== '' && !models.includes(value.model)
  const showInput = custom || models.length === 0

  const supportsEffort = EFFORT_PROVIDERS.has(value.provider)

  return (
    <div className="role-row">
      <div className="role-meta">
        <span className="role-name">{ROLE_LABELS[roleKey]}</span>
        <span className="role-desc">{ROLE_DESC[roleKey]}</span>
      </div>
      <div className="role-fields">
        <div className="field">
          <label>Provider</label>
          <select value={value.provider} onChange={(e) => handleProvider(e.target.value)}>
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div className="field field-model">
          <label>Model</label>
          <div className="model-picker">
            {models.length > 0 && (
              <select value={custom ? CUSTOM : value.model} onChange={(e) => handleModel(e.target.value)}>
                {unlisted && !custom && (
                  <option value={value.model}>{value.model} (not in list)</option>
                )}
                {models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
                <option value={CUSTOM}>Custom…</option>
              </select>
            )}
            {list?.refreshable && (
              <button
                type="button"
                className="refresh-btn"
                onClick={refresh}
                disabled={refreshing}
                title={
                  list.source === 'provider' && list.fetched_at
                    ? `Fetched from ${value.provider} at ${list.fetched_at}`
                    : `Built-in list — fetch the latest from ${value.provider}`
                }
              >
                {refreshing ? '…' : '↻'}
              </button>
            )}
          </div>
          {showInput && (
            <input
              type="text"
              placeholder="model ID"
              value={value.model}
              onChange={(e) => onChange({ ...value, model: e.target.value })}
            />
          )}
          {refreshErr && <span className="err-msg">{refreshErr}</span>}
        </div>
        {supportsEffort && (
          <div className="field">
            <label>Effort</label>
            <select
              value={value.reasoning_effort ?? 'none'}
              onChange={(e) =>
                onChange({ ...value, reasoning_effort: e.target.value === 'none' ? null : e.target.value })
              }
            >
              {EFFORT_OPTS.map((o) => (
                <option key={o} value={o}>{o}</option>
              ))}
            </select>
          </div>
        )}
        <div className="field field-url">
          <label>Base URL (optional)</label>
          <input
            type="text"
            placeholder="default"
            value={value.base_url ?? ''}
            onChange={(e) =>
              onChange({ ...value, base_url: e.target.value || null })
            }
          />
        </div>
      </div>
    </div>
  )
}

export default function Settings() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [modelLists, setModelLists] = useState<Record<string, ModelList>>({})

  useEffect(() => {
    fetch('/api/settings')
      .then((r) => r.json())
      .then((d) => setSettings(d as Settings))
      .catch(() => setErr('Failed to load settings'))
    fetch('/api/models')
      .then((r) => r.json())
      .then((d) => setModelLists(d as Record<string, ModelList>))
      .catch(() => setErr('Failed to load model lists'))
  }, [])

  const refreshModels = async (provider: string): Promise<string | null> => {
    try {
      const r = await fetch(`/api/models/${encodeURIComponent(provider)}/refresh`, { method: 'POST' })
      const d = await r.json()
      if (!r.ok) return String(d.detail ?? r.statusText)
      setModelLists((prev) => ({ ...prev, [provider]: d as ModelList }))
      return null
    } catch (e) {
      return String(e)
    }
  }

  if (!settings) {
    return <div className="loading">{err ?? 'Loading…'}</div>
  }

  const save = async () => {
    setSaving(true)
    setMsg(null)
    setErr(null)
    try {
      const r = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })
      if (!r.ok) throw new Error(await r.text())
      setMsg('Saved')
      setTimeout(() => setMsg(null), 3000)
    } catch (e) {
      setErr(String(e))
    } finally {
      setSaving(false)
    }
  }

  const setRole = (key: keyof AgentLLMs, v: RoleLLM) =>
    setSettings({ ...settings, agent_llms: { ...settings.agent_llms, [key]: v } })

  const toggleAnalyst = (a: string) => {
    const list = settings.analysts.includes(a)
      ? settings.analysts.filter((x) => x !== a)
      : [...settings.analysts, a]
    setSettings({ ...settings, analysts: list })
  }

  const roles = Object.keys(ROLE_LABELS) as (keyof AgentLLMs)[]

  return (
    <div className="settings">
      {/* Per-role LLMs */}
      <section>
        <div className="section-title">Agent LLMs</div>
        <div className="card roles-card">
          {roles.map((r) => (
            <RoleRow
              key={r}
              roleKey={r}
              value={settings.agent_llms[r]}
              list={modelLists[settings.agent_llms[r].provider]}
              modelLists={modelLists}
              onChange={(v) => setRole(r, v)}
              onRefresh={refreshModels}
            />
          ))}
        </div>
      </section>

      {/* General */}
      <section>
        <div className="section-title">General</div>
        <div className="card general-grid">
          <div className="field">
            <label>No. of Analyst Exchanges</label>
            <select
              value={settings.research_depth}
              onChange={(e) =>
                setSettings({ ...settings, research_depth: Number(e.target.value) })
              }
            >
              {DEPTH_OPTS.map(({ value, label }) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label>Output Language</label>
            <select
              value={settings.output_language}
              onChange={(e) => setSettings({ ...settings, output_language: e.target.value })}
            >
              {LANG_OPTS.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </div>

        </div>
      </section>

      {/* Analysts */}
      <section>
        <div className="section-title">Active Analysts</div>
        <div className="card analysts-card">
          {ANALYST_OPTIONS.map(({ value, label }) => (
            <label key={value} className="check-label">
              <input
                type="checkbox"
                checked={settings.analysts.includes(value)}
                onChange={() => toggleAnalyst(value)}
              />
              {label}
            </label>
          ))}
        </div>
      </section>

      <div className="save-bar">
        <button className="primary" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save Settings'}
        </button>
        {msg && <span className="save-msg">{msg}</span>}
        {err && <span className="err-msg">{err}</span>}
      </div>
    </div>
  )
}
