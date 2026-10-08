import { useEffect, useState } from 'react'
import type { Settings, AgentLLMs, RoleLLM } from '../types'
import { PROVIDERS, DEFAULT_MODELS, EFFORT_PROVIDERS, ROLE_LABELS, ROLE_DESC, ANALYST_OPTIONS } from '../types'
import './Settings.css'

const EFFORT_OPTS = ['none', 'low', 'medium', 'high']
const DEPTH_OPTS = [
  { value: 1, label: '1 exchange — fast, low cost' },
  { value: 2, label: '2 exchanges — mid effort, mid cost' },
  { value: 3, label: '3 exchanges — thorough, higher cost' },
]
const LANG_OPTS = ['en', 'zh', 'ja', 'ko', 'de', 'fr', 'es']

function RoleRow({
  roleKey,
  value,
  onChange,
}: {
  roleKey: keyof AgentLLMs
  value: RoleLLM
  onChange: (v: RoleLLM) => void
}) {
  const handleProvider = (p: string) => {
    onChange({ provider: p, model: DEFAULT_MODELS[p] ?? '', base_url: null, reasoning_effort: null })
  }

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
        <div className="field">
          <label>Model</label>
          <input
            type="text"
            value={value.model}
            onChange={(e) => onChange({ ...value, model: e.target.value })}
          />
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

  useEffect(() => {
    fetch('/api/settings')
      .then((r) => r.json())
      .then((d) => setSettings(d as Settings))
      .catch(() => setErr('Failed to load settings'))
  }, [])

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
              onChange={(v) => setRole(r, v)}
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
